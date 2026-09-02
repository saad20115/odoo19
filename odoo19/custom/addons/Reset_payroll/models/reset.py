from odoo import models

class HrPayslip(models.Model):
    
    _inherit = 'hr.payslip'


    def action_reset_to_draft(self):
        for payslip in self:

            if payslip.state == 'done' :
                payslip.state = 'draft'




















