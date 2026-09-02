# -*- coding: utf-8 -*-

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_PAYSLIP_MULTI_COMPANY_RULE_NAMES = (
    'Payroll multi company',
    'Payslips batches of my Company',
)


def _disable_payslip_multi_company_rules(env):
    """Hard-delete multi-company record rules on hr.payslip (SQL + ORM)."""
    cr = env.cr
    # Bulletproof: remove by name even if XML id / ORM cache is stale.
    cr.execute(
        """
        DELETE FROM ir_rule
        WHERE name = ANY(%s)
          AND model_id IN (
              SELECT id FROM ir_model WHERE model = 'hr.payslip'
          )
        RETURNING id, name
        """,
        [list(_PAYSLIP_MULTI_COMPANY_RULE_NAMES)],
    )
    deleted = cr.fetchall()
    if deleted:
        _logger.info(
            "Deleted hr.payslip multi-company rules: %s", deleted
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
        try:
            env.registry.clear_cache()
        except Exception:
            pass

    # Also catch any leftover "multi company" payslip rules by ORM.
    Rule = env['ir.rule'].sudo().with_context(active_test=False)
    payslip_model = env['ir.model'].sudo().search(
        [('model', '=', 'hr.payslip')], limit=1
    )
    if not payslip_model:
        return
    leftovers = Rule.search([
        ('model_id', '=', payslip_model.id),
        '|',
        ('name', 'in', list(_PAYSLIP_MULTI_COMPANY_RULE_NAMES)),
        ('name', 'ilike', 'multi company'),
    ])
    if leftovers:
        _logger.info("Unlinking leftover payslip multi-company rules: %s", leftovers.mapped('name'))
        leftovers.unlink()
        try:
            env.registry.clear_cache()
        except Exception:
            pass


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _disable_payslip_multi_company_rules(env)
