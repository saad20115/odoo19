# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class UnifiedContractSkipExecutionWizard(models.TransientModel):
    _name = 'unified.contract.skip.execution.wizard'
    _description = 'معالج تنبيه وتجاوز عدم اكتمال مرحلة التنفيذ'

    work_order_id = fields.Many2one(
        'unified.contract.work.order',
        string='أمر العمل',
        required=True
    )
    target_stage_id = fields.Many2one(
        'unified.contract.work.order.stage',
        string='المرحلة المستهدفة'
    )
    target_stage_name = fields.Char(
        string='المرحلة التالية'
    )
    execution_progress = fields.Float(
        string='نسبة إنجاز التنفيذ الحالية'
    )
    warning_message = fields.Char(
        string='رسالة التحذير'
    )

    def action_confirm_skip(self):
        self.ensure_one()
        order = self.work_order_id
        current_seq = order.stage_id.sequence if order.stage_id else 0

        # Search explicitly for stage with 'إغلاق' or next stage in sequence
        closure_stage = self.env['unified.contract.work.order.stage'].search([
            '|', ('name', 'ilike', 'إغلاق'), ('sequence', '>', current_seq)
        ], order='sequence asc', limit=1)

        if not closure_stage:
            raise UserError(_('عذراً، لا توجد مرحلة تالية للانتقال إليها.'))

        order.with_context(skip_execution_check=True).write({
            'is_execution_skipped': True,
            'stage_id': closure_stage.id,
        })
        order.message_post(
            body=f"⚠️ <b>تم تجاوز وتخطي مرحلة التنفيذ</b> والانتقال إلى مرحلة <b>({closure_stage.name})</b> بواسطة الموظف <b>{self.env.user.name}</b>."
        )
        return {'type': 'ir.actions.act_window_close'}
