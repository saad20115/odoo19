# -*- coding: utf-8 -*-


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.hr_payroll_community.hooks import (
        _disable_payslip_multi_company_rules,
    )
    _disable_payslip_multi_company_rules(env)
