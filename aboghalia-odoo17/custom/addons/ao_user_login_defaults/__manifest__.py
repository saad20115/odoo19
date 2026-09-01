# -*- coding: utf-8 -*-
{
    'name': 'User Login Defaults',
    'version': '17.0.1.0.5',
    'category': 'Hidden',
    'summary': 'Safe home action after login and default company selection.',
    'description': """
        - Skip inaccessible Home Action after login (fallback to Discuss).
        - On login, select company from related Employee form (hr.employee.company_id),
          then fall back to user Default Company. Manual company switch still works.
    """,
    'author': 'Abo Ghaly',
    'depends': ['web', 'mail', 'hr', 'base_setup'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
