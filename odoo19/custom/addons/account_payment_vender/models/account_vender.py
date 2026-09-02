# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class AccountPaymentInherit(models.Model):
    _inherit = "account.payment"



    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer/Vendor",
        store=True, readonly=False, ondelete='restrict',
        compute='_compute_partner_id',
        domain="['|', ('parent_id','=', False), ('is_company','=', True)]",
        tracking=True,
        check_company=True,
        required=True
    )

