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
    )
    payslip_ids = fields.Many2many(
        'hr.payslip',
        string='Payslips',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Prefer dedicated key: active_ids is often cleared when the dialog opens
        payslip_ids = (
            self.env.context.get('selected_payslip_ids')
            or self.env.context.get('active_ids')
            or []
        )
        payslips = self.env['hr.payslip'].browse(payslip_ids).exists()
        if payslips:
            res['payslip_ids'] = [(6, 0, payslips.ids)]
            res['employee_ids'] = [(6, 0, payslips.mapped('employee_id').ids)]
            res.setdefault('date_from', payslips[0].date_from)
            res.setdefault('date_to', payslips[0].date_to)
        return res

    @api.onchange('payslip_ids')
    def _onchange_payslip_ids(self):
        self.employee_ids = self.payslip_ids.mapped('employee_id')

    def _get_draft_payslips_to_process(self):
        """Validate selection/dates, apply period, return draft payslips."""
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
        return draft_payslips

    def _process_payslips(self, draft_payslips, process_fn):
        """Process payslips one-by-one so errors can name the failing employee."""
        for payslip in draft_payslips:
            employee_name = payslip.employee_id.display_name or _('Unknown')
            payslip_label = payslip.name or payslip.number or str(payslip.id)
            try:
                process_fn(payslip)
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

    def action_compute(self):
        """Apply period, then Compute Sheet only (same as form Compute Sheet)."""
        draft_payslips = self._get_draft_payslips_to_process()
        self._process_payslips(draft_payslips, lambda p: p.action_compute_sheet())
        return {'type': 'ir.actions.act_window_close'}

    def action_confirm(self):
        """Apply period, then Confirm only (same as form Confirm)."""
        draft_payslips = self._get_draft_payslips_to_process()
        self._process_payslips(draft_payslips, lambda p: p.action_payslip_done())
        return {'type': 'ir.actions.act_window_close'}
