from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta

class HrAttendanceEditRequest(models.Model):
    _name = "hr.attendance.edit.request"
    _description = "Attendance Edit Request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'employee_id'


    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, default=lambda self: self.env.user.employee_id.id)
    attendance_id = fields.Many2one('hr.attendance', string="Attendance", required=True, domain="[('employee_id', '=', employee_id)]")
    date = fields.Datetime(related='attendance_id.check_in', string="Attendance Date", store=True)

    check_in_new = fields.Datetime(string="New Check In")
    check_out_new = fields.Datetime(string="New Check Out")

    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string="Status", default='pending', tracking=True)
    approved_by = fields.Many2one('hr.employee', string="Approved By", readonly=True, copy=False)

    def action_approve(self):
        for rec in self:
            if rec.attendance_id:
                rec.attendance_id.write({
                    'check_in': rec.check_in_new or rec.attendance_id.check_in,
                    'check_out': rec.check_out_new or rec.attendance_id.check_out,
                })
            approved_employee = self.env.user.employee_id
            if not approved_employee:
                raise UserError(_("The current user is not linked to an employee."))
            rec.write({
                'state': 'approved',
                'approved_by': approved_employee.id,
            })
    def action_reject(self):
        for rec in self:
            rec.state = 'rejected'
            rec.message_post(body=_("Attendance edit request rejected."))

    def _check_attendance_date_allowed(self, attendance):
        if not attendance:
            raise ValidationError(_("Attendance record not found."))

        attendance_date = attendance.check_in.date()
        today = date.today()
        yesterday = today - timedelta(days=1)

        is_admin_or_hr = self.env.user.has_group('base.group_system') or self.env.user.has_group('hr.group_hr_manager')

        if not is_admin_or_hr:
            if attendance_date not in (today, yesterday):
                raise ValidationError(_("You can only request an edit for today's or yesterday's attendance."))

    @api.model
    def create(self, vals):
        attendance = self.env['hr.attendance'].browse(vals.get('attendance_id'))
        self._check_attendance_date_allowed(attendance)
        return super(HrAttendanceEditRequest, self).create(vals)

    def write(self, vals):
        if 'attendance_id' in vals:
            new_attendance_id = vals['attendance_id']
            attendance = self.env['hr.attendance'].browse(new_attendance_id)
            self._check_attendance_date_allowed(attendance)
        return super(HrAttendanceEditRequest, self).write(vals)