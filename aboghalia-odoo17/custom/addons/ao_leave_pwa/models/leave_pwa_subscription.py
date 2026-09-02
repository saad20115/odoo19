# -*- coding: utf-8 -*-
import base64
import json
import logging
import os

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = 'ao_leave_pwa.vapid_private_key'
VAPID_PUBLIC_KEY = 'ao_leave_pwa.vapid_public_key'
VAPID_SUBJECT = 'ao_leave_pwa.vapid_subject'


class LeavePwaSubscription(models.Model):
    _name = 'leave.pwa.subscription'
    _description = 'Leaves PWA Web Push Subscription'
    _rec_name = 'endpoint'

    user_id = fields.Many2one('res.users', required=True, index=True, ondelete='cascade')
    endpoint = fields.Char(required=True, index=True)
    p256dh = fields.Char(required=True)
    auth = fields.Char(required=True)
    user_agent = fields.Char()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('endpoint_uniq', 'unique(endpoint)', 'Push endpoint must be unique.'),
    ]

    @api.model
    def _ensure_vapid_keys(self):
        """Create VAPID keypair once (needed for Web Push over HTTPS)."""
        ICP = self.env['ir.config_parameter'].sudo()
        public = ICP.get_param(VAPID_PUBLIC_KEY)
        private = ICP.get_param(VAPID_PRIVATE_KEY)
        if public and private:
            return public, private
        try:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            _logger.warning('cryptography not available; Web Push VAPID keys not generated')
            return False, False

        key = ec.generate_private_key(ec.SECP256R1())
        private_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        public_numbers = key.public_key().public_numbers()
        x = public_numbers.x.to_bytes(32, 'big')
        y = public_numbers.y.to_bytes(32, 'big')
        uncompressed = b'\x04' + x + y
        public_b64 = base64.urlsafe_b64encode(uncompressed).decode().rstrip('=')

        ICP.set_param(VAPID_PRIVATE_KEY, private_pem)
        ICP.set_param(VAPID_PUBLIC_KEY, public_b64)
        if not ICP.get_param(VAPID_SUBJECT):
            ICP.set_param(VAPID_SUBJECT, 'mailto:leave-pwa@aboghaliaoffice.com')
        return public_b64, private_pem

    @api.model
    def get_vapid_public_key(self):
        public, _private = self._ensure_vapid_keys()
        return public or False

    @api.model
    def register_subscription(self, user, subscription, user_agent=None):
        """Upsert a browser PushSubscription JSON dict for the given user."""
        if not user or not subscription:
            return False
        endpoint = (subscription.get('endpoint') or '').strip()
        keys = subscription.get('keys') or {}
        p256dh = keys.get('p256dh') or ''
        auth = keys.get('auth') or ''
        if not endpoint or not p256dh or not auth:
            return False
        if len(endpoint) > 2048 or len(p256dh) > 512 or len(auth) > 512:
            return False

        existing = self.sudo().search([('endpoint', '=', endpoint)], limit=1)
        vals = {
            'user_id': user.id,
            'endpoint': endpoint,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': (user_agent or '')[:512],
            'active': True,
        }
        if existing:
            existing.write(vals)
            return existing
        return self.sudo().create(vals)

    @api.model
    def unregister_endpoint(self, user, endpoint):
        endpoint = (endpoint or '').strip()
        if not endpoint or not user:
            return False
        subs = self.sudo().search([('user_id', '=', user.id), ('endpoint', '=', endpoint)])
        subs.write({'active': False})
        return True

    @api.model
    def send_to_users(self, users, title, body, data=None):
        """Send Web Push to all active subscriptions of the given users.

        Uses an isolated venv helper (/opt/leave-pwa-push-venv) so pywebpush
        never conflicts with Odoo system cryptography packages.
        Falls back to in-process pywebpush if the helper is missing.
        """
        if not users:
            return
        public, private = self._ensure_vapid_keys()
        if not public or not private:
            return

        ICP = self.env['ir.config_parameter'].sudo()
        subject = ICP.get_param(VAPID_SUBJECT) or 'mailto:leave-pwa@aboghaliaoffice.com'
        payload = json.dumps({
            'title': title or 'SJC Leaves',
            'body': body or '',
            'data': data or {},
            'url': (data or {}).get('url') or '/leave',
        })
        subs = self.sudo().search([
            ('user_id', 'in', users.ids),
            ('active', '=', True),
        ])
        if not subs:
            return

        helper = '/opt/leave-pwa-push-venv/bin/leave_webpush_send.py'
        helper_python = '/opt/leave-pwa-push-venv/bin/python'
        use_helper = os.path.isfile(helper) and os.path.isfile(helper_python)

        inproc_webpush = None
        if not use_helper:
            try:
                from pywebpush import webpush as inproc_webpush
            except ImportError:
                _logger.info('pywebpush helper/venv missing; skipping Web Push (FCM may still send)')
                return

        for sub in subs:
            subscription_info = {
                'endpoint': sub.endpoint,
                'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
            }
            try:
                if use_helper:
                    import subprocess
                    msg = {
                        'subscription': subscription_info,
                        'data': payload,
                        'vapid_private_key': private,
                        'vapid_claims': {'sub': subject},
                    }
                    proc = subprocess.run(
                        [helper_python, helper],
                        input=json.dumps(msg).encode(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=20,
                        check=False,
                    )
                    result = {}
                    try:
                        result = json.loads(proc.stdout.decode() or '{}')
                    except Exception:
                        result = {'ok': False, 'error': proc.stderr.decode() or proc.stdout.decode()}
                    if not result.get('ok'):
                        err = result.get('error') or 'webpush failed'
                        status = result.get('response')
                        if status in (404, 410) or '410' in str(err) or 'Gone' in str(err):
                            sub.write({'active': False})
                        else:
                            _logger.warning('Web Push failed for user %s: %s', sub.user_id.id, err)
                else:
                    inproc_webpush(
                        subscription_info=subscription_info,
                        data=payload,
                        vapid_private_key=private,
                        vapid_claims={'sub': subject},
                    )
            except Exception as err:
                msg = str(err)
                if '410' in msg or '404' in msg or 'Gone' in msg:
                    sub.write({'active': False})
                else:
                    _logger.warning('Web Push failed for user %s: %s', sub.user_id.id, err)

    @api.model
    def notify_users(self, users, title, body, data=None):
        """FCM (attendance app) + Web Push (PWA) for the same event."""
        users = users.exists() if users else self.env['res.users']
        if not users:
            return

        # Web Push (HTTPS + pywebpush)
        try:
            self.send_to_users(users, title, body, data=data)
        except Exception:
            _logger.exception('leave PWA web push failed')

        # FCM via existing mobile attendance helper
        Emp = self.env['hr.employee'].sudo()
        try:
            for user in users:
                employees = Emp.search([('user_id', '=', user.id)])
                for emp in employees:
                    if hasattr(emp, 'send_notification_to_user'):
                        try:
                            emp.send_notification_to_user(
                                emp,
                                title,
                                body,
                                data={k: str(v) for k, v in (data or {}).items()},
                            )
                        except Exception:
                            _logger.exception('FCM leave notify failed for employee %s', emp.id)
        except Exception:
            _logger.exception('FCM leave notify batch failed')
