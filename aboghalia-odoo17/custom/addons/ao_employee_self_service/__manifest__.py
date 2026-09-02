# -*- coding: utf-8 -*-
{
    'name': 'البوابة الإلكترونية | Enterprise Web Portal',
    'version': '17.0.1.0.0',
    'category': 'Human Resources/Self Service',
    'summary': 'البوابة الإلكترونية الموحدة للخدمات الذاتية والمهام والطلبات بأسلوب عصري شافي',
    'description': """
الخدمات الذاتية للموظف - Odoo 17 External Web Portal
===================================================
- بوابة إلكترونية خارجية مستقلة على المسار `/portal/self-service`
- تصميم عصري فريد بأسلوب Glassmorphism ودعم كامل للغة العربية (RTL)
- تسجيل الحضور والانصراف التفاعلي مع تحديد الموقع الجغرافي (GPS)
- تقديم طلبات الإجازات، السلف، شهادات التعريف بالراتب، وأذونات الخروج
- سلة المهام والطلبات ومتابعتها الحية (My Requests & Approvals)
- مركز الإشعارات والتنبيهات الذكية (انتهاء الوثائق والعقود والتأخير)
    """,
    'author': 'Al-Bighalia / Saad',
    'website': 'https://github.com/saad20115/odoo19',
    'depends': [
        'base',
        'hr',
        'hr_attendance',
        'hr_holidays',
        'web',
        'portal',
        'website',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/portal_templates.xml',
        'views/employee_self_service_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ao_employee_self_service/static/src/scss/backend_rtl_ltr_fix.scss',
            'ao_employee_self_service/static/src/js/backend_rtl_direction.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
