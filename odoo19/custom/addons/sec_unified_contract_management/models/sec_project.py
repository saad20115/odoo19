# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SecUnifiedProject(models.Model):
    _name = 'sec.unified.project'
    _description = 'مشروع العقد الموحد الرئيسي (شركة الكهرباء)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='اسم المشروع / العقد', required=True, tracking=True)
    code = fields.Char(string='كود المشروع', copy=False, readonly=True, default=lambda self: self.env['ir.sequence'].next_by_code('sec.unified.project') or '/')
    
    region = fields.Selection([
        ('makkah', 'منطقة مكة المكرمة'),
        ('madinah', 'منطقة المدينة المنورة'),
        ('jeddah', 'محافظة جدة'),
        ('taif', 'محافظة الطائف'),
        ('riyadh', 'منطقة الرياض'),
        ('eastern', 'المنطقة الشرقية'),
        ('southern', 'المنطقة الجنوبية'),
        ('northern', 'المنطقة الشمالية'),
        ('other', 'أخرى'),
    ], string='المنطقة / الفرع', required=True, default='makkah', tracking=True)

    sec_contract_number = fields.Char(string='رقم العقد الرئيسي مع شركة الكهرباء', tracking=True)
    manager_id = fields.Many2one('res.users', string='مدير المشروع العام', default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one('res.company', string='الشركة', default=lambda self: self.env.company, required=True)
    
    date_start = fields.Date(string='تاريخ بدء العقد', tracking=True)
    date_end = fields.Date(string='تاريخ نهاية العقد', tracking=True)
    contract_value = fields.Float(string='القيمة الإجمالية للعقد (ر.س)', tracking=True)
    
    state = fields.Selection([
        ('draft', 'مسودة / جديد'),
        ('running', 'ساري / قيد التنفيذ'),
        ('closed', 'مغلق ومنتهي'),
    ], string='حالة العقد', default='running', tracking=True)

    work_order_ids = fields.One2many('sec.work.order', 'project_id', string='أوامر العمل التابعة')
    work_order_count = fields.Integer(string='عدد أوامر العمل', compute='_compute_work_order_count')
    active = fields.Boolean(default=True)
    notes = fields.Html(string='ملاحظات وشروط العقد')

    @api.depends('work_order_ids')
    def _compute_work_order_count(self):
        for rec in self:
            rec.work_order_count = len(rec.work_order_ids)

    def action_view_work_orders(self):
        self.ensure_one()
        return {
            'name': f'أوامر العمل - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'sec.work.order',
            'view_mode': 'tree,kanban,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
