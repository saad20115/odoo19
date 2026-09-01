# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HrPayslipComputeConfirmWizard(models.TransientModel):
    _name = 'hr.payslip.compute.confirm.wizard'
    _description = 'Compute and Confirm Payslips'

    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Employees',
        readonly=True,
    )
    payslip_ids = fields.Many2many(
        'hr.payslip',
        string='Payslips',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids') or []
        payslips = self.env['hr.payslip'].browse(active_ids)
        if payslips:
            res['payslip_ids'] = [(6, 0, payslips.ids)]
            res['employee_ids'] = [(6, 0, payslips.mapped('employee_id').ids)]
            res.setdefault('date_from', payslips[0].date_from)
            res.setdefault('date_to', payslips[0].date_to)
        return res

    def action_compute_and_confirm(self):
        """Apply period, then Compute Sheet and Confirm (same as form buttons)."""
        self.ensure_one()
        if not self.payslip_ids:
            raise UserError(_("No payslips selected."))
        if self.date_from > self.date_to:
            raise UserError(_("Date From must be before Date To."))

        payslips = self.payslip_ids
        payslips.write({
            'date_from': self.date_from,
            'date_to': self.date_to,
        })

        draft_payslips = payslips.filtered(lambda p: p.state == 'draft')
        if not draft_payslips:
            raise UserError(_(
                "None of the selected payslips are in Draft. "
                "Only draft payslips can be computed and confirmed."
            ))

        # Process one-by-one so errors can name the failing employee
        for payslip in draft_payslips:
            employee_name = payslip.employee_id.display_name or _('Unknown')
            payslip_label = payslip.name or payslip.number or str(payslip.id)
            try:
                payslip.action_compute_sheet()
                payslip.action_payslip_done()
            except (UserError, ValidationError) as err:
                error_msg = err.args[0] if err.args else str(err)
                raise UserError(_(
                    "Failed for employee: %(employee)s\n"
                    "Payslip: %(payslip)s\n\n"
                    "%(error)s"
                ) % {
                    'employee': employee_name,
                    'payslip': payslip_label,
                    'error': error_msg,
                }) from err
            except Exception as err:
                raise UserError(_(
                    "Failed for employee: %(employee)s\n"
                    "Payslip: %(payslip)s\n\n"
                    "%(error)s"
                ) % {
                    'employee': employee_name,
                    'payslip': payslip_label,
                    'error': str(err),
                }) from err

        return {'type': 'ir.actions.act_window_close'}
