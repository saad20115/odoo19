# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2022-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

from odoo import models, fields, api
from odoo.exceptions import UserError



class AccountAccount(models.Model):
    _inherit = 'account.journal'

    @api.model
    def default_get(self, default_fields):
        res = super(AccountAccount, self).default_get(default_fields)
        branch_id = False

        if self._context.get('branch_id'):
            branch_id = self._context.get('branch_id')
        elif self.env.user.branch_id:
            branch_id = self.env.user.branch_id.id
        res.update({
            'branch_id' : branch_id
        })
        return res

    branch_id = fields.Many2one('res.branch', string="Branch")


    default_account_id = fields.Many2one(
    comodel_name='account.account', check_company=True, copy=False,
    ondelete='restrict',
    string='Default Account',
    domain="[('deprecated', '=', False), ('company_id', '=', company_id),"
            "'|', ('account_type', '=', default_account_type), "
            "('account_type', 'not in', ('asset_receivable', 'liability_payable')),"
            "'|',('branch_id', '=', branch_id), ('branch_id', '=', False)]")

    suspense_account_id = fields.Many2one(
        comodel_name='account.account', check_company=True, ondelete='restrict',
        readonly=False, store=True,
        compute='_compute_suspense_account_id',
        help="Bank statements transactions will be posted on the suspense "
             "account until the final reconciliation "
             "allowing finding the right account.", string='Suspense Account',
        domain="[('deprecated', '=', False), ('company_id', '=', company_id), \
                        ('account_type', 'not in', ('asset_receivable', 'liability_payable')), \
                        ('account_type', '=', 'asset_current')], '|', "
               "('branch_id', '=', branch_id), ('branch_id', '=', False)")

    profit_account_id = fields.Many2one(
        comodel_name='account.account', check_company=True,
        help="Used to register a profit when the ending balance of a cash "
             "register differs from what the system computes",
        string='Profit Account',
        domain="[('deprecated', '=', False), ('company_id', '=', company_id), \
                        ('account_type', 'not in', ('asset_receivable', 'liability_payable')), \
                        ('account_type', 'in', ('income', 'income_other')), '|', "
               "('branch_id', '=', branch_id), ('branch_id', '=', False)]")

    loss_account_id = fields.Many2one(
        comodel_name='account.account', check_company=True,
        help="Used to register a loss when the ending balance of a cash "
             "register differs from what the system computes",
        string='Loss Account',
        domain="[('deprecated', '=', False), ('company_id', '=', company_id), \
                        ('account_type', 'not in', ('asset_receivable', 'liability_payable')), \
                        ('account_type', '=', 'expense'), '|', "
               "('branch_id', '=', branch_id), ('branch_id', '=', False)]")
    
    
    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        selected_brach = self.branch_id
        if selected_brach:
            user_id = self.env['res.users'].browse(self.env.uid)
            user_branch = user_id.sudo().branch_id
            if user_branch and user_branch.id != selected_brach.id:
                raise UserError("Please select active branch only. Other may create the Multi branch issue. \n\ne.g: If you wish to add other branch then Switch branch from the header and set that.") 
        """onchange methode"""
        self.default_account_id = False
        self.suspense_account_id = False
        self.profit_account_id = False
        self.loss_account_id = False    