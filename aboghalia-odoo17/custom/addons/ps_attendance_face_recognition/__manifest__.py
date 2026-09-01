# -*- coding: utf-8 -*-

{
    # Module Info
    'name': "Attendance Face Recognition",
    'version': '17.0.1.0.0',
    'category': 'Hr Attendance',
    'description': 'Facial recognition-based attendance system for employees.',
    'summary': 'This module enables employees to register their attendance using facial recognition. It integrates with the webcam to scan and verify employee faces for accurate and secure attendance tracking.',

    # Author
    'author': 'PySquad Informatics LLP',
    'company': 'PySquad Informatics LLP',
    'maintainer': 'PySquad Informatics LLP',
    'website': 'https://www.pysquad.com/',

    # Dependencies
    'depends': ['base_setup','hr_attendance','hr'],

    # Data
    'data':[
        'views/res_config_settings_view.xml',
        'views/hr_attendance_view.xml'
    ],

    'assets': {
        'web.assets_backend': [
            'ps_attendance_face_recognition/static/src/css/camera_effect.css',
            'ps_attendance_face_recognition/static/src/js/attendance_menu.js',
            'ps_attendance_face_recognition/static/src/xml/camera_dialog_attendance_templates.xml',
            'ps_attendance_face_recognition/static/src/xml/camera_dialog_templates.xml',
            'ps_attendance_face_recognition/static/src/xml/image_upload_templates.xml',
            'ps_attendance_face_recognition/static/src/xml/public_kiosk_app.xml',
            # 'ps_attendance_face_recognition/static/src/xml/attendance_menu.xml',
            'ps_attendance_face_recognition/static/src/js/CameraDialog.js',
            'ps_attendance_face_recognition/static/src/js/CameraDialogAttendance.js',
            'ps_attendance_face_recognition/static/src/js/ImageField.js',
            'ps_attendance_face_recognition/static/src/js/public_kiosk_app.js',

        ],
    },
    
    'images': [
        'static/description/banner.png',
    ],

    # Technical Info
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}

