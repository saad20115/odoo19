# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    leave_project_manager_id = fields.Many2one(
        'hr.employee',
        string='Project Manager',
        tracking=True,
        help='Employee who approves this person\'s time off at the Project Manager level. '
             'They are added to the Leave Project Manager group if they are not already in it.',
    )

    def _ensure_leave_project_manager_group(self):
        group = self.env.ref(
            'ao_leave_approval.group_leave_project_manager',
            raise_if_not_found=False,
        )
        if not group:
            return
        for employee in self:
            pm = employee.leave_project_manager_id
            if not pm:
                continue
            if not pm.user_id:
                raise UserError(_(
                    'Project Manager %(name)s has no related user. '
                    'Link a user on that employee first.',
                    name=pm.name,
                ))
            if group not in pm.user_id.sudo().groups_id:
                pm.user_id.sudo().write({'groups_id': [(4, group.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees.filtered('leave_project_manager_id')._ensure_leave_project_manager_group()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if 'leave_project_manager_id' in vals:
            self._ensure_leave_project_manager_group()
        return res
