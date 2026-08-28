# -*- coding: utf-8 -*-

from odoo import models, fields, api

class UnifiedContractStage(models.Model):
    _name = 'unified.contract.stage'
    _description = 'مرحلة مشروع العقد الموحد'
    _order = 'sequence, id'

    name = fields.Char(string='اسم المرحلة', required=True, translate=True)
    sequence = fields.Integer(string='التسلسل', default=10)
    stage_progress = fields.Float(
        string='نسبة الإنجاز المستحقة (%)',
        default=0.0,
        help='نسبة الإنجاز التراكمية التي يتم تعيينها للمشروع تلقائياً عند الوصول لهذه المرحلة'
    )
    fold = fields.Boolean(
        string='مطوي في كانبان',
        help='علامة تحدد ما إذا كانت القائمة مطوية تلقائياً في شاشة الكانبان'
    )
    active = fields.Boolean(string='نشط', default=True)
