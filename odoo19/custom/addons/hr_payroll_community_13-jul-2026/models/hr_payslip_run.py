# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
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
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from odoo import fields, models, _, api


class HrPayslipRun(models.Model):
    """Create new model for getting Payslip Batches"""
    _name = 'hr.payslip.run'
    _description = 'Payslip Batches'
    _inherit = 'mail.thread'

    name = fields.Char(required=True, help="Name for Payslip Batches",
                       string="Name")
    slip_ids = fields.One2many('hr.payslip',
                               'payslip_run_id',
                               string='Payslips',
                               help="Choose Payslips for Batches")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('close', 'Close'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft',
                               help="Status for Payslip Batches")
    date_start = fields.Date(string='Date From', required=True,
                            help="Start date for Payslip",
                            default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=-1, day=1,
                                                              days=0)).date()))
    date_end = fields.Date(string='Date To', required=True,
                          help="End date for Payslip",
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=0, day=1,
                                                              days=-1)).date()))
    credit_note = fields.Boolean(string='Credit Note',
                                 help="If its checked, indicates that all"
                                      "payslips generated from here are refund"
                                      "payslips.")

    @api.onchange('date_start', 'date_end')
    def _onchange_date(self):
            
        for payslip in self.slip_ids:
                payslip.write({'date_from': self.date_start, 'date_to': self.date_end})

    def action_payslip_run(self):
        """Function for state change"""
        return self.write({'state': 'draft'})

    def close_payslip_run(self):
        """Function for state change"""
        return self.write({'state': 'close'})

    def action_payslip_confirm(self):
        for line in self.slip_ids:
            line.action_payslip_done()
        # slips = self.env["hr.payslip"].search([])
        # for slip in slips:
        #     if slip.is_cleared == False :
        #         slip.y_absence = slip.x_absence 
        #         slip.y_penalties = slip.x_penalties
        #         slip.y_delay = slip.x_delay
        #         slip.y_other_discounts = slip.x_other_discounts
        #         slip.y_number_of_absence_days = slip.x_number_of_absence_days
        #         slip.y_number_of_penalty_days = slip.x_number_of_penalty_days
        #         slip.y_number_of_hours = slip.x_number_of_hours
        #         slip.y_hour_rate = slip.x_hour_rate
        #         slip.y_number_of_overtime_hours = slip.x_number_of_overtime_hours
        #         slip.y_total_overtime = slip.x_total_overtime
        #         slip.is_cleared = True
        # contracts = self.env["hr.contract"].search([])
        # for contract in contracts:
        #         contract.x_number_of_absence_days = 0
        #         contract.x_number_of_penalty_days = 0
        #         contract.x_number_of_hours = 0
        #         contract.x_number_of_overtime_hours = 0
        #         contract.x_other_discounts = 0
    
    def action_compute_sheet_all(self):
        for line in self.slip_ids:
            line.action_compute_sheet()