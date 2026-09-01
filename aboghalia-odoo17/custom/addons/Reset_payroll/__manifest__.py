# -*- coding: utf-8 -*-
# Copyright 2019-TODAY Daniel Lago Suarez <dls@anuia.es>
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Reset Payroll',
    'summary': '',
    'description': """Reset Payroll

""",
    'category': '',
    'version': '1.0.0',
    'license': 'AGPL-3',
    'author': 'Zyad Esam',
    'maintainer': 'Zyad Esam',
    'contributors': [
        'Daniel Lago Suarez <dls@anubia.es>',
    ],
    'website': 'http://www.anubia.es',
    'depends': [
        'base',
        'hr', 'hr_payroll_community',
        
    ],
    'data': [

        'views/reset.xml',
    ],
    'demo': [],
    'test': [],
  
    'installable': True,
    'auto_install': False,
    'application': False,
    'price': 0,
    'currency': 'EUR',
}
