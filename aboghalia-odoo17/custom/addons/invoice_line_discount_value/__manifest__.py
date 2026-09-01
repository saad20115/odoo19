# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Invoice Line Discount Value",
    "version": "1.0.0",
    "summary": "Invoice Line Discount Value",
    "author": "Ahmed Osama",
    "sequence": 1,
    "description": """Invoice Line Discount Value""",
    "category": "Custom",
    "website": "https://www.odoo.com/page/billing",
    "license": "LGPL-3",
    "depends": [
        "crm",
        "sale",
    ],
    "data": [
        "views/account_move.xml",


    ],
   'assets':
        {},
    "demo": [],
    "installable": True,
    "auto_install": False,
}
    # "data": [
    #     'security/ir.model.access.csv',
    #     "views/notification_view.xml",
    #     "views/menu.xml",
    # ]