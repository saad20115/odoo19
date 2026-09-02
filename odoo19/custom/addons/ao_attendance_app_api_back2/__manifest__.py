# -*- coding: utf-8 -*-
{
    'name': "Attendance Mobile App API",
    'summary': "Attendance Mobile App API",
    'description': """Attendance Mobile App API""",
    'author': "Ahmed Osama, Fathy Tarek",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'version': '1.0',
    'license': 'AGPL-3',
    'depends': ['base', 'hr_attendance','hr', 'hr_expense', 'hr_payroll_community', 'hr_payroll_account_community'],
    "external_dependencies": {"python": ["firebase-admin", "python-dotenv", "beautifulsoup4"]},
    'data': [
        'security/ir.model.access.csv',
        'views/inherit_hr_employee.xml',
        'views/notifications.xml'
    ],
    'application': True,
    'installable': True
}
