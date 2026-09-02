# -*- coding: utf-8 -*-
from odoo import fields, models


class PoEntity(models.Model):
    _name = 'po.entity'
    _description = 'Entity'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)
