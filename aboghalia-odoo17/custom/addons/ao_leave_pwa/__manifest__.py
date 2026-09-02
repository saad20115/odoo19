# -*- coding: utf-8 -*-
{
    'name': 'Leaves PWA | تطبيق الإجازات',
    'version': '17.0.1.3.0',
    'category': 'Human Resources/Time Off',
    'summary': 'Installable Arabic RTL PWA for leave requests and the 4-level approval cycle.',
    'description': """
Leaves PWA (SJC)
================
Mobile Progressive Web App for employees and approvers:

* Login with Odoo credentials (API token)
* Request time off, view balances, track status
* Approve / refuse using ao_leave_approval cycle
  (Manager → Project Manager → General Manager → HR)
* Web Push + FCM notifications on leave cycle events

Open: /leave

Optional server package for browser Web Push: pip install pywebpush
(HTTPS required for install prompt + push on real phones)
    """,
    'author': 'Aboghalia Office',
    'website': 'https://www.aboghaliaoffice.com',
    'license': 'LGPL-3',
    'depends': [
        'web',
        'hr_holidays',
        'ao_leave_approval',
        'ao_attendance_app_api',
    ],
    'data': [
        'data/leave_pwa_balance_data.xml',
        'security/ir.model.access.csv',
        'views/leave_pwa_balance_views.xml',
    ],
    'external_dependencies': {
        'python': [],  # optional: pywebpush for browser push; FCM works without it
    },
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
}
