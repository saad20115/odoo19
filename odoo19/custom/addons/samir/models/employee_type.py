from odoo import fields , models 


class EmployeeRequestType(models.Model):
    _name = 'employee.request.type'
    _description = 'Employee Request Type'

    name = fields.Char(string="Transaction Type", required=True)
