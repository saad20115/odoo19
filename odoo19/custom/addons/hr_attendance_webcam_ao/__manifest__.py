{
    "name": "Attendance WebCam AO",
    "summary": "Take images with a WebCam when employees check-in and check-out from attendance.",
    "version": "1.0",
    "category": "Human Resources",
    'author': "Ahmed Osama",
    # "data": [
    #     "views/assets.xml",
    #     "views/hr_attendance_view.xml",
    # ],
    "depends": [
        "web",
        "hr_attendance"
    ],
    # "qweb": [
    #     "static/src/xml/hr_attendance_webcam.xml",
    # ],
    'assets': {
        # 'web.assets_backend': [
        #     'hr_attendance_webcam_ao/static/src/xml/custom_webcam_popup.xml',
        #     'hr_attendance_webcam_ao/static/src/js/custom_webcam_popup.js',
        #     'hr_attendance_webcam_ao/static/src/js/kiosk_attendance.js',
        # ],
        'hr_attendance.assets_public_attendance': [
            'hr_attendance_webcam_ao/static/src/xml/custom_webcam_popup.xml',
            'hr_attendance_webcam_ao/static/src/js/custom_webcam_popup.js',
            'hr_attendance_webcam_ao/static/src/js/kiosk_attendance.js',
        ],
    },
    "installable": True,
    'auto_install': False,
    'application': True,
}
