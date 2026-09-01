# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Allow selecting a manager from another company (e.g. shared managers
    # whose user has the employee company in allowed companies).
    parent_id = fields.Many2one(check_company=False)
