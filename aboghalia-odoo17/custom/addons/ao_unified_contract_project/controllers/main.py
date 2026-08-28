# -*- coding: utf-8 -*-

import json
from odoo import http, _
from odoo.http import request


class UnifiedContractMapController(http.Controller):

    @http.route('/unified_contract/map_view', type='http', auth='user', website=True)
    def render_map_view(self, **kwargs):
        work_orders = request.env['unified.contract.work.order'].search([])
        map_data = []
        for wo in work_orders:
            lat = 21.5433
            lng = 39.1728
            if wo.coordinate_y:
                try:
                    lat = float(wo.coordinate_y.strip())
                except (ValueError, TypeError):
                    lat = 21.5433
            if wo.coordinate_x:
                try:
                    lng = float(wo.coordinate_x.strip())
                except (ValueError, TypeError):
                    lng = 39.1728

            map_data.append({
                'id': wo.id,
                'number': wo.work_order_number or wo.name or '',
                'project': wo.project_id.name if wo.project_id else _('غير محدد'),
                'contractor': wo.contractor_id.name if wo.contractor_id else _('غير محدد'),
                'stage': wo.stage_id.name if wo.stage_id else _('غير محدد'),
                'stage_5_status': wo.stage_5_status or 'not_started',
                'progress': wo.progress or 0.0,
                'lat': lat,
                'lng': lng,
                'state': wo.state or 'draft',
            })
            
        return request.render('ao_unified_contract_project.work_order_map_dashboard_template', {
            'map_data_json': json.dumps(map_data),
            'work_orders': work_orders,
        })
