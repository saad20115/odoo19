# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

{
    "name": "Expense Dynamic Approval",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Accounting",
    "summary": "Customizable Expense Approvals Real-time Expense Review Automated Expense Validation Workflow-based Expense Authorization Multi-level Expense Approval Expense Policy Compliance Flexible Expense Approval Rules Expense Manager Role Dynamic Expense Approval Expense Approval Process Expenses Approval Process Dynamic Expense Approval Dynamic Expenses Approval Expense Multi Approval Expense Multiple Approval Expense Double Approval User Wise Approval Group Wise Approval Odoo",
    "description": """This module allows you to set dynamic and multi-level approvals in the employee expense so each expense can be approved by many levels. Expense is approved by particular users or groups they get emails notification about the expense that waiting for approval. When the expense approves or rejects employee gets a notification about it.""",
    "version": "0.0.1",
    "depends": ["hr_expense", "bus", "sh_base_dynamic_approval"],
    "data": [
        'security/ir.model.access.csv',
        'data/mail_data.xml',
        'wizard/sh_reject_reason_wizard.xml',
        'views/sh_expense_approval_line_views.xml',
        'views/sh_expense_approval_config_views.xml',
        'views/sh_approval_info_views.xml',
        'views/hr_expense_sheet_views.xml',
    ],
    "license": "OPL-1",
    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "application": True,
    "price": 30,
    "currency": "EUR"
}
