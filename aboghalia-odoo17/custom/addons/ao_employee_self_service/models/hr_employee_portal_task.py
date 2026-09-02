# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HrEmployeePortalTask(models.Model):
    _name = 'hr.employee.portal.task'
    _description = 'Employee Portal Task'
    _order = 'priority desc, date_deadline asc, create_date desc'

    name = fields.Char(string='عنوان المهمة', required=True)
    description = fields.Text(string='تفاصيل المهمة')
    employee_id = fields.Many2one('hr.employee', string='منشئ المهمة', required=True, default=lambda self: self.env.user.employee_id)
    assigned_to_id = fields.Many2one('hr.employee', string='المسند إليه المهمة', default=lambda self: self.env.user.employee_id)
    task_type = fields.Selection([
        ('personal', 'مهمة شخصية'),
        ('team', 'مهمة فريق'),
    ], string='نوع المهمة', default='personal', required=True)
    priority = fields.Selection([
        ('0', 'منخفضة'),
        ('1', 'متوسطة'),
        ('2', 'عالية'),
        ('3', 'عاجلة جداً'),
    ], string='الأولوية', default='1')
    date_deadline = fields.Date(string='تاريخ الاستحقاق')
    state = fields.Selection([
        ('todo', 'قيد الانتظار'),
        ('in_progress', 'جاري العمل'),
        ('done', 'مكتملة'),
        ('cancel', 'ملغاة'),
    ], string='الحالة', default='todo', required=True, tracking=True)

    def action_set_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_set_done(self):
        self.write({'state': 'done'})

    def action_set_cancel(self):
        self.write({'state': 'cancel'})
