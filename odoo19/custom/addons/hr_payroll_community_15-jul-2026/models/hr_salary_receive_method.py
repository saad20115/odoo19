# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrSalaryReceiveMethod(models.Model):
    _name = 'hr.salary.receive.method'
    _description = 'Salary Receive Method'

    name = fields.Char(string='Name', required=True, translate=True)
    note = fields.Text(string='Note')
    employee_ids = fields.One2many(
        'hr.employee',
        'salary_receive_method_id',
        string='Employees',
    )
    # UI field for editable list with many2many_tags; syncs to employee Many2one
    employee_ids_m2m = fields.Many2many(
        'hr.employee',
        compute='_compute_employee_ids_m2m',
        inverse='_inverse_employee_ids_m2m',
        string='Employees',
    )

    @api.depends('employee_ids')
    def _compute_employee_ids_m2m(self):
        for method in self:
            method.employee_ids_m2m = method.employee_ids

    def _inverse_employee_ids_m2m(self):
        for method in self:
            selected = method.employee_ids_m2m
            previous = method.employee_ids
            to_add = selected - previous
            to_remove = previous - selected
            if to_add:
                to_add.write({'salary_receive_method_id': method.id})
            if to_remove:
                to_remove.write({'salary_receive_method_id': False})
