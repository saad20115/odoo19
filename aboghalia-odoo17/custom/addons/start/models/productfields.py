from odoo import api, fields, models, _
from datetime import datetime


class Product(models.Model):
    _inherit = 'product.template'

    # Define your new field
    type_ = fields.Char(string="Type")
    payer_ = fields.Char(string="Payer")
    # endurance_ = fields.Char(string="endurance", defulte="company")


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Define your new field
    type_ = fields.Char(related="product_id.type_", string="type")
    payer_ = fields.Char(
        string="payer", defulte="company")
    amount_tax = fields.Float(
        string="Amount Tax", compute='amount_tax_compute')
    the_value_work_orderdate = fields.Date(
        string="the value Work order", default=fields.Date.today())

    @api.onchange("price_unit", "tax_id")
    def amount_tax_compute(self):
        for line in self:
            line.amount_tax = line.price_unit * (15/100)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Define your new field
    type_ = fields.Char(related="product_id.type_", string="type")
    payer_ = fields.Char(
        string="payer", defulte="company")

    # def endurance_compute(self):
    #     self.endurance_ = "company"

    amount_tax = fields.Float(
        string="Amount Tax", compute='amount_tax_compute')
    the_value_work_orderdate = fields.Date(
        string="the value Work order", default=fields.Date.today())

    @api.onchange("price_unit", "tax_ids")
    def amount_tax_compute(self):
        for line in self:
            line.amount_tax = line.price_unit * (15/100)


class AccountMove(models.Model):
    _inherit = 'account.move'

    sequence_ao = fields.Char(string='المعرف', copy=False)

    # def action_post(self): 

    #     rec = super().action_post()
    #     if self.date:
    #         isExist = False
    #         prefix = 'S/'
    #         if self.env.company.id == 3:
    #             prefix = 'SJ/'
    #         elif self.env.company.id == 1: 
    #             prefix = 'SL/'
    #         year_final = str(self.date.year)
    #         year_name_final = year_final+"-journal-entry" + str(self.env.company.id)
    #         sequences = self.env['ir.sequence'].search([])
    #         for seq in sequences:
    #             if seq.name == year_name_final:
    #                 isExist = True
    #         if not isExist:
    #             self.env['ir.sequence'].create({"code": year_final+".move.code."+str(self.env.company.id),"name": year_name_final,"padding": 5,"company_id": self.env.company.id})
    #         self.sequence_ao = prefix+year_final+'/'+self.env['ir.sequence'].next_by_code(year_final+".move.code."+str(self.env.company.id))

    #     return	rec 
    def _post(self, soft=True):
        rec = super()._post()
        for record in self:
            if record.date and (not record.sequence_ao):
                isExist = False
                prefix = 'S/'
                if self.env.company.id == 3:
                    prefix = 'SJ/'
                elif self.env.company.id == 1: 
                    prefix = 'SL/'
                year_final = str(record.date.year)
                year_name_final = year_final+"-journal-entry" + str(self.env.company.id)
                sequences = self.env['ir.sequence'].search([])
                for seq in sequences:
                    if seq.name == year_name_final:
                        isExist = True
                if not isExist:
                    self.env['ir.sequence'].create({"code": year_final+".move.code."+str(self.env.company.id),"name": year_name_final,"padding": 5,"company_id": self.env.company.id})
                record.sequence_ao = prefix+year_final+'/'+self.env['ir.sequence'].next_by_code(year_final+".move.code."+str(self.env.company.id))

        return	rec 
    # def create(self, vals):
    #     isExist = False
    #     prefix = 'S/'
    #     if self.env.company.id == 3:
    #         prefix = 'SJ/'
    #     elif self.env.company.id == 1: 
    #         prefix = 'SL/'
    #     year_final = vals['date'][:4]
    #     year_name_final = year_final+"-journal-entry"
    #     sequences = self.env['ir.sequence'].search([])
    #     for seq in sequences:
    #         if seq.name == year_name_final:
    #             isExist = True
    #     if not isExist:
    #         self.env['ir.sequence'].create({"code": year_final+".move.code","name": year_name_final,"padding": 5,"company_id": self.env.company.id})
    #     vals['sequence_ao'] = prefix+year_final+'/'+self.env['ir.sequence'].next_by_code(year_final+".move.code")
    #     return super(AccountMove,self).create(vals)
    

    @api.model
    def get_current_datetime(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
