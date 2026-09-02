# -*- coding: utf-8 -*-
{
    'name': 'Leave 4-Level Approval',
    'version': '17.0.1.1.0',
    'category': 'Human Resources',
    'summary': 'Sequential leave approval: Manager, Project Manager, General Manager, HR Managers.',
    'description': """
        Employee time-off requests follow a fixed 4-level approval cycle:
        Direct Manager → Project Manager group → General Manager group → HR Managers group.
        Remaining leave days are shown on the request form. Approve/Refuse is limited
        to the group that currently has the queue.
    """,
    'author': 'Abo Ghaly',
    'depends': [
        'hr_holidays',
        'ohrms_holidays_approval',
        'hr_vacation_mngmt',
    ],
    'data': [
        'security/leave_approval_security.xml',
        'views/hr_employee_views.xml',
        'views/hr_leave_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
