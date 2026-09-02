from odoo import models, fields, api
from datetime import datetime

class CTSRoutingAssignment(models.Model):
    _name = 'cts.routing.assignment'
    _description = 'CTS Routing & Assignment'
    _rec_name = 'transaction_id'

    transaction_id = fields.Many2one('employee.request', string="المعاملة", required=True, ondelete='cascade')
    assigned_from = fields.Many2one('res.users', string="محالة من", required=True, default=lambda self: self.env.user)
    assigned_to_user = fields.Many2one('res.users', string="محالة إلى (موظف)")
    assigned_to_department = fields.Many2one('hr.department', string="محالة إلى (قسم)")
    
    assignment_date = fields.Datetime(string="تاريخ الإحالة", default=fields.Datetime.now, required=True)
    due_date = fields.Datetime(string="تاريخ الاستحقاق")
    
    action_required = fields.Selection([
        ('review', 'للمراجعة'),
        ('approve', 'للاعتماد'),
        ('reply', 'للرد'),
        ('info', 'للعلم'),
    ], string="الإجراء المطلوب", required=True)
    
    notes = fields.Text(string="ملاحظات / توجيهات")
    
    status = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('completed', 'مكتمل'),
        ('rejected', 'مرفوض'),
    ], string="حالة الإحالة", default='pending')
    
    completion_date = fields.Datetime(string="تاريخ الإنجاز")
    completion_notes = fields.Text(string="ملاحظات الإنجاز")

    def action_complete(self):
        for rec in self:
            rec.status = 'completed'
            rec.completion_date = fields.Datetime.now()
            
    def action_reject(self):
        for rec in self:
            rec.status = 'rejected'
            rec.completion_date = fields.Datetime.now()
