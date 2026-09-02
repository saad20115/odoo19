# -*- coding: utf-8 -*-
from odoo import api, fields, models


SENT_STATE_NAMES = (
    'تم الارسال',
    'تم الإرسال',
    'تم ارسال',
    'ارسال',
    'إرسال',
)


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    sjc_due_date = fields.Date(
        string='SJC Due Date',
        tracking=True,
        help='Dashboard overdue date for Expenses. Late when today is after this date plus grace days.',
    )
    sjc_sent_to_manager_by_id = fields.Many2one(
        'res.users',
        string='Sent to Manager By',
        index=True,
        copy=False,
        readonly=True,
        help='User who set الحالة to تم الارسال (sent to manager).',
    )

    def _sjc_is_sent_state(self, state_rec):
        if not state_rec:
            return False
        name = (state_rec.name or '').strip()
        return any(token in name for token in SENT_STATE_NAMES)

    def write(self, vals):
        res = super().write(vals)
        track_keys = set(vals) & {'x_state', 'sheet_id'}
        if track_keys and 'sjc_sent_to_manager_by_id' in self._fields:
            for expense in self:
                if expense.sjc_sent_to_manager_by_id:
                    continue
                sent_state = (
                    'x_state' in self._fields and expense._sjc_is_sent_state(expense.x_state)
                )
                has_manager = bool(expense.sheet_id) or bool(expense.manager)
                if sent_state or has_manager:
                    expense.sjc_sent_to_manager_by_id = self.env.user.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if 'sjc_sent_to_manager_by_id' in self._fields:
            for expense in records:
                sent_state = (
                    'x_state' in self._fields and expense._sjc_is_sent_state(expense.x_state)
                )
                has_manager = bool(expense.sheet_id) or bool(expense.manager)
                if sent_state or has_manager:
                    expense.sjc_sent_to_manager_by_id = self.env.user.id
        return records
