# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AttendanceReportWizard(models.TransientModel):
    _name = 'attendance.report.wizard'
    _description = 'Attendance Summary Report Wizard'

    department_ids = fields.Many2many(
        'hr.department',
        'attendance_report_wizard_department_rel',
        'wizard_id',
        'department_id',
        string='Departments',
        help='Filter employees by one or more departments. Ignored when Print All is enabled.',
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
            self.department_ids = False

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_('The start date must be before or equal to the end date.'))

    def action_print(self):
        self.ensure_one()
        if not self.print_all and not self.department_ids:
            raise UserError(_('Please select at least one department or enable Print All.'))
        return self.env['hr.employee.attendance.grid'].generate_attendance_summary_excel(
            self.date_from,
            self.date_to,
            self.department_ids.ids,
            self.print_all,
        )
