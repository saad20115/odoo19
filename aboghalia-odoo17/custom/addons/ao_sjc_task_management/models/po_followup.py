# -*- coding: utf-8 -*-
from odoo import fields, models

YES_NO_SELECTION = [
    ('yes', 'تم'),
    ('no', 'لم يتم'),
]


class PoFollowup(models.Model):
    _inherit = 'po.followup'

    disbursement = fields.Selection(
        YES_NO_SELECTION,
        string='الصرف',
        default='no',
        tracking=True,
        help='تم الصرف → Completed on the SJC dashboard. Anything else → In Progress.',
    )
    sjc_due_date = fields.Date(
        string='SJC Due Date',
        tracking=True,
        help='Dashboard overdue date. Late when today is after this date plus grace days.',
    )
    sjc_sent_to_accounting_by_id = fields.Many2one(
        'res.users',
        string='Sent to Accounting By',
        index=True,
        copy=False,
        readonly=True,
    )

    def action_assign_to_accounting(self):
        drafts = self.filtered(lambda r: r.state == 'draft')
        res = super().action_assign_to_accounting()
        success = drafts.filtered(lambda r: r.state == 'assigned')
        if success:
            success.write({'sjc_sent_to_accounting_by_id': self.env.user.id})
        return res
