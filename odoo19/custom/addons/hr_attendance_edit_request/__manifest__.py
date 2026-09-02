{
    'name': "HR Attendance Edit Custom",
    'author': "Mohamed Gamal",
    'category': '',
    'version': '17.0.0.0',
    'depends': ['base', 'hr_attendance','hr_attendance', 'hr',
                ],
    'data': [

        'security/ir.model.access.csv',
        'views/hr_attendance_edit_request_views.xml',
             ],
    'assets':{
        'web.assets_backend':[
            # 'app_one/static/src/css/property.css',


        ],

    },

    'application': True,


}