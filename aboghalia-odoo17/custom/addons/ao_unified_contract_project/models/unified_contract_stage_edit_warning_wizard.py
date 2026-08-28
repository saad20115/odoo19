# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UnifiedContractStageEditWarningWizard(models.TransientModel):
    _name = 'unified.contract.stage.edit.warning.wizard'
    _description = 'معالج تنبيه تحرير مرحلة مكتملة'

    work_order_id = fields.Many2one(
        'unified.contract.work.order',
        string='أمر العمل',
        required=True,
        ondelete='cascade'
    )
    stage_number = fields.Integer(
        string='رقم المرحلة',
        required=True
    )
    stage_name = fields.Char(
        string='اسم المرحلة',
        required=True
    )
    warning_message = fields.Text(
        string='رسالة التنبيه'
    )

    def action_preview_read_only(self):
        self.ensure_one()
        order = self.work_order_id
        num = self.stage_number
        
        vals = {}
        if num == 1:
            vals = {'show_stage_1_details': True, 'stage_1_unlocked_for_edit': False}
        elif num == 2:
            vals = {'show_stage_2_details': True, 'stage_2_unlocked_for_edit': False}
        elif num == 3:
            vals = {'show_stage_3_details': True, 'stage_3_unlocked_for_edit': False}
        elif num == 4:
            vals = {'show_stage_4_details': True, 'stage_4_unlocked_for_edit': False}
        elif num == 5:
            vals = {'show_stage_5_details': True, 'stage_5_unlocked_for_edit': False}

        order.with_context(skip_stage_permission_check=True).write(vals)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_confirm_unlock_for_edit(self):
        self.ensure_one()
        order = self.work_order_id
        num = self.stage_number
        
        vals = {}
        if num == 1:
            vals = {'show_stage_1_details': True, 'stage_1_unlocked_for_edit': True}
        elif num == 2:
            vals = {'show_stage_2_details': True, 'stage_2_unlocked_for_edit': True}
        elif num == 3:
            vals = {'show_stage_3_details': True, 'stage_3_unlocked_for_edit': True}
        elif num == 4:
            vals = {'show_stage_4_details': True, 'stage_4_unlocked_for_edit': True}
        elif num == 5:
            vals = {'show_stage_5_details': True, 'stage_5_unlocked_for_edit': True}

        order.with_context(skip_stage_permission_check=True).write(vals)
        order.message_post(body=_('⚠️ قام الموظف <b>%s</b> بفتح مرحلة <b>(%s)</b> المكتملة وإتاحتها للتحرير والتعديل.') % (self.env.user.name, self.stage_name))
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
