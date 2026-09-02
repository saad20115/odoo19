from odoo import fields,models

class EmployeeRequestTag(models.Model):
    _name = 'employee.request.tag'
    _description = 'Employee Request Tag'

    name = fields.Char(string="Tag Name", required=True)
    color = fields.Integer(string='Color') 
