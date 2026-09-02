# -*- coding: utf-8 -*-
{
    'name': 'PO Follow-up',
    'version': '17.0.1.0.0',
    'category': 'Operations',
    'summary': 'PO follow-up intake, Accounting bridge, and PO Order attachments.',
    'description': """
        Track purchase orders (PO), assign them to Accounting Aboghalia via API,
        and manage post-accounting PO Order documents (PDF viewer) for the
        unified contract team — including home screen and employee assignment.
    """,
    'author': 'Abo Ghaly',
    'depends': ['base', 'mail'],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/po_followup_security.xml',
        'security/ir.model.access.csv',
        'data/po_contractor_data.xml',
        'data/po_office_data.xml',
        'data/po_entity_data.xml',
        'data/po_followup_actions.xml',
        'data/po_order_recompute.xml',
        'views/po_contractor_views.xml',
        'views/po_office_views.xml',
        'views/po_entity_views.xml',
        'views/po_followup_views.xml',
        'views/po_order_views.xml',
        'views/po_order_assign_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ao_po_followup/static/src/css/po_followup.css',
            'ao_po_followup/static/src/js/po_followup_list.js',
            'ao_po_followup/static/src/js/en_us_date_field.js',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
