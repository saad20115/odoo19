# -*- coding: utf-8 -*-
{
    'name': 'SJC+ Task Management',
    'version': '17.0.1.6.3',
    'category': 'Project',
    'summary': 'SJC+ three-role task dashboard (beta).',
    'description': """
        SJC+ task dashboard for Management, Project Managers, and Employees.

        Phase 1 data sources: PO Madina, PO Makka, Incoming Mail,
        Administrative Communications, Expenses.
        Other SJC menus are empty shells until later sources exist.

        Install on the beta database only. Do not install on live.
    """,
    'author': 'Abo Ghaly',
    'depends': [
        'base',
        'web',
        'hr',
        'hr_expense',
        'ao_po_followup',
        'ao_makka_po_followup',
        'incoming_mail_store',
    ],
    'data': [
        'security/sjc_security.xml',
        'security/ir.model.access.csv',
        'data/sjc_data.xml',
        'views/res_users_views.xml',
        'views/po_followup_views.xml',
        'views/makka_po_followup_views.xml',
        'views/po_order_views.xml',
        'views/hr_expense_views.xml',
        'views/incoming_mail_views.xml',
        'views/sjc_po_instruction_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
        'data/sjc_home_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ao_sjc_task_management/static/src/css/sjc_dashboard.css',
            'ao_sjc_task_management/static/src/js/sjc_dashboard.js',
            'ao_sjc_task_management/static/src/xml/sjc_dashboard.xml',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
