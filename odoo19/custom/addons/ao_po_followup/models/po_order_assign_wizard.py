# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class PoOrderAssignWizard(models.TransientModel):
    _name = 'po.order.assign.wizard'
    _description = 'Assign PO Orders to User'

    order_ids = fields.Many2many(
        'po.order',
        string='PO Orders',
        required=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Assign To',
        required=True,
        domain="[('share', '=', False)]",
    )

    def action_assign(self):
        self.ensure_one()
        if not self.order_ids:
            raise UserError(_('Select at least one PO Order.'))
        if not self.user_id:
            raise UserError(_('Select a user to assign.'))

        partner = self.user_id.partner_id
        po_names = self.order_ids.mapped('name')
        self.order_ids.write({
            'user_id': self.user_id.id,
            'is_done': False,
        })
        for order in self.order_ids:
            order.message_subscribe(partner_ids=partner.ids)
            order.message_post(body=_(
                'Assigned to %(user)s by %(by)s.'
            ) % {
                'user': self.user_id.name,
                'by': self.env.user.name,
            })

        # One inbox/bell notification for the assignee covering all selected POs.
        self.order_ids[:1].message_notify(
            partner_ids=partner.ids,
            subject=_('PO Order assignment'),
            body=_(
                'You have been assigned to %(count)s PO Order(s): %(pos)s'
            ) % {
                'count': len(po_names),
                'pos': ', '.join(po_names),
            },
        )
        return {'type': 'ir.actions.act_window_close'}
