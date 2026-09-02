# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models


class ApprovalInfo(models.Model):
    _inherit = 'sh.approval.info'
    _description = "Approval Information"

    hr_expense_sheet_id = fields.Many2one('hr.expense.sheet')
