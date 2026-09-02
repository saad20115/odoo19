# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AttendanceReportWizard(models.TransientModel):
    _name = 'attendance.report.wizard'
    _description = 'Attendance Summary Report Wizard'

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        help='Filter employees by department. Ignored when Print All is enabled.',
    )
    date_from = fields.Date(
        string='From',
        required=True,
        default=fields.Date.context_today,
    )
    date_to = fields.Date(
        string='To',
        required=True,
        default=fields.Date.context_today,
    )
    print_all = fields.Boolean(
        string='Print All',
        help='Include all employees regardless of department.',
    )

    @api.onchange('print_all')
    def _onchange_print_all(self):
        if self.print_all:
            self.department_id = False

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_('The start date must be before or equal to the end date.'))

    def action_print(self):
        self.ensure_one()
        if not self.print_all and not self.department_id:
            raise UserError(_('Please select a department or enable Print All.'))
        return self.env['hr.employee.attendance.grid'].generate_attendance_summary_excel(
            self.date_from,
            self.date_to,
            self.department_id.id if self.department_id else False,
            self.print_all,
        )
