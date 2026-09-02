# -*- coding: utf-8 -*-
from odoo import fields, models


class MakkaPoOrder(models.Model):
    _inherit = 'makka.po.order'

    sjc_assigned_by_id = fields.Many2one(
        'res.users',
        string='Assigned By',
        index=True,
        copy=False,
        readonly=True,
        help='User who assigned this Makka PO Order (Assign to me / Assign to).',
    )

    def action_assign_to_me(self):
        res = super().action_assign_to_me()
        self.write({'sjc_assigned_by_id': self.env.user.id})
        return res


class MakkaPoOrderAssignWizard(models.TransientModel):
    _inherit = 'makka.po.order.assign.wizard'

    def action_assign(self):
        res = super().action_assign()
        if self.order_ids:
            self.order_ids.write({'sjc_assigned_by_id': self.env.user.id})
        return res
