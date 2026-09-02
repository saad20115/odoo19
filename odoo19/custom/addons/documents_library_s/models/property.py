from odoo import models,fields



class property(models.Model):

    _name="property"
    _inherit ='mail.thread'

    name = fields.Char()
    ministrey = fields.Many2one('res.partner')
    company = fields.Many2one('res.partner')
    responsible_employee = fields.Many2one('res.partner')
    way_to_renew = fields.Selection([('Electronic','الكتروني'),('manual','يدوي')])
    expire_date = fields.Date(tracking= True) 
    date_version = fields.Date(tracking= True)
    special_number = fields.Integer()
    addition_number = fields.Integer()
    attachment_id = fields.Binary( string="مرفق الوثيقة")
