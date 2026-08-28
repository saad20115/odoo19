# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class UnifiedContractStageRevertWizard(models.TransientModel):
    _name = 'unified.contract.stage.revert.wizard'
    _description = 'معالج إرجاع المراحل للسابقة'

    res_model = fields.Char(
        string='اسم النموذج',
        required=True
    )
    res_id = fields.Integer(
        string='معرف السجل',
        required=True
    )
    stage_id = fields.Many2one(
        'unified.contract.work.order.stage',
        string='المرحلة السابقة المراد الإرجاع إليها (أمر العمل)',
        domain="[('id', 'in', context.get('previous_stage_ids', []))]"
    )
    project_stage_id = fields.Many2one(
        'unified.contract.stage',
        string='المرحلة السابقة المراد الإرجاع إليها (المشروع)',
        domain="[('id', 'in', context.get('previous_project_stage_ids', []))]"
    )
    reason = fields.Text(
        string='سبب الملاحظات والتوجيهات للإرجاع'
    )

    @api.model
    def default_get(self, fields_list):
        res = super(UnifiedContractStageRevertWizard, self).default_get(fields_list)
        res_model = res.get('res_model') or self.env.context.get('default_res_model')
        res_id = res.get('res_id') or self.env.context.get('default_res_id')
        
        if res_model == 'unified.contract.work.order' and res_id:
            order = self.env['unified.contract.work.order'].browse(res_id)
            current_seq = order.stage_id.sequence if order.stage_id else 9999
            prev_stages = self.env['unified.contract.work.order.stage'].search([
                ('sequence', '<', current_seq)
            ], order='sequence desc')
            if prev_stages and 'stage_id' in fields_list and not res.get('stage_id'):
                res['stage_id'] = prev_stages[0].id
        elif res_model == 'unified.contract.project' and res_id:
            project = self.env['unified.contract.project'].browse(res_id)
            current_seq = project.stage_id.sequence if project.stage_id else 9999
            prev_stages = self.env['unified.contract.stage'].search([
                ('sequence', '<', current_seq)
            ], order='sequence desc')
            if prev_stages and 'project_stage_id' in fields_list and not res.get('project_stage_id'):
                res['project_stage_id'] = prev_stages[0].id
        return res

    @api.onchange('res_id', 'res_model')
    def _onchange_res_id_filter_previous_stages(self):
        if self.res_model == 'unified.contract.work.order' and self.res_id:
            order = self.env['unified.contract.work.order'].browse(self.res_id)
            current_seq = order.stage_id.sequence if order.stage_id else 9999
            prev_stages = self.env['unified.contract.work.order.stage'].search([
                ('sequence', '<', current_seq)
            ])
            return {
                'domain': {
                    'stage_id': [('id', 'in', prev_stages.ids)]
                }
            }

    def action_confirm_revert(self):
        self.ensure_one()
        if self.res_model == 'unified.contract.work.order':
            order = self.env['unified.contract.work.order'].browse(self.res_id)
            if not self.stage_id:
                raise UserError(_('يرجى اختيار المرحلة السابقة المراد الإرجاع إليها.'))
            order.with_context(skip_stage_permission_check=True, skip_execution_check=True).write({
                'stage_id': self.stage_id.id,
                'is_execution_skipped': False,
            })
            if order.stage_id.sequence <= 3:
                order.is_execution_skipped = False
                if order.execution_progress >= 100.0:
                    order.execution_status = 'completed'
                elif order.execution_progress <= 0.0:
                    order.execution_status = 'not_started'
                else:
                    order.execution_status = 'in_progress'
            if order.is_first_stage:
                order.state = 'draft'
            order.message_post(body=f"تم إرجاع أمر العمل إلى مرحلة <b>({self.stage_id.name})</b> بواسطة {self.env.user.name}.<br/>السبب: {self.reason or 'بدون ملاحظات مدوّنة'}")
            
        elif self.res_model == 'unified.contract.project':
            project = self.env['unified.contract.project'].browse(self.res_id)
            if not self.project_stage_id:
                raise UserError(_('يرجى اختيار المرحلة السابقة المراد الإرجاع إليها.'))
            project.with_context(skip_stage_permission_check=True).write({'stage_id': self.project_stage_id.id})
            if project.is_first_stage:
                project.state = 'draft'
            project.message_post(body=f"تم إرجاع المشروع إلى مرحلة <b>({self.project_stage_id.name})</b> بواسطة {self.env.user.name}.<br/>السبب: {self.reason or 'بدون ملاحظات مدوّنة'}")
            
        return {'type': 'ir.actions.act_window_close'}
