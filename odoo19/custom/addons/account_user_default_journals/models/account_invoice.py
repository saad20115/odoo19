from odoo import models, api, fields


class account_invoice(models.Model):

    _inherit = 'account.move'

    @api.depends('move_type')
    def _compute_journal_id(self):
        if(self.move_type == 'in_invoice'):
            self.journal_id = self.env.user.default_purchase_journal_id
        if(self.move_type == 'out_invoice'):
            self.journal_id = self.env.user.default_sale_journal_id


