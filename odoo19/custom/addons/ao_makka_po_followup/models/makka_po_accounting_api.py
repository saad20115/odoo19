# -*- coding: utf-8 -*-
import base64
import json
import logging

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PoAccountingApi(models.AbstractModel):
    _name = 'makka.po.accounting.api'
    _description = 'Accounting Odoo API Client'

    @api.model
    def _get_settings(self):
        ICP = self.env['ir.config_parameter'].sudo()
        url = (ICP.get_param('ao_makka_po_followup.accounting_url') or '').rstrip('/')
        login = ICP.get_param('ao_makka_po_followup.accounting_login') or ''
        password = ICP.get_param('ao_makka_po_followup.accounting_password') or ''
        # Same Accounting system as Madinah PO Follow-up — reuse those creds if Makka is empty.
        if not url or not login or not password:
            url = url or (ICP.get_param('ao_po_followup.accounting_url') or '').rstrip('/')
            login = login or (ICP.get_param('ao_po_followup.accounting_login') or '')
            password = password or (ICP.get_param('ao_po_followup.accounting_password') or '')
        if not url or not login or not password:
            raise UserError(_(
                'Accounting API is not configured. '
                'Set URL, login and password under PO Follow-up Makka > Configuration > Settings '
                '(same values as PO Follow-up / Accounting Incoming API).'
            ))
        return url, login, password

    @api.model
    def _basic_auth_header(self, login, password):
        token = base64.b64encode(f'{login}:{password}'.encode()).decode()
        return {'Authorization': f'Basic {token}', 'Content-Type': 'application/json'}

    @api.model
    def create_draft_invoices(self, items):
        """POST items to Accounting; return parsed JSON body."""
        url, login, password = self._get_settings()
        endpoint = f'{url}/api/makka_unified_contract/invoices'
        headers = self._basic_auth_header(login, password)
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                data=json.dumps({'items': items}),
                timeout=120,
            )
        except requests.RequestException as exc:
            _logger.exception('Accounting API connection failed')
            raise UserError(_('Could not reach Accounting Odoo: %s') % exc) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise UserError(_(
                'Accounting API returned invalid JSON (HTTP %s).'
            ) % response.status_code) from exc

        if response.status_code >= 400 or payload.get('status') == 'error':
            message = payload.get('message') or response.text
            raise UserError(_('Accounting API error: %s') % message)
        return payload
