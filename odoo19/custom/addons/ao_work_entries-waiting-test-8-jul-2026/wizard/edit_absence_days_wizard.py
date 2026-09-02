# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EditAbsenceDaysWizard(models.TransientModel):
    _name = 'edit.absence.days.wizard'
    _description = 'Edit Employees Absence Days Wizard'

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        'edit_absence_days_wizard_employee_rel',
        'wizard_id',
        'employee_id',
        string='Employees',
        required=True,
    )
    absence_days = fields.Integer(
        string='Update Absence Days',
        default=0,
        help='New total absence days value (zero is allowed)',
    )
    year = fields.Integer(
        string='Year',
        required=True,
    )
    month = fields.Integer(
        string='Month',
        required=True,
    )

    @api.onchange('department_id')
    def _onchange_department_id(self):
        self.employee_ids = False
        if self.department_id:
            return {
                'domain': {
                    'employee_ids': [('department_id', '=', self.department_id.id)],
                },
            }
        return {'domain': {'employee_ids': []}}

    def action_save(self):
        self.ensure_one()
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
                'total_absence_days',
                self.absence_days,
                mark_absence_manual=True,
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
            'Updated absence days to %(days)s for %(count)s employee(s).',
            days=self.absence_days,
            count=updated_count,
        )
        if errors:
            message = '%s\n%s' % (message, '\n'.join(errors))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Absence Days Updated'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
