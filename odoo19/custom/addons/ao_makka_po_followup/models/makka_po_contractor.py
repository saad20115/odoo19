# -*- coding: utf-8 -*-
from odoo import fields, models


class PoContractor(models.Model):
    _name = 'makka.po.contractor'
    _description = 'Contractor'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)
