{
    'name': 'AO Work Entries',
    'version': '17.0.1.0.1',
    'category': 'Human Resources',
    'summary': 'Calendar view for employee attendance and leaves using existing HR modules',
    'description': """
Work Entries Calendar View
==========================

This module provides a calendar view for tracking employee work entries using existing Odoo modules:
- hr_attendance (for attendance tracking)
- hr_holidays (for leave management)

Features:
* Monthly calendar view displaying all employees
* Color-coded status indicators:
  - Green: Present (has attendance record)
  - Red: On Leave (approved leave request)
  - Yellow: Public Holiday
  - Gray: Weekend
  - Light Gray: No data available
* Employee summary modal with detailed attendance and leave information
* Month navigation (previous/next)
* Click on employee name to view detailed summary
* Click on day cells to see quick status info
* Responsive design optimized for desktop and tablet

The module leverages existing Odoo data:
- Employee records from hr.employee
- Attendance records from hr.attendance  
- Leave requests from hr.leave
- Public holidays from resource.calendar.leaves

No additional data storage required - all information is computed from existing records.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'hr',
        'hr_attendance', 
        'hr_holidays',
        'web'
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/attendance_report_wizard_views.xml',
        'wizard/edit_absence_days_wizard_views.xml',
        'views/work_entries.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ao_work_entries/static/src/xml/work_entries.xml',
            'ao_work_entries/static/src/css/work_entries.css',
            'ao_work_entries/static/src/js/work_entries.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
}