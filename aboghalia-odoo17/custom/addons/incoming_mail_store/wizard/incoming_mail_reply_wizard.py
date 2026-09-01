import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import formataddr

_PROVIDER_SMTP_PATTERNS = {
    'gmail': ('gmail.com', 'googlemail.com'),
    'zoho': ('zoho.com', 'zohomail.com'),
    'outlook': ('outlook.com', 'office365.com', 'hotmail.com', 'live.com'),
    'hostinger': ('hostinger.com', 'hostinger.', 'titan.email'),
}


class IncomingMailReplyWizard(models.TransientModel):
    _name = 'incoming.mail.reply.wizard'
    _description = 'Reply to Incoming Mail'

    incoming_mail_id = fields.Many2one(
        'incoming.mail',
        string='Incoming Mail',
        required=True,
        readonly=True,
    )
    mail_server_id = fields.Many2one(
        'ir.mail_server',
        string='Outgoing Mail Server',
        required=True,
        help='Choose which SMTP server will send this reply.',
    )
    email_from = fields.Char(
        string='From',
        compute='_compute_email_from',
        readonly=True,
        help='Sender address used for SMTP. It must match the selected outgoing server.',
    )
    email_to = fields.Char(string='To', required=True)
    subject = fields.Char(string='Subject', required=True)
    body = fields.Html(string='Message', required=True, sanitize_style=True)

    @api.model
    def _mail_server_for_provider(self, provider):
        patterns = _PROVIDER_SMTP_PATTERNS.get(provider, ())
        if not patterns:
            return self.env['ir.mail_server']
        for server in self.env['ir.mail_server'].sudo().search([]):
            hostname = (server.smtp_host or '').lower()
            if any(pattern in hostname for pattern in patterns):
                return server
        return self.env['ir.mail_server']

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        incoming_mail = self.env['incoming.mail'].browse(
            self.env.context.get('default_incoming_mail_id')
        )
        if 'mail_server_id' in fields_list and not defaults.get('mail_server_id'):
            mail_server = self._mail_server_for_provider(incoming_mail.provider)
            if not mail_server:
                mail_server = self.env['ir.mail_server'].sudo().search([], order='sequence', limit=1)
            defaults['mail_server_id'] = mail_server.id
        return defaults

    @api.depends('mail_server_id', 'mail_server_id.smtp_user', 'incoming_mail_id.mailbox')
    def _compute_email_from(self):
        for wizard in self:
            wizard.email_from = wizard._prepare_email_from()

    def _prepare_email_from(self):
        self.ensure_one()
        smtp_user = (self.mail_server_id.smtp_user or '').strip()
        if not smtp_user or smtp_user.startswith('@'):
            return False
        sender_name = self.incoming_mail_id.mailbox or self.env.user.name
        return formataddr((sender_name, smtp_user))

    def _get_original_message_id(self):
        self.ensure_one()
        original_message = self.env['mail.message'].search([
            ('model', '=', 'incoming.mail'),
            ('res_id', '=', self.incoming_mail_id.id),
            ('message_type', '=', 'email'),
        ], order='id asc', limit=1)
        return original_message.message_id if original_message else False

    def action_send_reply(self):
        self.ensure_one()
        if not self.body or not self.body.strip():
            raise UserError(_('Please write a reply message before sending.'))
        if not self.mail_server_id:
            raise UserError(_('Please choose an outgoing mail server.'))

        email_from = self._prepare_email_from()
        if not email_from:
            raise UserError(_(
                'The outgoing mail server "%(server)s" has no valid sender address. '
                'Please set a full email address in the SMTP username field.',
                server=self.mail_server_id.display_name,
            ))

        incoming_mail = self.incoming_mail_id
        original_message_id = self._get_original_message_id()
        mail_values = {
            'subject': self.subject,
            'email_from': email_from,
            'email_to': self.email_to,
            'body_html': self.body,
            'model': 'incoming.mail',
            'res_id': incoming_mail.id,
            'author_id': self.env.user.partner_id.id,
            'reply_to': email_from,
            'mail_server_id': self.mail_server_id.id,
        }
        if original_message_id:
            mail_values.update({
                'references': original_message_id,
                'headers': json.dumps({'In-Reply-To': original_message_id}),
            })

        outgoing_mail = self.env['mail.mail'].sudo().create(mail_values)
        outgoing_mail.send()

        chatter_body = _(
            '<p><strong>Reply sent to %(email)s</strong></p>'
            '<p><em>Via outgoing server: %(server)s</em></p>%(body)s',
            email=self.email_to,
            server=self.mail_server_id.display_name,
            body=self.body,
        )
        if outgoing_mail.state == 'sent':
            incoming_mail.message_post(
                body=chatter_body,
                subject=self.subject,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            if incoming_mail.state == 'new':
                incoming_mail.state = 'in_progress'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Reply sent'),
                    'message': _('Your reply was sent to %s.', self.email_to),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }

        failure_reason = outgoing_mail.failure_reason or _('Unknown delivery error.')
        incoming_mail.message_post(
            body=_(
                '<p><strong>Reply failed to %(email)s</strong></p>'
                '<p><em>Via outgoing server: %(server)s</em></p>'
                '<p><em>%(reason)s</em></p>%(body)s',
                email=self.email_to,
                server=self.mail_server_id.display_name,
                reason=failure_reason,
                body=self.body,
            ),
            subject=self.subject,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        if incoming_mail.state == 'new':
            incoming_mail.state = 'in_progress'
        raise UserError(_(
            'The reply could not be sent.\n\n%s\n\n'
            'Please check your outgoing mail server configuration.',
            failure_reason,
        ))
