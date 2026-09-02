from odoo import models, fields, api

class CTSAuditLog(models.Model):
    _name = 'cts.audit.log'
    _description = 'CTS Audit Log'
    _order = 'create_date desc'

    transaction_id = fields.Many2one('employee.request', string="المعاملة", required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string="المستخدم", default=lambda self: self.env.user, required=True)
    action = fields.Char(string="الإجراء (Action)", required=True)
    
    old_status = fields.Char(string="الحالة القديمة")
    new_status = fields.Char(string="الحالة الجديدة")
    
    notes = fields.Text(string="ملاحظات / تفاصيل")
