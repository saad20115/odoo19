# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SjcPoInstructionWizard(models.TransientModel):
    _name = 'sjc.po.instruction.wizard'
    _description = 'Send Instructions to Employees'

    followup_model = fields.Char(required=True)
    followup_id = fields.Integer(required=True)
    po_number = fields.Char(string='Reference', readonly=True)
    display_name_po = fields.Char(string='Record', readonly=True)
    user_ids = fields.Many2many(
        'res.users',
        'sjc_po_instruction_wizard_user_rel',
        'wizard_id',
        'user_id',
        string='Employees',
        required=True,
        domain="[('share', '=', False), ('active', '=', True)]",
    )
    message = fields.Html(
        string='Instructions',
        required=True,
        sanitize_style=True,
    )

    def _record_label(self):
        if self.followup_model == 'employee.request':
            return _('Transaction Number')
        if self.followup_model == 'hr.expense':
            return _('Expense')
        return _('PO Number')

    def _default_intro(self):
        if self.env.context.get('default_followup_model') == 'employee.request':
            return _('Please follow the instructions below for this request')
        return _('Please follow the instructions below for this PO')

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        model = self.env.context.get('default_followup_model')
        res_id = self.env.context.get('default_followup_id')
        if model and res_id and model in self.env:
            record = self.env[model].browse(int(res_id)).exists()
            if record:
                defaults['followup_model'] = model
                defaults['followup_id'] = record.id
                if model == 'employee.request':
                    ref = getattr(record, 'serial_number', False) or record.display_name
                elif model == 'hr.expense':
                    ref = record.display_name
                else:
                    ref = getattr(record, 'po_number', False) or record.display_name
                defaults['po_number'] = ref
                defaults['display_name_po'] = record.display_name
                if 'message' in fields_list and not defaults.get('message'):
                    if model == 'employee.request':
                        label = _('Transaction Number')
                        intro = _('Please follow the instructions below for this request')
                    elif model == 'hr.expense':
                        label = _('Expense')
                        intro = _('Please follow the instructions below for this expense')
                    else:
                        label = _('PO Number')
                        intro = _('Please follow the instructions below for this PO')
                    defaults['message'] = Markup(
                        '<p>%s</p><p><strong>%s:</strong> %s</p>'
                    ) % (intro, label, defaults['po_number'])
        return defaults

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

    def action_send(self):
        self.ensure_one()
        if not self.user_ids:
            raise UserError(_('Please select at least one employee.'))
        if not self.message or not str(self.message).strip():
            raise UserError(_('Please write the instructions before sending.'))
        if self.followup_model not in self.env:
            raise UserError(_('Invalid record model.'))

        record = self.env[self.followup_model].browse(self.followup_id).exists()
        if not record:
            raise UserError(_('Record was not found.'))

        ref_label = self._record_label()
        po_label = self.po_number or record.display_name
        record_url = '%s/web#id=%s&model=%s&view_type=form' % (
            record.get_base_url(),
            record.id,
            self.followup_model,
        )
        body = Markup(
            '%(message)s'
            '<hr/>'
            '<p><strong>%(po_label)s:</strong> %(po)s</p>'
            '<p><a href="%(url)s">%(open_label)s</a></p>'
            '<p><em>%(from_label)s: %(sender)s</em></p>'
        ) % {
            'message': self.message,
            'po_label': ref_label,
            'po': po_label,
            'url': record_url,
            'open_label': _('Open record'),
            'from_label': _('From'),
            'sender': self.env.user.name,
        }

        for user in self.user_ids:
            self._send_odoobot_message(user, body)
            if user.partner_id and hasattr(record, 'message_subscribe'):
                record.message_subscribe(partner_ids=user.partner_id.ids)

        if hasattr(record, 'message_post'):
            record.message_post(
                body=_(
                    'Instructions sent to: %(users)s',
                    users=', '.join(self.user_ids.mapped('name')),
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Instructions sent'),
                'message': _('Message sent to %s employee(s).') % len(self.user_ids),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
