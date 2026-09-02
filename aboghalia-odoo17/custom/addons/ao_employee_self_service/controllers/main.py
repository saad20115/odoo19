# -*- coding: utf-8 -*-

import json
import base64
from datetime import datetime
from odoo import http, fields, _
from odoo.http import request


class EmployeeSelfServicePortalController(http.Controller):

    @http.route('/portal/self-service', type='http', auth='user', website=True)
    def render_employee_portal(self, **kwargs):
        """Render the standalone Employee Self-Services Web Portal."""
        data = request.env['hr.employee.self.service'].get_employee_portal_data()
        
        leave_types = request.env['hr.leave.type'].sudo().search([])
        leave_types_data = [{'id': lt.id, 'name': lt.name} for lt in leave_types]

        # Fetch root app menus for the App Switcher dropdown
        app_menus = []
        try:
            root_menus = request.env['ir.ui.menu'].sudo().search(
                [('parent_id', '=', False)],
                order='sequence, id',
                limit=24,
            )
            for menu in root_menus:
                icon_data = ''
                if menu.web_icon_data:
                    icon_data = menu.web_icon_data.decode('utf-8') if isinstance(menu.web_icon_data, bytes) else str(menu.web_icon_data)
                app_menus.append({
                    'id': menu.id,
                    'name': menu.name,
                    'web_icon_data': icon_data,
                })
        except Exception:
            pass

        values = {
            'portal_data': data,
            'portal_data_json': json.dumps(data),
            'leave_types': leave_types_data,
            'user': request.env.user,
            'app_menus': app_menus,
        }
        return request.render('ao_employee_self_service.employee_portal_template', values)

    @http.route('/portal/self-service/check_in_out', type='json', auth='user', methods=['POST'], csrf=False)
    def check_in_out(self, latitude=None, longitude=None, accuracy=None, location_name=None):
        """Toggle Check-In / Check-Out for the logged-in employee via AJAX."""
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            employee = request.env['hr.employee'].sudo().search([('work_email', '=', user.email)], limit=1)
            
        if not employee:
            return {'success': False, 'message': _('لا يوجد سجل موظف مقترن بحساب المستخدم الحالي.')}

        now = fields.Datetime.now()
        
        try:
            open_attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], order='check_in desc', limit=1)
            
            att_state = getattr(employee, 'attendance_state', False)
            is_currently_in = bool(open_attendance or att_state == 'checked_in')

            if not is_currently_in:
                vals = {
                    'employee_id': employee.id,
                    'check_in': now,
                }
                if hasattr(request.env['hr.attendance'], 'latitude'):
                    vals.update({
                        'latitude': latitude,
                        'longitude': longitude,
                    })
                attendance = request.env['hr.attendance'].sudo().create(vals)
                msg = _('تم تسجيل الحضور بنجاح!')
                if location_name:
                    msg += f" ({location_name})"
                return {
                    'success': True,
                    'is_checked_in': True,
                    'message': msg,
                    'check_in_time': now.strftime('%Y-%m-%d %H:%M:%S'),
                }
            else:
                if open_attendance:
                    open_attendance.write({
                        'check_out': now,
                    })
                    msg = _('تم تسجيل الانصراف بنجاح!')
                    if location_name:
                        msg += f" ({location_name})"
                    return {
                        'success': True,
                        'is_checked_in': False,
                        'message': msg,
                        'check_out_time': now.strftime('%Y-%m-%d %H:%M:%S'),
                    }
                else:
                    return {'success': False, 'message': _('لم يتم العثور على سجل حضور مفتوح للانصراف.')}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route('/portal/self-service/submit_leave', type='json', auth='user', methods=['POST'], csrf=False)
    def submit_leave_request(self, holiday_status_id, date_from, date_to, description=None):
        """Submit a new Leave Request from the Web Portal."""
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            return {'success': False, 'message': _('سجل الموظف غير موجود.')}

        try:
            dt_from = datetime.strptime(date_from, '%Y-%m-%d')
            dt_to = datetime.strptime(date_to, '%Y-%m-%d')
            
            leave_vals = {
                'name': description or _('طلب إجازة عبر البوابة الإلكترونية'),
                'employee_id': employee.id,
                'holiday_status_id': int(holiday_status_id),
                'request_date_from': dt_from.date(),
                'request_date_to': dt_to.date(),
                'date_from': dt_from,
                'date_to': dt_to,
            }
            leave = request.env['hr.leave'].sudo().create(leave_vals)
            
            if hasattr(leave, 'action_confirm'):
                leave.action_confirm()
                
            return {
                'success': True,
                'message': _('تم تقديم طلب الإجازة بنجاح وهو قيد الاعتماد.'),
                'leave_id': leave.id,
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route('/portal/self-service/approve_leave', type='json', auth='user', methods=['POST'], csrf=False)
    def approve_leave(self, leave_id, action_type='approve'):
        """Manager 1-Click Approve / Refuse Leave Request."""
        try:
            leave = request.env['hr.leave'].sudo().browse(int(leave_id))
            if not leave.exists():
                return {'success': False, 'message': _('طلب الإجازة غير موجود.')}

            if action_type == 'approve':
                if hasattr(leave, 'action_approve'):
                    leave.action_approve()
                else:
                    leave.write({'state': 'validate'})
                return {'success': True, 'message': _('تمت الموافقة على طلب الإجازة بنجاح.')}
            else:
                if hasattr(leave, 'action_refuse'):
                    leave.action_refuse()
                else:
                    leave.write({'state': 'refuse'})
                return {'success': True, 'message': _('تم رفض طلب الإجازة.')}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route('/portal/self-service/task/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_task(self, name, description=None, task_type='personal', assigned_to_id=None, priority='1', date_deadline=None):
        """Create a new Task (personal or team assignment) from portal."""
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            return {'success': False, 'message': _('سجل الموظف غير موجود.')}

        try:
            assignee = employee.id
            if task_type == 'team' and assigned_to_id:
                assignee = int(assigned_to_id)

            task_vals = {
                'name': name,
                'description': description or '',
                'employee_id': employee.id,
                'assigned_to_id': assignee,
                'task_type': task_type,
                'priority': priority,
                'state': 'todo',
            }
            if date_deadline:
                task_vals['date_deadline'] = datetime.strptime(date_deadline, '%Y-%m-%d').date()

            task = request.env['hr.employee.portal.task'].sudo().create(task_vals)
            return {
                'success': True,
                'message': _('تم إضافة المهمة بنجاح!'),
                'task_id': task.id,
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route('/portal/self-service/task/update_state', type='json', auth='user', methods=['POST'], csrf=False)
    def update_task_state(self, task_id, state):
        """Update Task State (todo, in_progress, done, cancel)."""
        try:
            task = request.env['hr.employee.portal.task'].sudo().browse(int(task_id))
            if not task.exists():
                return {'success': False, 'message': _('المهمة غير موجودة.')}

            task.write({'state': state})
            return {
                'success': True,
                'message': _('تم تحديث حالة المهمة بنجاح!'),
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route('/portal/self-service/profile/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_profile(self, mobile_phone=None, work_phone=None, private_email=None, emergency_contact=None, emergency_phone=None, street=None, city=None, avatar_base64=None):
        """Update Employee Self-Profile details and photo."""
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            return {'success': False, 'message': _('سجل الموظف غير موجود.')}

        try:
            vals = {}
            if mobile_phone is not None:
                vals['mobile_phone'] = mobile_phone
            if work_phone is not None:
                vals['work_phone'] = work_phone
            if private_email is not None and hasattr(employee, 'private_email'):
                vals['private_email'] = private_email
            if emergency_contact is not None and hasattr(employee, 'emergency_contact'):
                vals['emergency_contact'] = emergency_contact
            if emergency_phone is not None and hasattr(employee, 'emergency_phone'):
                vals['emergency_phone'] = emergency_phone
            if street is not None and hasattr(employee, 'street'):
                vals['street'] = street
            if city is not None and hasattr(employee, 'city'):
                vals['city'] = city
            if avatar_base64:
                # Strip header if data URI
                if ',' in avatar_base64:
                    avatar_base64 = avatar_base64.split(',')[1]
                vals['image_1920'] = avatar_base64

            employee.sudo().write(vals)
            return {
                'success': True,
                'message': _('تم تحديث بيانات الملف الشخصي بنجاح!'),
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}
