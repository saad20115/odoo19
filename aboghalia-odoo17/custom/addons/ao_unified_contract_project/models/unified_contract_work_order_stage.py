# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UnifiedContractWorkOrderStage(models.Model):
    _name = 'unified.contract.work.order.stage'
    _description = 'مرحلة أمر العمل'
    _order = 'sequence, id'

    name = fields.Char(string='اسم المرحلة', required=True, translate=True)
    sequence = fields.Integer(string='التسلسل', default=10)
    stage_progress = fields.Float(
        string='نسبة الإنجاز المستحقة (%)',
        default=0.0,
        help='نسبة الإنجاز التراكمية التي يتم تعيينها لأمر العمل تلقائياً عند التواجد أو الوصول لهذه المرحلة'
    )
    fold = fields.Boolean(
        string='مطوي في كانبان',
        help='علامة تحدد ما إذا كانت القائمة مطوية تلقائياً في شاشة الكانبان'
    )
    active = fields.Boolean(string='نشط', default=True)

    def write(self, vals):
        res = super().write(vals)
        if 'stage_progress' in vals or 'sequence' in vals or 'name' in vals:
            work_orders = self.env['unified.contract.work.order'].sudo().search([])
            work_orders._compute_overall_progress()
        return res
