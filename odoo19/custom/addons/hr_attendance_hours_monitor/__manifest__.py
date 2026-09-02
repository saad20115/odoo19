# -*- coding: utf-8 -*-
{
    'name': 'HR Attendance Working Hours Monitor',
    'version': '17.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Monitor actual worked hours vs required hours',
    'description': """
        HR Attendance Working Hours Monitor
        ===================================
        This module adds functionality to monitor employee attendance against
        their work schedule. It calculates actual worked hours per day and 
        compares them to the required hours from the work schedule.

        Features:
        ---------
        * Display required and actual worked hours in attendance views
        * Highlight records where worked hours are less than required
        * Supports coloring rows based on worked hours vs required hours
    """,
    'author': 'Mohamed Adel',
    'depends': ['hr_attendance', 'hr'],
    'data': [
        'views/hr_attendance_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
