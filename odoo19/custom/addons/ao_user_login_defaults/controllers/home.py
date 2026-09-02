# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home


class AoUserLoginHome(Home):

    def _ao_set_login_company_cookie(self, response, uid):
        if not uid or not response:
            return response
        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists():
            return response
        request.session['ao_force_employee_company'] = True
        company = user._ao_apply_login_company()
        if company:
            response.set_cookie('cids', str(company.id), path='/')
        return response

    @http.route()
    def web_login(self, redirect=None, **kw):
        response = super().web_login(redirect=redirect, **kw)
        if request.params.get('login_success') and request.session.uid:
            response = self._ao_set_login_company_cookie(response, request.session.uid)
        return response
