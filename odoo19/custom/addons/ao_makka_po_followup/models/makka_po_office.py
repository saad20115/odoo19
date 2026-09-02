# -*- coding: utf-8 -*-
from odoo import fields, models


class PoOffice(models.Model):
    _name = 'makka.po.office'
    _description = 'Office'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)
