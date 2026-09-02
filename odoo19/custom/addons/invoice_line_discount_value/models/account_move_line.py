from odoo import fields, models, api








class AccountMoveLine(models.Model):

    _inherit = 'account.move.line'

    discount_value_f = fields.Float(
    string='قيمة الخصم',

    )

    @api.onchange("discount_value_f","price_unit")
    def calculate_discount_percentage(self):
        if self.price_unit != 0:
            final_res = (self.discount_value_f / self.price_unit) * 100
            self.discount = final_res
   


    @api.onchange("discount","price_unit","quantity")
    def calculate_discount_value_f(self):
        final_res = (self.discount/100) * self.price_unit * self.quantity
        self.discount_value_f = final_res

    