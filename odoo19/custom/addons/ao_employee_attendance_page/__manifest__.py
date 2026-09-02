{
    'name': 'Employee Attendance Page',
    'version': '17.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Employee attendance check-in/check-out page',
    'description': """
        Employee Attendance Page for Odoo 17
        - Single page attendance interface
        - Uses existing hr.attendance model
        - Modern OWL architecture
        - Employee image and name display
    """,
    'author': 'Your Company',
    'depends': ['hr_attendance', 'web'],
    'data': [
        'views/attendance_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ao_employee_attendance_page/static/src/js/attendance_kiosk.js',
            'ao_employee_attendance_page/static/src/xml/attendance_kiosk.xml',
            'ao_employee_attendance_page/static/src/css/attendance_kiosk.css',
        ],
    },
    'installable': True,
    'auto_install': False,
}