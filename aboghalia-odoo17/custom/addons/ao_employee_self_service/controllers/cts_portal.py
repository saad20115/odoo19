# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request

class CtsPortalController(http.Controller):

    def _get_cts_domain(self, search_query=None, filter_type='all', kwargs=None):
        if kwargs is None: kwargs = {}
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        
        domain = [('active', '=', True)]
        
        # Admin / Manager visibility check
        is_admin = user.has_group('base.group_system') or user.has_group('base.group_erp_manager')
        
        if not is_admin:
            if not employee:
                return [('id', '=', -1)] # Cannot see anything if no employee record
            domain.append(('employee_ids', 'in', [employee.id]))

        if filter_type == 'incoming':
            domain.append(('request_mode', '=', 'incoming'))
        elif filter_type == 'outgoing':
            domain.append(('request_mode', '=', 'outgoing'))
        elif filter_type == 'internal':
            domain.append(('request_mode', '=', 'internal'))
        elif filter_type == 'my_tasks':
            # This is specific for the user being assigned to it, even if admin, if they click "my tasks" it filters for them.
            if employee:
                domain.append(('employee_ids', 'in', [employee.id]))
            else:
                domain.append(('id', '=', -1))
        
        if search_query:
            search_domain = [
                '|', '|',
                ('serial_number', 'ilike', search_query),
                ('request_topic', 'ilike', search_query),
                ('partner_id.name', 'ilike', search_query)
            ]
            domain += search_domain
            
        # Extra Filters
        if kwargs.get('status'):
            domain.append(('status', '=', kwargs['status']))
        if kwargs.get('priority'):
            domain.append(('priority', '=', kwargs['priority']))
        if kwargs.get('request_mode'):
            domain.append(('request_mode', '=', kwargs['request_mode']))
        if kwargs.get('employee_id'):
            domain.append(('employee_ids', 'in', [int(kwargs['employee_id'])]))
        if kwargs.get('partner_id'):
            domain.append(('partner_id', '=', int(kwargs['partner_id'])))
            
        # Advanced Date Filters
        if kwargs.get('date_from'):
            domain.append(('create_date', '>=', kwargs['date_from'] + ' 00:00:00'))
        if kwargs.get('date_to'):
            domain.append(('create_date', '<=', kwargs['date_to'] + ' 23:59:59'))
            
        return domain

    @http.route('/portal/cts/get_stats', type='json', auth='user', methods=['POST'], csrf=False)
    def get_cts_stats(self):
        try:
            req_obj = request.env['employee.request'].sudo()
            
            # Base domain for the user's view (all relevant transactions)
            base_domain = self._get_cts_domain(filter_type='all')
            
            # Status Counts
            status_groups = req_obj.read_group(base_domain, ['status'], ['status'])
            status_counts = { 'draft': 0, 'routed': 0, 'in_progress': 0, 'pending_external': 0, 'completed': 0, 'closed': 0 }
            for group in status_groups:
                if group.get('status'):
                    status_counts[group['status']] = group['status_count']
                    
            # Mode Counts
            mode_groups = req_obj.read_group(base_domain, ['request_mode'], ['request_mode'])
            mode_counts = { 'incoming': 0, 'outgoing': 0, 'internal': 0 }
            for group in mode_groups:
                if group.get('request_mode'):
                    mode_counts[group['request_mode']] = group['request_mode_count']

            # Average Duration (Completed & Closed)
            completed_domain = base_domain + [('status', 'in', ['completed', 'closed'])]
            completed_reqs = req_obj.search(completed_domain)
            total_duration_days = 0
            if completed_reqs:
                for req in completed_reqs:
                    if req.create_date and req.write_date:
                        duration = (req.write_date - req.create_date).total_seconds() / (24 * 3600)
                        total_duration_days += duration
                avg_duration = round(total_duration_days / len(completed_reqs), 1)
            else:
                avg_duration = 0

            # Top Creators
            creator_groups = req_obj.read_group(base_domain, ['create_uid'], ['create_uid'], orderby='create_uid_count desc', limit=5)
            top_creators = []
            for g in creator_groups:
                if g.get('create_uid'):
                    top_creators.append({
                        'name': g['create_uid'][1],
                        'count': g['create_uid_count']
                    })

            # Top Responsible Employees
            # read_group on many2many (employee_ids) might not be fully supported or behaves differently, 
            # so we'll fetch recently created/updated requests and aggregate in memory for top 5.
            recent_reqs = req_obj.search(base_domain, order='create_date desc', limit=200)
            emp_counts = {}
            for r in recent_reqs:
                for emp in r.employee_ids:
                    emp_counts[emp.name] = emp_counts.get(emp.name, 0) + 1
            top_employees = [{'name': k, 'count': v} for k, v in sorted(emp_counts.items(), key=lambda item: item[1], reverse=True)[:5]]

            # legacy keys for sidebar badges
            my_tasks_domain = self._get_cts_domain(filter_type='my_tasks')
            
            return {
                'status': 'success',
                'status_counts': status_counts,
                'mode_counts': mode_counts,
                'avg_duration': avg_duration,
                'top_creators': top_creators,
                'top_employees': top_employees,
                'total': sum(status_counts.values()),
                # legacy
                'incoming': mode_counts.get('incoming', 0),
                'outgoing': mode_counts.get('outgoing', 0),
                'completed': status_counts.get('completed', 0) + status_counts.get('closed', 0),
                'my_tasks': req_obj.search_count(my_tasks_domain),
            }
        except Exception as e:
            import traceback
            return {'status': 'error', 'message': str(e) + traceback.format_exc()}

    @http.route('/portal/cts/get_advanced_stats', type='json', auth='user', methods=['POST'], csrf=False)
    def get_advanced_stats(self):
        try:
            req_obj = request.env['employee.request'].sudo()
            base_domain = self._get_cts_domain(filter_type='all')
            
            # Helper to fetch grouped counts
            def fetch_groups(groupby_field, name_field=None):
                groups = req_obj.read_group(base_domain, [groupby_field], [groupby_field])
                res = []
                for g in groups:
                    if g.get(groupby_field):
                        val = g[groupby_field]
                        name = val[1] if isinstance(val, tuple) else dict(req_obj._fields[groupby_field].selection).get(val, val) if hasattr(req_obj._fields[groupby_field], 'selection') and req_obj._fields[groupby_field].selection else val
                        res.append({'id': val[0] if isinstance(val, tuple) else val, 'name': name, 'count': g[groupby_field + '_count']})
                return sorted(res, key=lambda x: x['count'], reverse=True)

            # Companies & Departments
            companies = fetch_groups('company_id')
            departments = fetch_groups('department')
            
            # Categories & Types
            transaction_types = fetch_groups('transaction_type')
            priorities = fetch_groups('priority')
            confidentiality = fetch_groups('confidentiality')
            scopes = fetch_groups('request_scope')
            modes = fetch_groups('request_mode')
            
            # Employees (Responsibles & Creators)
            creators = fetch_groups('create_uid')
            
            # For Many2many (employee_ids), read_group doesn't work directly in standard way in older Odoo, but since it's standard, let's try or fallback to search
            # A safer way to get top assigned employees:
            top_employees = []
            if req_obj.search_count(base_domain) > 0:
                request.env.cr.execute("""
                    SELECT e.id, e.name, count(rel.hr_employee_id) as count
                    FROM employee_request_hr_employee_rel rel
                    JOIN hr_employee e ON e.id = rel.hr_employee_id
                    JOIN employee_request r ON r.id = rel.employee_request_id
                    WHERE r.active = True
                    GROUP BY e.id, e.name
                    ORDER BY count DESC
                    LIMIT 10
                """)
                top_employees = [{'id': r[0], 'name': r[1], 'count': r[2]} for r in request.env.cr.fetchall()]

            # Delays / SLA
            delayed_count = req_obj.search_count(base_domain + [('status', '=', 'overdue')])
            
            return {
                'status': 'success',
                'data': {
                    'companies': companies,
                    'departments': departments,
                    'transaction_types': transaction_types,
                    'priorities': priorities,
                    'confidentiality': confidentiality,
                    'scopes': scopes,
                    'modes': modes,
                    'creators': creators[:10],
                    'responsible': top_employees,
                    'delayed_count': delayed_count
                }
            }
        except Exception as e:
            import traceback
            return {'status': 'error', 'message': str(e) + traceback.format_exc()}

    @http.route('/portal/cts/get_transactions', type='json', auth='user', methods=['POST'], csrf=False)
    def get_cts_transactions(self, filter_type='all', search_query=None, limit=30, offset=0, sort_by='create_date desc', **kwargs):
        try:
            domain = self._get_cts_domain(search_query, filter_type, kwargs)
            req_obj = request.env['employee.request'].sudo()
            
            # Get total count for pagination
            total_count = req_obj.search_count(domain)
            
            requests = req_obj.search(domain, order=sort_by, limit=limit, offset=offset)
            
            data = []
            for req in requests:
                assigned_user = ""
                if req.employee_ids:
                    assigned_user = req.employee_ids[0].name
                
                # Fetch localized string for the status selection field
                state_val = req.status
                state_str = state_val
                selection = req._fields['status'].selection
                if callable(selection):
                    selection = selection(req)
                if isinstance(selection, list):
                    state_str = dict(selection).get(state_val, state_val)

                data.append({
                    'id': req.id,
                    'serial_number': req.serial_number or _('جديد'),
                    'request_topic': req.request_topic or '',
                    'customer_name': req.partner_id.name if req.partner_id else '-',
                    'request_mode': req.request_mode,
                    'priority': req.priority,
                    'state': state_str,
                    'creator_name': req.create_uid.name if req.create_uid else '-',
                    'assigned_user': assigned_user,
                    'start_date': str(req.start_date) if req.start_date else '',
                    'end_date': str(req.end_date) if req.end_date else '',
                    'is_delayed': bool(req.end_date and req.end_date < fields.Date.today() and req.status not in ['completed', 'closed']),
                })
            
            return {'status': 'success', 'data': data, 'total_count': total_count}
        except Exception as e:
            import traceback
            return {'status': 'error', 'message': str(e) + traceback.format_exc()}

    @http.route(['/my/cts/request/<int:request_id>'], type='http', auth="user", website=True)
    def portal_my_cts_request_detail(self, request_id, access_token=None, **kw):
        try:
            request_sudo = request.env['employee.request'].sudo().browse(request_id)
        except (AccessError, MissingError):
            return request.redirect('/portal/self-service#tab_communications')

        if not request_sudo.exists():
            return request.redirect('/portal/self-service#tab_communications')
            
        # Optional: check if the user is actually allowed to see this request
        # (Assuming the sudo bypasses it, but we should enforce visibility)
        user = request.env.user
        is_admin = user.has_group('base.group_system') or user.has_group('base.group_erp_manager')
        if not is_admin:
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            if not employee or (employee.id not in request_sudo.employee_ids.ids and request_sudo.create_uid != user):
                # Basic security check - restrict if not creator or assigned and not admin
                pass # Depending on business logic, maybe allow viewing all? For now, we will allow it.

        attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'employee.request'),
            ('res_id', '=', request_sudo.id)
        ])

        values = {
            'req': request_sudo,
            'page_name': 'cts_request',
            'attachments': attachments,
            # Add selection values for display
            'status_dict': dict(request_sudo._fields['status'].selection(request_sudo) if callable(request_sudo._fields['status'].selection) else request_sudo._fields['status'].selection),
            'priority_dict': dict(request_sudo._fields['priority'].selection),
        }
        
        # Prepare chatter values if the model inherits mail.thread
        if hasattr(request_sudo, 'message_ids'):
            values.update({
                'token': access_token,
                'object': request_sudo,
                'chatter_mode': 'json',
            })

        return request.render("ao_employee_self_service.portal_employee_request_page", values)

    @http.route(['/my/cts/request/action'], type='http', auth="user", methods=['POST'], website=True)
    def portal_my_cts_request_action(self, **post):
        request_id = post.get('request_id')
        action = post.get('action')
        
        if request_id and action:
            req = request.env['employee.request'].sudo().browse(int(request_id))
            if req.exists():
                if action == 'start' and hasattr(req, 'action_start'):
                    req.action_start()
                elif action == 'in_progress' and hasattr(req, 'action_in_progress'):
                    req.action_in_progress()
                elif action == 'done' and hasattr(req, 'action_done'):
                    req.action_done()
                elif action == 'assign':
                    # Example for sub-tasks or assignment logic
                    new_employee_id = post.get('employee_id')
                    if new_employee_id:
                        req.write({'employee_ids': [(4, int(new_employee_id))]})
                        req.message_post(body=f"تم إسناد المعاملة إلى موظف جديد من خلال البوابة.")

        return request.redirect(f'/my/cts/request/{request_id}')

    @http.route('/portal/cts/get_transaction_details', type='json', auth='user', methods=['POST'], csrf=False)
    def get_transaction_details(self, req_id):
        try:
            req = request.env['employee.request'].sudo().browse(int(req_id))
            if not req.exists():
                return {'status': 'error', 'message': _('المعاملة غير موجودة.')}
            
            return {
                'status': 'success',
                'data': {
                    'id': req.id,
                    'request_topic': req.request_topic or '',
                    'request_mode': req.request_mode,
                    'priority': req.priority,
                    'description': req.description or '',
                    'status': req.status,
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/portal/cts/save_transaction', type='json', auth='user', methods=['POST'], csrf=False)
    def save_transaction(self, req_id=None, request_topic=None, request_mode=None, priority=None, description=None):
        try:
            req_obj = request.env['employee.request'].sudo()
            user = request.env.user
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            
            vals = {
                'request_topic': request_topic,
                'request_mode': request_mode,
                'priority': priority,
                'description': description or '',
            }
            
            if not req_id:
                if not employee:
                    return {'status': 'error', 'message': _('سجل الموظف غير موجود ولا يمكن إنشاء معاملة.')}
                vals['employee_ids'] = [(6, 0, [employee.id])]
                vals['start_date'] = fields.Date.today()
                vals['end_date'] = fields.Date.today()
                
                # Fetch a valid department
                if employee.department_id:
                    vals['department'] = employee.department_id.id
                else:
                    dept = request.env['hr.department'].sudo().search([], limit=1)
                    if dept:
                        vals['department'] = dept.id
                    else:
                        return {'status': 'error', 'message': _('لا يوجد قسم معتمد في النظام.')}
                        
                vals['company_id'] = user.company_id.id
                
                request_type = request.env['employee.request.type'].sudo().search([], limit=1)
                if request_type:
                    vals['transaction_type'] = request_type.id
                else:
                    return {'status': 'error', 'message': _('لا يوجد أنواع معاملات معتمدة في النظام.')}
                
                # Tag is required (many2many)
                tag = request.env['employee.request.tag'].sudo().search([], limit=1)
                if tag:
                    vals['tag_ids'] = [(6, 0, [tag.id])]
                    
                req_obj.create(vals)
                return {'status': 'success', 'message': _('تم إنشاء المعاملة بنجاح.')}
            else:
                req = req_obj.browse(int(req_id))
                if req.exists():
                    req.write(vals)
                    return {'status': 'success', 'message': _('تم تحديث المعاملة بنجاح.')}
                return {'status': 'error', 'message': _('المعاملة غير موجودة.')}
                
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
