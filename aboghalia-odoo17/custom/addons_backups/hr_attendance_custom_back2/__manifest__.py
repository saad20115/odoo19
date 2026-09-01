{
    'name': "HR Attendance Custom",
    'author': "Mohamed Gamal",
    'category': '',
    'version': '17.0.0.0',
    'depends': ['base', 'hr_attendance','hr_holidays'
                ],
    'data': [
        # 'security/security.xml',
        # 'security/ir.model.access.csv',
        # 'reports/property_report.xml',    
        # 'data/sequence.xml',
        #  'views/base_menu.xml',
           'views/hr_attendance_inhirt_views.xml',
        # 'views/owner_view.xml',
        # 'views/tag_view.xml',
        # 'views/sale_order_view.xml',
        # 'views/res_partner_view.xml',
        # 'views/account_move_view.xml',
        # 'views/property_history_view.xml',
        # 'wizard/change_state_wizard_view.xml',
             ],
    'assets':{
        'web.assets_backend':[
            # 'app_one/static/src/css/property.css',


        ],

    },

    'application': True,


}