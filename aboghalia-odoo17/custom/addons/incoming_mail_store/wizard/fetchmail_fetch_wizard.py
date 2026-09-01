from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class FetchmailFetchWizard(models.TransientModel):
    _name = 'fetchmail.fetch.wizard'
    _description = 'Fetch Emails by Date Range'

    fetchmail_server_id = fields.Many2one(
        'fetchmail.server',
        string='Incoming Mail Server',
        required=True,
        domain="[('object_id.model', '=', 'incoming.mail'), ('state', '=', 'done')]",
    )
    date_from = fields.Date(
        string='From',
        required=True,
        default=fields.Date.context_today,
        help='Import emails received on or after this date (IMAP only).',
    )
    date_to = fields.Date(
        string='To',
        required=True,
        default=fields.Date.context_today,
        help='Import emails received on or before this date (IMAP only).',
    )

    @api.model
    def _incoming_mail_server_domain(self):
        return [
            ('object_id.model', '=', 'incoming.mail'),
            ('state', '=', 'done'),
        ]

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if self.env.context.get('fetchmail_force_choose_server'):
            return defaults
        if 'fetchmail_server_id' in fields_list and not defaults.get('fetchmail_server_id'):
            server = self.env['fetchmail.server'].search(
                self._incoming_mail_server_domain(),
                order='priority, id',
                limit=1,
            )
            defaults['fetchmail_server_id'] = server.id
        return defaults

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_('The start date must be before or equal to the end date.'))

    def action_fetch(self):
        self.ensure_one()
        server = self.fetchmail_server_id
        if not server:
            raise UserError(_('Please choose an incoming mail server.'))
        if server.object_id.model != 'incoming.mail':
            raise UserError(_(
                'The server "%(server)s" must have "Create a New Record" set to Incoming Mail.',
                server=server.display_name,
            ))

        if server.server_type == 'pop':
            server.sudo().fetch_mail()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Fetch started'),
                    'message': _(
                        'POP server "%(server)s" fetched unread emails from the mailbox. '
                        'Date range applies to IMAP servers only.',
                        server=server.display_name,
                    ),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }

        job = self.env['fetchmail.fetch.job'].create_from_wizard(
            server,
            self.date_from,
            self.date_to,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fetch started'),
                'message': _(
                    'Fetching %(total)d email(s) from %(date_from)s to %(date_to)s in the background. '
                    'You will be notified when it finishes.',
                    total=job.total_found,
                    date_from=self.date_from,
                    date_to=self.date_to,
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
