# -*- coding: utf-8 -*-
{
    'name': 'AO Work Entries - Attendance Grid PDF Export',
    'version': '17.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Add Print PDF button to Attendance Grid and export PDF from the grid data.',
    'depends': ['ao_work_entries', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'report/report.xml',
        'report/attendance_grid_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ao_work_entries_pdf/static/src/xml/attendance_grid_pdf_button.xml',
            'ao_work_entries_pdf/static/src/js/attendance_grid_pdf_export.js',
        ],
    },
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
}
