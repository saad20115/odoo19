# -*- coding: utf-8 -*-
{
    'name': 'PO Follow-up Makka',
    'version': '17.0.1.2.0',
    'category': 'Operations',
    'summary': 'Makka unified contract PO follow-up, Accounting bridge, print and merge.',
    'description': """
        Track Makka purchase orders (العقد الموحد مكة), assign them to Accounting
        Aboghalia via API, receive returned invoices on Makka PO Order, then print
        فاتورة صيانة مكة and merge PDF attachments on the portal.
    """,
    'author': 'Abo Ghaly',
    'depends': ['base', 'mail'],
    'external_dependencies': {
        'python': ['requests', 'PyPDF2'],
    },
    'data': [
        'security/makka_po_followup_security.xml',
        'security/ir.model.access.csv',
        'data/makka_po_contractor_data.xml',
        'data/makka_po_office_data.xml',
        'data/makka_po_entity_data.xml',
        'data/makka_po_followup_actions.xml',
        'data/makka_po_order_recompute.xml',
        'views/makka_po_contractor_views.xml',
        'views/makka_po_office_views.xml',
        'views/makka_po_entity_views.xml',
        'views/makka_po_import_fix_wizard_views.xml',
        'views/makka_po_followup_views.xml',
        'views/makka_po_order_views.xml',
        'views/makka_po_order_assign_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ao_makka_po_followup/static/src/css/makka_po_followup.css',
            'ao_makka_po_followup/static/src/js/makka_po_followup_list.js',
            'ao_makka_po_followup/static/src/js/en_us_date_field.js',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
