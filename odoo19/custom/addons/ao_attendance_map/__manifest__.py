{
    'name': 'HR Attendance Maps',
    'version': '17.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Add Leaflet maps to attendance records',
    'description': """
        This module adds Leaflet maps to attendance records showing check-in and check-out locations
        based on latitude and longitude coordinates.
    """,
    'depends': ['hr_attendance'],
    'data': [
        'views/hr_attendance_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'ao_attendance_map/static/src/css/leaflet_map_widget.css',
            'ao_attendance_map/static/src/js/leaflet_map_widget.js',
            'ao_attendance_map/static/src/xml/leaflet_map_widget.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}