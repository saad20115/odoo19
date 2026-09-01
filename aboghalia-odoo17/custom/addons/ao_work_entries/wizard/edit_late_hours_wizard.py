# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EditLateHoursWizard(models.TransientModel):
    _name = 'edit.late.hours.wizard'
    _description = 'Edit Employees Late Hours Wizard'

    department_ids = fields.Many2many(
        'hr.department',
        'edit_late_hours_wizard_department_rel',
        'wizard_id',
        'department_id',
        string='Departments',
        required=True,
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        'edit_late_hours_wizard_employee_rel',
        'wizard_id',
        'employee_id',
        string='Employees',
        required=True,
    )
    late_hours = fields.Float(
        string='Update Late Hours',
        default=0.0,
        digits=(16, 2),
        help='New total late hours value (zero is allowed)',
    )
    year = fields.Integer(
        string='Year',
        required=True,
    )
    month = fields.Integer(
        string='Month',
        required=True,
    )

    @api.onchange('department_ids')
    def _onchange_department_ids(self):
        self.employee_ids = False
        if self.department_ids:
            return {
                'domain': {
                    'employee_ids': [('department_id', 'in', self.department_ids.ids)],
                },
            }
        return {'domain': {'employee_ids': []}}

    def action_save(self):
        self.ensure_one()
        if not self.department_ids:
            raise UserError(_('Please select at least one department.'))
        if not self.employee_ids:
            raise UserError(_('Please select at least one employee.'))

        grid = self.env['hr.employee.attendance.grid']
        updated_count = 0
        errors = []

        for employee in self.employee_ids:
            result = grid.update_employee_monthly_summary(
                employee.id,
                self.year,
                self.month,
                'total_late_hours',
                self.late_hours,
                mark_late_manual=True,
            )
            if result.get('success'):
                updated_count += 1
            else:
                errors.append(
                    _('%(employee)s: %(message)s', employee=employee.name, message=result.get('message', _('Update failed')))
                )

        if not updated_count:
            raise UserError(
                _('No employees were updated.\n%s') % '\n'.join(errors)
            )

        message = _(
            'Updated late hours to %(hours)s for %(count)s employee(s).',
            hours=self.late_hours,
            count=updated_count,
        )
        if errors:
            message = '%s\n%s' % (message, '\n'.join(errors))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Late Hours Updated'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
