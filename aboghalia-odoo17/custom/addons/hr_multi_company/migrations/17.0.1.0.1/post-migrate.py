# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Delete payslip multi-company rule left from older module versions."""
    cr.execute(
        """
        DELETE FROM ir_rule
        WHERE name IN (
            'Payroll multi company',
            'Payslips batches of my Company'
        )
        AND model_id IN (
            SELECT id FROM ir_model WHERE model = 'hr.payslip'
        )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE model = 'ir.rule'
          AND name IN (
              'payroll_multi_company_rule',
              'hr_payroll_batches_company'
          )
        """
    )
