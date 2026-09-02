# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Start',
    'version': '1.1',
    'summary': 'MY First Model',
    'author': 'mohamed menam',
    'sequence': 1,
    'description': """
Invoicing & Payments
====================
The specific and easy-to-use Invoicing system in Odoo allows you to keep track of your accounting, even when you are not an accountant. It provides an easy way to follow up on your vendors and customers.

You could use this simplified accounting in case you work with an (external) account to keep your books, and you still want to keep track of payments. This module also offers you an easy method of registering payments, without having to encode complete abstracts of account.
    """,
    'category': 'Invoicing Management',
    'website': 'https://www.odoo.com/page/billing',
    'depends': ['base', 'product', 'sale', 'account', 'l10n_sa'],
    'data': [
        # "reports/frist.xml",
        # "views/productedite.xml",
        # "reports/report2.xml",
        # "reports/osas.xml"
        "reports/equipment_handing.xml",
        "reports/equipment_disclaimer.xml",
        "reports/fleet_handing.xml",
        "reports/fleet_disclaimer.xml"

    ],
    'assets': {
        'web.report_assets_common': ['start/static/src/css/fonts.css'],
    },
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
}
