# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class SjcDashboardController(http.Controller):

    @http.route('/sjc/dashboard/data', type='json', auth='user')
    def dashboard_data(self):
        return request.env['sjc.dashboard'].get_dashboard_data()
