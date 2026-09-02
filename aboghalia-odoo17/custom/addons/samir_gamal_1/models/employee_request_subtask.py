from odoo import models, fields, api
from odoo.exceptions import ValidationError

class EmployeeRequestSubtask(models.Model):
    _name = 'employee.request.subtask'
    _description = 'Employee Request Subtask'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    request_id = fields.Many2one('employee.request', string="المعاملة الأساسية", ondelete='cascade', required=True)
    department_id = fields.Many2one('hr.department', string="القسم المختص", required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string="الموظف المعني", required=True, tracking=True)
    
    name = fields.Char(string="المهمة المطلوبة / تعليمات العمل", required=True, tracking=True)
    due_date = fields.Date(string="تاريخ الاستحقاق", required=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'قيد الانتظار'),
        ('in_progress', 'جاري العمل'),
        ('done', 'مكتملة'),
        ('cancel', 'ملغاة')
    ], string="الحالة", default='draft', tracking=True)
    
    notes = fields.Html(string="ملاحظات والتفاصيل")
    
    # Related fields from the main request for summary display
    request_topic = fields.Text(related='request_id.request_topic', string="موضوع المعاملة", readonly=True)
    request_serial = fields.Char(related='request_id.serial_number', string="رقم المعاملة", readonly=True)
    
    @api.constrains('due_date', 'request_id')
    def _check_due_date(self):
        for rec in self:
            if rec.due_date and rec.request_id:
                if rec.request_id.start_date and rec.due_date < rec.request_id.start_date:
                    raise ValidationError("تاريخ استحقاق المهمة الفرعية لا يمكن أن يكون قبل تاريخ بداية المعاملة الأصلية.")
                if rec.request_id.end_date and rec.due_date > rec.request_id.end_date:
                    raise ValidationError("تاريخ استحقاق المهمة الفرعية يجب أن لا يتجاوز تاريخ الاستحقاق الكلي للمعاملة الأصلية.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super(EmployeeRequestSubtask, self).create(vals_list)
        for record in records:
            if record.employee_id and record.employee_id.user_id:
                # Schedule an activity for the assigned user on the MAIN transaction so they can view the whole context
                record.request_id.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=record.employee_id.user_id.id,
                    date_deadline=record.due_date,
                    summary=f"مهمة فرعية جديدة: {record.name}",
                    note=f"تم توجيه مهمة فرعية إليك مرتبطة بالمعاملة رقم {record.request_id.serial_number}. القسم: {record.department_id.name}"
                )
        return records

    def write(self, vals):
        # Monitor changes in assignment
        res = super(EmployeeRequestSubtask, self).write(vals)
        for record in self:
            if 'employee_id' in vals and record.employee_id and record.employee_id.user_id:
                record.request_id.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=record.employee_id.user_id.id,
                    date_deadline=record.due_date,
                    summary=f"تم تحويل المهمة الفرعية إليك: {record.name}",
                    note=f"تم توجيه مهمة فرعية إليك مرتبطة بالمعاملة رقم {record.request_id.serial_number}."
                )
        return res
