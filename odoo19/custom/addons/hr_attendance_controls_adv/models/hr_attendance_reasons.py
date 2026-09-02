from odoo import fields, models, api, _

class HrAttendanceReasons(models.Model):
    _name = "hr.attendance.reasons"
    _description = "Attendance Reasons"

    name = fields.Char(String='Reason',help='Reason Check in or Check out',required=True, index=True)    
    attendance_state = fields.Selection([
        ('checked_in', 'Checked in'),
        ('checked_out', 'Checked out')
        ],string="Attendance State", 
        help="Reasons will be filtered out based on the attendance state performed at check-in or check-out; leave empty if the action is unrelated.")

    _sql_constraints = [
        ('unique_name', 'UNIQUE(name)', 'Reason Name must be unique')
    ]