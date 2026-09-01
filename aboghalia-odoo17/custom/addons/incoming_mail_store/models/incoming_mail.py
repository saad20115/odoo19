from email.utils import parseaddr

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class IncomingMail(models.Model):
    _name = 'incoming.mail'
    _description = 'Incoming Mail'
    _inherit = ['mail.thread']
    _order = 'received_date desc, id desc'

    name = fields.Char(string='Subject', required=True, tracking=True)
    email_from = fields.Char(string='From', tracking=True)
    email_to = fields.Char(string='To', tracking=True)
    email_cc = fields.Char(string='CC')
    received_date = fields.Datetime(string='Received On', default=fields.Datetime.now, tracking=True)
    fetchmail_server_id = fields.Many2one(
        'fetchmail.server',
        string='Incoming Mail Server',
        readonly=True,
        tracking=True,
        ondelete='set null',
    )
    provider = fields.Selection(
        related='fetchmail_server_id.provider',
        string='Provider',
        store=True,
        readonly=True,
    )
    mailbox = fields.Char(
        related='fetchmail_server_id.user',
        string='Mailbox',
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ('new', 'New'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('archived', 'Archived'),
        ],
        string='Status',
        default='new',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    shared_user_ids = fields.Many2many(
        'res.users',
        'incoming_mail_shared_user_rel',
        'mail_id',
        'user_id',
        string='Shared With',
        help='Users outside the Incoming Mail group who can open only this email.',
    )

    @api.model
    def _is_incoming_mail_user(self, user=None):
        user = user or self.env.user
        return user.has_group('incoming_mail_store.group_incoming_mail_user')

    def _grant_shared_access(self, user):
        """Allow a non-inbox user to read/write only this incoming mail record."""
        self.ensure_one()
        if self._is_incoming_mail_user(user):
            return False
        if user not in self.shared_user_ids:
            self.write({'shared_user_ids': [(4, user.id)]})
        return True

    def _get_sender_email_address(self):
        self.ensure_one()
        if not self.email_from:
            return False
        _name, email_address = parseaddr(self.email_from)
        return email_address or self.email_from.strip()

    def _get_reply_subject(self):
        self.ensure_one()
        subject = (self.name or '').strip()
        if not subject:
            return _('Re: No Subject')
        if subject.lower().startswith('re:'):
            return subject
        return _('Re: %s') % subject

    def action_mark_done(self):
        self.write({'state': 'done'})
        return True

    def action_archive(self):
        self.write({'state': 'archived'})
        return True

    def action_reply(self):
        self.ensure_one()
        sender_email = self._get_sender_email_address()
        if not sender_email:
            raise UserError(_('This email has no sender address to reply to.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reply by Email'),
            'res_model': 'incoming.mail.reply.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_incoming_mail_id': self.id,
                'default_email_to': sender_email,
                'default_subject': self._get_reply_subject(),
            },
        }

    def action_assign_employee(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Notify via OdooBot'),
            'res_model': 'incoming.mail.assign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_incoming_mail_id': self.id,
            },
        }

    def action_open_fetch_date_range_wizard(self):
        servers = self.env['fetchmail.server'].search([
            ('object_id.model', '=', 'incoming.mail'),
            ('state', '=', 'done'),
        ])
        if not servers:
            raise UserError(_(
                'No confirmed incoming mail server is configured for Incoming Mail.\n\n'
                'Go to Settings → Technical → Incoming Mail Servers, open your server, '
                'set "Create a New Record" to Incoming Mail, then click Test & Confirm.'
            ))
        context = dict(self.env.context)
        if not self.env['incoming.mail'].search_count([]):
            context['fetchmail_force_choose_server'] = True
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fetch Date Range'),
            'res_model': 'fetchmail.fetch.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        custom_values = dict(custom_values or {})
        fetchmail_server_id = (
            custom_values.get('fetchmail_server_id')
            or self.env.context.get('default_fetchmail_server_id')
        )
        custom_values.update({
            'name': msg_dict.get('subject') or _('No Subject'),
            'email_from': msg_dict.get('email_from') or msg_dict.get('from'),
            'email_to': msg_dict.get('to'),
            'email_cc': msg_dict.get('cc'),
            'received_date': msg_dict.get('date') or fields.Datetime.now(),
            'fetchmail_server_id': fetchmail_server_id,
            'state': 'new',
        })
        return super().message_new(msg_dict, custom_values)

    def message_update(self, msg_dict, update_vals=None):
        update_vals = dict(update_vals or {})
        if not self.fetchmail_server_id:
            fetchmail_server_id = (
                update_vals.get('fetchmail_server_id')
                or self.env.context.get('default_fetchmail_server_id')
            )
            if fetchmail_server_id:
                update_vals['fetchmail_server_id'] = fetchmail_server_id
        return super().message_update(msg_dict, update_vals)
