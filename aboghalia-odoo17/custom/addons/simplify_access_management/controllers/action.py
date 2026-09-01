from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home, ensure_db
import odoo

class Home(Home):

    @http.route('/web', type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        ensure_db()
        if request.session.uid:
            try:
                user = request.env.user.browse(request.session.uid)
                if user.exists() and (not kw.get('debug') or kw.get('debug') != "0"):
                    cids_cookie = request.httprequest.cookies.get('cids')
                    cids = int(cids_cookie.split(',')[0]) if (cids_cookie and cids_cookie.split(',')[0].isdigit()) else (request.env.company.id if request.env.company else False)
                    if cids:
                        access_management = request.env['access.management'].sudo().search([
                            ('active','=',True),
                            ('company_ids','in',cids),
                            ('disable_debug_mode','=',True),
                            ('user_ids','in',user.id)
                        ], limit=1)
                        if access_management and access_management.id:
                            return request.redirect('/web?debug=0')
            except Exception:
                pass
        return super().web_client(s_action=s_action, **kw)
