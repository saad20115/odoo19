from odoo import fields , models

class ResCompany(models.Model):
    _inherit = 'res.company'

    request_sequence_prefix = fields.Char(string="Request Prefix")
