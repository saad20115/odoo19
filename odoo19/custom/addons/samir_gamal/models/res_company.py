from odoo import models,fields

class Company(models.Model):
    _inherit = 'res.company'

    employee_request_prefix = fields.Char(string="Prefix")
