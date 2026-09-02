# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sjc_grace_days = fields.Integer(
        string='Overdue Grace Days',
        config_parameter='ao_sjc_task_management.grace_days',
        default=10,
        help='A task is overdue when today is after the due date plus this many days, '
             'and the task is not completed.',
    )
    sjc_admin_due_field = fields.Selection(
        [
            ('end_date', 'End Date (تاريخ النهاية)'),
            ('start_date', 'Start Date (تاريخ البداية)'),
        ],
        string='Admin Comms Due Date Field',
        config_parameter='ao_sjc_task_management.admin_due_field',
        default='end_date',
        help='Which employee.request date field is used for Late calculation.',
    )
    sjc_expense_due_field = fields.Selection(
        [
            ('sjc_due_date', 'SJC Due Date'),
            ('date', 'Expense Date (التاريخ)'),
        ],
        string='Expenses Due Date Field',
        config_parameter='ao_sjc_task_management.expense_due_field',
        default='date',
        help='Which hr.expense date field is used for Late calculation with grace days. '
             'Status تمت الموافقه = Under processing; Odoo Done = Completed; else New.',
    )
