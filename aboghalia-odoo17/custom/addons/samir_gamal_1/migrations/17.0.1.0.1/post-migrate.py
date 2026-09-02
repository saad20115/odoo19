# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.samir_gamal_1.hooks import cleanup_leftover_employee_request_ui
    cleanup_leftover_employee_request_ui(env)
