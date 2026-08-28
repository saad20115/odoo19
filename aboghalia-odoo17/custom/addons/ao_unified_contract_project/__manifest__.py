# -*- coding: utf-8 -*-
{
    'name': 'Unified Contract Project Management | إدارة مشاريع العقد الموحد',
    'version': '17.0.1.0.0',
    'category': 'Services/Project',
    'summary': 'Standalone Unified Contract project management system with work orders, tracking, and Odoo marketplace ready architecture.',
    'description': """
Unified Contract Project Management (Standalone Edition)
======================================================
This module is a 100% standalone system for managing Unified Contract Projects (مشاريع العقد الموحد) and Work Orders (أوامر العمل).

Key Features:
-------------
* Dedicated Standalone Data Models (`unified.contract.project` & `unified.contract.work.order`).
* Custom Stages & Drag-and-Drop Kanban Board (`unified.contract.stage`).
* Interactive Work Order tracking with progress percentage & assignees.
* Mail Thread Chatter integration (messages, activities, attachments).
* Multi-company support and role-based security rules.
* Odoo Apps Store Marketplace ready with zero custom third-party dependencies.

ميزات النظام المستقل:
-------------------
* موديلات بيانات مخصصة ومستقلة كلياً لتجنب أي تعارضات مع النظام الأساسي.
* خيارات إعدادات مرنة للتحكم بطول رقم أمر العمل وشروط التكرار والأرقام فقط.
* إدارة أوامر العمل والمهام الفنية مع نسبة الإنجاز والمسؤولين.
* دعم التوثيق والدردشة وسجل الأنشطة والمرفقات الحية (Chatter).
* متوافق 100% مع أودو 17 (كومينتي وانتربرايس) وجاهز للبيع على متجر أودو.
    """,
    'author': 'Aboghalia Office',
    'website': 'https://www.aboghaliaoffice.com',
    'license': 'OPL-1',
    'price': 49.00,
    'currency': 'EUR',
    'depends': [
        'base',
        'mail',
        'hr',
        'analytic',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/stage_data.xml',
        'data/work_order_stage_data.xml',
        'views/unified_contract_stage_revert_wizard_views.xml',
        'views/unified_contract_skip_execution_wizard_views.xml',
        'views/unified_contract_permit_extend_wizard_views.xml',
        'views/unified_contract_config_views.xml',
        'views/res_config_settings_views.xml',
        'views/unified_contract_project_views.xml',
        'views/unified_contract_work_order_views.xml',
        'views/unified_contract_team_views.xml',
        'views/unified_contract_permission_profile_views.xml',
        'reports/completion_certificate_report.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ao_unified_contract_project/static/src/scss/sidebar.scss',
            'ao_unified_contract_project/static/src/js/sidebar_widget.js',
            'ao_unified_contract_project/static/src/xml/sidebar_templates.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
