# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.session import Session


class AoUserLoginSession(Session):

    @http.route('/web/session/authenticate', type='json', auth="none")
    def authenticate(self, db, login, password, base_location=None):
        result = super().authenticate(db, login, password, base_location=base_location)
        uid = request.session.uid
        if uid:
            user = request.env['res.users'].sudo().browse(uid)
            if user.exists():
                request.session['ao_force_employee_company'] = True
                company = user._ao_apply_login_company()
                if company:
                    request.future_response.set_cookie('cids', str(company.id), path='/')
        return result
