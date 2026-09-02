# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ExpenseApprovalConfig(models.Model):
    _name = 'sh.expense.approval.config'
    _description = 'Expense Approval Configuration'

    name = fields.Char()
    min_amount = fields.Float(string="Minimum Amount", required=True)
    company_ids = fields.Many2many(
        'res.company', string="Allowed Companies", default=lambda self: self.env.company)
    is_boolean = fields.Boolean(string="Employee Always in CC")
    expense_approval_line = fields.One2many(
        'sh.expense.approval.line', 'expense_approval_config_id')

    @api.constrains('expense_approval_line')
    def approval_line_level(self):
        if self.expense_approval_line:
            levels = self.expense_approval_line.mapped('level')
            if len(levels) != len(set(levels)):
                raise ValidationError('Levels must be different!!!')
