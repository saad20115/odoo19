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
from odoo import api, models


class HrPayslip(models.Model):
    """ Extends the 'hr.payslip' model to include
    additional functionality related to employee loans."""
    _inherit = 'hr.payslip'

    def _get_contracts_for_inputs(self, contract_ids):
        """Normalize contract_ids (recordset or list of ids) to a recordset."""
        if not contract_ids:
            return self.env['hr.contract']
        if hasattr(contract_ids, 'ids'):
            return contract_ids
        return self.env['hr.contract'].browse(contract_ids)

    def get_inputs(self, contract_ids, date_from, date_to):
        """Sum ALL unpaid loan installments in the payslip period.

        Covers multiple loans and multiple installments on the same loan
        within the same month.
        """
        res = super(HrPayslip, self).get_inputs(contract_ids, date_from,
                                                date_to)
        contracts = self._get_contracts_for_inputs(contract_ids)
        employees = contracts.mapped('employee_id')
        if not employees and self.employee_id:
            employees = self.employee_id
        for emp in employees:
            loan_lines = self.env['hr.loan.line'].search([
                ('loan_id.employee_id', '=', emp.id),
                ('loan_id.state', '=', 'approve'),
                ('paid', '=', False),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])
            if not loan_lines:
                continue
            total_amount = sum(loan_lines.mapped('amount'))
            for result in res:
                if result.get('code') == 'LO':
                    result['amount'] = total_amount
                    result['loan_line_ids'] = [(6, 0, loan_lines.ids)]
        return res

    def _refresh_loan_input_lines(self):
        """Persist summed loan inputs on the payslip (DB) for line computation."""
        for payslip in self:
            if not payslip.contract_id or not payslip.date_from or not payslip.date_to:
                continue
            if not payslip.id or not isinstance(payslip.id, int):
                continue
            input_data = payslip.get_inputs(
                payslip.contract_id, payslip.date_from, payslip.date_to)
            commands = [(5, 0, 0)]
            for vals in input_data:
                line_vals = {
                    'name': vals.get('name'),
                    'code': vals.get('code'),
                    'amount': vals.get('amount', 0.0),
                    'contract_id': vals.get(
                        'contract_id', payslip.contract_id.id),
                    'date_from': vals.get('date_from', payslip.date_from),
                    'date_to': vals.get('date_to', payslip.date_to),
                }
                if vals.get('loan_line_ids'):
                    line_vals['loan_line_ids'] = vals['loan_line_ids']
                commands.append((0, 0, line_vals))
            payslip.write({'input_line_ids': commands})

    @api.model
    def _get_payslip_lines(self, contract_ids, payslip_id):
        """Refresh summed LO inputs after onchange, then compute salary lines."""
        payslip = self.env['hr.payslip'].browse(payslip_id)
        payslip._refresh_loan_input_lines()
        return super(HrPayslip, self)._get_payslip_lines(
            contract_ids, payslip_id)

    def action_compute_sheet(self):
        """Parent onchange rebuilds inputs; LO sum is re-applied in _get_payslip_lines."""
        return super(HrPayslip, self).action_compute_sheet()

    def action_payslip_done(self):
        """Refresh summed loan lines, mark them paid, then confirm payslip."""
        self._refresh_loan_input_lines()
        for line in self.input_line_ids:
            if line.loan_line_ids:
                line.loan_line_ids.write({'paid': True})
                line.loan_line_ids.mapped('loan_id')._compute_total_amount()
        return super(HrPayslip, self).action_payslip_done()

    def action_payslip_cancel(self):
        for line in self.input_line_ids:
            if line.loan_line_ids:
                line.loan_line_ids.write({'paid': False})
                line.loan_line_ids.mapped('loan_id')._compute_total_amount()
        return super(HrPayslip, self).action_payslip_cancel()
