# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        user = request.env.user
        if not request.session.uid or user._is_public():
            return info

        info['home_action_id'] = user._ao_safe_home_action_id()

        # Once per session after login: force Employee company into cookie + payload.
        # Cleared afterward so manual company switch still works.
        if request.session.pop('ao_force_employee_company', None):
            company = user._ao_apply_login_company()
            if company:
                request.future_response.set_cookie('cids', str(company.id), path='/')
                companies = info.get('user_companies') or {}
                if companies:
                    companies['current_company'] = company.id
                    info['user_companies'] = companies
        return info
