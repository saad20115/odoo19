from odoo import http
from odoo.http import request
from datetime import datetime

class CtsPortal(http.Controller):

    @http.route('/portal/cts/get_transactions', type='json', auth='user')
    def get_cts_transactions(self, filter_type='all', **kwargs):
        domain = []
        if filter_type == 'incoming':
            domain = [('request_mode', '=', 'incoming')]
        elif filter_type == 'outgoing':
            domain = [('request_mode', '=', 'outgoing')]
        elif filter_type == 'my_tasks':
            domain = [('assigned_user_id', '=', request.env.user.id), ('state', 'in', ['routed', 'in_progress', 'pending_external'])]
        
        requests = request.env['employee.request'].search(domain, order='date_start desc')
        
        data = []
        for req in requests:
            data.append({
                'id': req.id,
                'serial_number': req.serial_number or 'جديد',
                'request_topic': req.request_topic,
                'request_mode': req.request_mode,
                'priority': req.priority,
                'state': req.state,
                'date_start': req.date_start.strftime('%Y-%m-%d') if req.date_start else '',
                'assigned_user': req.assigned_user_id.name if req.assigned_user_id else '',
            })
        return {'status': 'success', 'data': data}

    @http.route('/portal/cts/get_stats', type='json', auth='user')
    def get_cts_stats(self, **kwargs):
        Env = request.env['employee.request']
        incoming = Env.search_count([('request_mode', '=', 'incoming')])
        outgoing = Env.search_count([('request_mode', '=', 'outgoing')])
        my_tasks = Env.search_count([('assigned_user_id', '=', request.env.user.id), ('state', 'in', ['routed', 'in_progress'])])
        completed = Env.search_count([('state', '=', 'completed')])
        
        return {
            'status': 'success',
            'incoming': incoming,
            'outgoing': outgoing,
            'my_tasks': my_tasks,
            'completed': completed
        }

    @http.route('/portal/cts/get_transaction_details', type='json', auth='user')
    def get_cts_transaction_details(self, req_id, **kwargs):
        req = request.env['employee.request'].browse(int(req_id))
        if not req.exists():
            return {'status': 'error', 'message': 'المعاملة غير موجودة'}
        
        return {
            'status': 'success',
            'data': {
                'id': req.id,
                'request_topic': req.request_topic or '',
                'request_mode': req.request_mode or 'internal',
                'priority': req.priority or 'medium',
                'date_start': req.date_start.strftime('%Y-%m-%d') if req.date_start else '',
                'date_end': req.date_end.strftime('%Y-%m-%d') if req.date_end else '',
                'description': req.description or '',
                'partner_id': req.partner_id.id if req.partner_id else False,
            }
        }

    @http.route('/portal/cts/save_transaction', type='json', auth='user')
    def save_cts_transaction(self, **post):
        req_id = post.get('req_id')
        vals = {
            'request_topic': post.get('request_topic'),
            'request_mode': post.get('request_mode', 'internal'),
            'priority': post.get('priority', 'medium'),
            'description': post.get('description'),
        }
        if post.get('date_end'):
            vals['date_end'] = post.get('date_end')
        if post.get('partner_id'):
            vals['partner_id'] = int(post.get('partner_id'))
            
        try:
            if req_id:
                req = request.env['employee.request'].browse(int(req_id))
                req.write(vals)
            else:
                req = request.env['employee.request'].create(vals)
            return {'status': 'success', 'message': 'تم الحفظ بنجاح'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/portal/cts/delete_transaction', type='json', auth='user')
    def delete_cts_transaction(self, req_id, **kwargs):
        req = request.env['employee.request'].browse(int(req_id))
        if not req.exists():
            return {'status': 'error', 'message': 'المعاملة غير موجودة'}
        if req.state != 'draft':
            return {'status': 'error', 'message': 'لا يمكن حذف المعاملة إلا في حالة المسودة'}
        try:
            req.unlink()
            return {'status': 'success', 'message': 'تم الحذف بنجاح'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
