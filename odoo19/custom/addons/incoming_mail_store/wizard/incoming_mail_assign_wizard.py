from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class IncomingMailAssignWizard(models.TransientModel):
    _name = 'incoming.mail.assign.wizard'
    _description = 'Notify Employee via OdooBot'

    incoming_mail_id = fields.Many2one(
        'incoming.mail',
        string='Incoming Mail',
        required=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Recipient',
        required=True,
        domain=[('share', '=', False), ('active', '=', True)],
    )
    message = fields.Html(
        string='Message',
        required=True,
        sanitize_style=True,
        help='Message sent to the employee through OdooBot in Discuss.',
    )

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        incoming_mail = self.env['incoming.mail'].browse(
            self.env.context.get('default_incoming_mail_id')
        )
        if incoming_mail and 'message' in fields_list and not defaults.get('message'):
            defaults['message'] = self._default_bot_message(incoming_mail)
        return defaults

    @api.model
    def _default_bot_message(self, incoming_mail):
        record_url = '%s/web#id=%s&model=incoming.mail&view_type=form' % (
            incoming_mail.get_base_url(),
            incoming_mail.id,
        )
        return Markup(
            '<p>%(intro)s</p>'
            '<ul>'
            '<li><strong>%(subject_label)s:</strong> %(subject)s</li>'
            '<li><strong>%(from_label)s:</strong> %(email_from)s</li>'
            '<li><strong>%(received_label)s:</strong> %(received_date)s</li>'
            '</ul>'
            '<p><a href="%(record_url)s">%(open_label)s</a></p>'
        ) % {
            'intro': _('You have been assigned the following incoming email:'),
            'subject_label': _('Subject'),
            'subject': incoming_mail.name or _('No Subject'),
            'from_label': _('From'),
            'email_from': incoming_mail.email_from or '-',
            'received_label': _('Received On'),
            'received_date': incoming_mail.received_date or '-',
            'record_url': record_url,
            'open_label': _('Open Incoming Mail'),
        }

    def _send_odoobot_message(self, assignee, body):
        odoobot = self.env.ref('base.partner_root')
        channel = self.env['discuss.channel'].with_user(assignee).channel_get(
            [odoobot.id, assignee.partner_id.id],
            pin=False,
        )
        channel.sudo().with_context(mail_create_nosubscribe=True).message_post(
            body=body,
            author_id=odoobot.id,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

    def action_assign(self):
        self.ensure_one()
        if not self.message or not self.message.strip():
            raise UserError(_('Please write a message before sending.'))

        incoming_mail = self.incoming_mail_id
        assignee = self.user_id

        incoming_mail._grant_shared_access(assignee)
        if assignee.partner_id:
            incoming_mail.message_subscribe(partner_ids=assignee.partner_id.ids)
        self._send_odoobot_message(assignee, self.message)

        incoming_mail.message_post(
            body=_(
                'OdooBot notification sent to %(user)s.',
                user=assignee.display_name,
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        if incoming_mail.state == 'new':
            incoming_mail.state = 'in_progress'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notification sent'),
                'message': _('OdooBot sent a message to %s.', assignee.display_name),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
