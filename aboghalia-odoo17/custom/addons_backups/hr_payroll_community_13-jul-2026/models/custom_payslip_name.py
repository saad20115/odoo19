from odoo import models, fields, api

class PayslipNameModel(models.Model):
    _name = 'custom.payslip'
    _rec_name = 'payslip_name'

    payslip_name = fields.Char(string='Payslip Name')