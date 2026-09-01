# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.
{
    "name": "All in one WhatsApp Integration-Sales, Purchase, Account and CRM",
    "author": "Softhealer Technologies",
    "website": "http://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Extra Tools",
    "license": "OPL-1",
    "summary": "Whatsapp Integration App,  Invoice To Customer Whatsapp Module, stock whatsup Whatsapp, Sales Whatsapp App, Purchase Whatsapp, CRM Whatsapp, invoice whatsapp, inventory whatsapp, account whatsup Odoo",
    "description": """Using this module you can send Quotations, Sale Order, Invoices, Bills, RFQs, Purchase Orders,
     and direct to Clients/Vendor's WhatsApp. 
     You can easily send PDF of sale, purchase, invoice & inventory documents using URL.""",
    "version": "0.0.1",
    "depends": ['crm', 'sale_management', 'purchase', 'stock'],
    "application": True,
    "data": [
            "data/mail_template_data.xml",

            "security/whatsapp_security_groups.xml",
            "security/ir.model.access.csv",

            "wizard/sh_send_whatsapp_message_wizard_views.xml",
            "views/res_partner_views.xml",
            "wizard/sh_send_whatsapp_number_wizard_views.xml",
            "views/crm_lead_views.xml",
            "views/sale_order_views.xml",
            "views/purchase_order_views.xml",
            "views/customer_invoice_views.xml",
            "views/customer_delivery_views.xml",
            "views/res_config_settings_views.xml",
            "views/res_users_views.xml",
            "views/account_payment_views.xml",
    ],
    "images": ["static/description/background.png", ],
    "live_test_url": "https://www.youtube.com/watch?v=qsbWdscnly0&feature=youtu.be",
    "auto_install": False,
    "installable": True,
    "price": 45,
    "currency": "EUR"
}
