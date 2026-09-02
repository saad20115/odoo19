# -*- coding: utf-8 -*-

from datetime import date, datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HrEmployeeSelfService(models.AbstractModel):
    _name = 'hr.employee.self.service'
    _description = 'Employee Self Service Portal Aggregation Model'

    @api.model
    def get_employee_portal_data(self, user_id=None):
        """Aggregate all dashboard portal data for the logged-in employee."""
        if not user_id:
            user_id = self.env.user.id
            
        user = self.env['res.users'].browse(user_id)
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        
        if not employee:
            employee = self.env['hr.employee'].sudo().search([('work_email', '=', user.email)], limit=1)
            
        if not employee:
            return {
                'has_employee': False,
                'user_name': user.name,
                'message': _('لا يوجد سجل موظف مقترن بحساب المستخدم الحالي. يرجى مراجعة إدارة الموارد البشرية.')
            }

        today = fields.Date.today()
        now = fields.Datetime.now()
        
        # Check backend access permission (System admin, HR user, HR manager)
        has_backend_access = user.has_group('base.group_system') or user.has_group('hr.group_hr_user') or user.has_group('hr.group_hr_manager')
        
        # 1. Profile Header & Detailed Profile Data
        avatar_url = f'/web/image?model=hr.employee&field=avatar_128&id={employee.id}'
        manager_name = employee.parent_id.name if employee.parent_id else _('غير محدد')
        department_name = employee.department_id.name if employee.department_id else _('عام')
        job_title = employee.job_title or (employee.job_id.name if employee.job_id else False) or _('موظف')
        emp_code = getattr(employee, 'registration_number', False) or getattr(employee, 'barcode', False) or f"EMP-{employee.id}"

        work_email = employee.work_email or user.email or ''
        private_email = getattr(employee, 'private_email', False) or getattr(employee, 'email', '') or ''
        work_phone = employee.work_phone or ''
        mobile_phone = employee.mobile_phone or ''
        emergency_contact = getattr(employee, 'emergency_contact', '') or ''
        emergency_phone = getattr(employee, 'emergency_phone', '') or ''
        street = getattr(employee, 'street', '') or ''
        city = getattr(employee, 'city', '') or ''

        profile_details = {
            'id': employee.id,
            'name': employee.name,
            'job_title': job_title,
            'department_name': department_name,
            'manager_name': manager_name,
            'emp_code': emp_code,
            'avatar_url': avatar_url,
            'work_email': work_email,
            'private_email': private_email,
            'work_phone': work_phone,
            'mobile_phone': mobile_phone,
            'emergency_contact': emergency_contact,
            'emergency_phone': emergency_phone,
            'street': street,
            'city': city,
        }

        # 2. Attendance Status & Today Worked Hours
        open_attendance = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], order='check_in desc', limit=1)
        
        att_state = getattr(employee, 'attendance_state', False)
        is_checked_in = bool(open_attendance or att_state == 'checked_in')
        
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        attendances_today = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', today_start),
            ('check_in', '<=', today_end)
        ], order='check_in desc')
        
        last_att = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id)
        ], order='check_in desc', limit=1)

        last_check_in = False
        last_check_in_time_str = ''
        last_check_out_time_str = ''

        if last_att and last_att.check_in:
            dt_in = fields.Datetime.context_timestamp(self, last_att.check_in)
            last_check_in = dt_in.strftime('%Y-%m-%d %H:%M:%S')
            period = 'ص' if dt_in.strftime('%p') == 'AM' else 'م'
            last_check_in_time_str = dt_in.strftime(f'%I:%M {period}')

        if last_att and last_att.check_out:
            dt_out = fields.Datetime.context_timestamp(self, last_att.check_out)
            period = 'ص' if dt_out.strftime('%p') == 'AM' else 'م'
            last_check_out_time_str = dt_out.strftime(f'%I:%M {period}')

        today_hours = sum(att.worked_hours for att in attendances_today) if attendances_today else 0.0

        # 3. Leave Balance Summary
        leave_types = self.env['hr.leave.type'].sudo().search([])
        leave_balance_list = []
        total_remaining_leaves = 0.0
        
        for lt in leave_types:
            allocations = self.env['hr.leave.allocation'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', lt.id),
                ('state', '=', 'validate')
            ])
            total_allocated = sum(al.number_of_days for al in allocations)
            
            leaves_taken = self.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', lt.id),
                ('state', '=', 'validate')
            ])
            total_taken = sum(l.number_of_days for l in leaves_taken)
            remaining = total_allocated - total_taken
            if remaining > 0:
                total_remaining_leaves += remaining
                
            leave_balance_list.append({
                'id': lt.id,
                'name': lt.name,
                'allocated': total_allocated,
                'taken': total_taken,
                'remaining': max(0.0, remaining),
            })

        # 4. My Submitted Requests
        my_leaves = self.env['hr.leave'].sudo().search([('employee_id', '=', employee.id)], order='create_date desc', limit=15)
        my_requests_list = []
        for l in my_leaves:
            my_requests_list.append({
                'id': l.id,
                'type': _('طلب إجازة'),
                'title': f"{l.holiday_status_id.name} ({l.number_of_days} أيام)",
                'date_from': l.date_from.strftime('%Y-%m-%d') if l.date_from else '',
                'date_to': l.date_to.strftime('%Y-%m-%d') if l.date_to else '',
                'state': l.state,
                'state_label': dict(l._fields['state'].selection).get(l.state, l.state),
                'create_date': l.create_date.strftime('%Y-%m-%d %H:%M'),
            })

        # 5. Pending Approvals & Team Statistics (For Managers)
        subordinate_employees = self.env['hr.employee'].sudo().search([('parent_id', '=', employee.id)])
        team_members_list = [{'id': emp.id, 'name': emp.name, 'job_title': emp.job_title or emp.job_id.name or ''} for emp in subordinate_employees]
        
        team_present_count = 0
        if subordinate_employees:
            team_present_count = sum(1 for emp in subordinate_employees if getattr(emp, 'is_checked_in', False))

        pending_approvals = []
        if subordinate_employees:
            pending_leaves = self.env['hr.leave'].sudo().search([
                ('employee_id', 'in', subordinate_employees.ids),
                ('state', 'in', ['confirm', 'validate1'])
            ], order='create_date desc', limit=10)
            
            for pl in pending_leaves:
                pending_approvals.append({
                    'id': pl.id,
                    'type': _('طلب إجازة موظف'),
                    'employee_name': pl.employee_id.name,
                    'title': f"{pl.holiday_status_id.name} ({pl.number_of_days} أيام)",
                    'date_from': pl.date_from.strftime('%Y-%m-%d') if pl.date_from else '',
                    'date_to': pl.date_to.strftime('%Y-%m-%d') if pl.date_to else '',
                    'state': pl.state,
                    'create_date': pl.create_date.strftime('%Y-%m-%d %H:%M'),
                })

        # 6. Tasks Box (Personal & Team Tasks)
        tasks_domain = ['|', ('employee_id', '=', employee.id), ('assigned_to_id', '=', employee.id)]
        if subordinate_employees:
            tasks_domain = ['|', '|', ('employee_id', '=', employee.id), ('assigned_to_id', '=', employee.id), ('employee_id', 'in', subordinate_employees.ids)]
            
        portal_tasks = self.env['hr.employee.portal.task'].sudo().search(tasks_domain, order='priority desc, create_date desc')
        tasks_list = []
        todo_count = 0
        in_progress_count = 0
        done_count = 0
        team_pending_tasks_count = 0
        
        priority_labels = {'0': _('منخفضة'), '1': _('متوسطة'), '2': _('عالية'), '3': _('عاجلة جداً')}
        state_labels = {'todo': _('قيد الانتظار'), 'in_progress': _('جاري العمل'), 'done': _('مكتملة'), 'cancel': _('ملغاة')}
        
        for t in portal_tasks:
            if t.state == 'todo':
                todo_count += 1
            elif t.state == 'in_progress':
                in_progress_count += 1
            elif t.state == 'done':
                done_count += 1

            if t.task_type == 'team' and t.state in ['todo', 'in_progress']:
                team_pending_tasks_count += 1
                
            tasks_list.append({
                'id': t.id,
                'name': t.name,
                'description': t.description or '',
                'task_type': t.task_type,
                'task_type_label': _('شخصية') if t.task_type == 'personal' else _('فريق'),
                'creator_name': t.employee_id.name,
                'assignee_name': t.assigned_to_id.name if t.assigned_to_id else t.employee_id.name,
                'priority': t.priority,
                'priority_label': priority_labels.get(t.priority, t.priority),
                'date_deadline': t.date_deadline.strftime('%Y-%m-%d') if t.date_deadline else '',
                'state': t.state,
                'state_label': state_labels.get(t.state, t.state),
                'is_my_task': t.assigned_to_id.id == employee.id,
            })

        # 7. Smart Notifications & Alerts
        alerts_list = []
        warning_days = 30
        threshold_date = today + timedelta(days=warning_days)
        
        for doc_field, doc_label in [
            ('identification_id', _('الهوية الوطنية / الإقامة')),
            ('passport_id', _('جواز السفر')),
        ]:
            val = getattr(employee, doc_field, False)
            exp_date = getattr(employee, f"{doc_field}_expiry", False) or getattr(employee, 'expiry_date', False)
            if exp_date and isinstance(exp_date, date) and exp_date <= threshold_date:
                days_left = (exp_date - today).days
                alerts_list.append({
                    'id': f"doc_{doc_field}",
                    'level': 'danger' if days_left <= 7 else 'warning',
                    'icon': 'fa-id-card',
                    'title': f"{_('اقتراب انتهاء')} {doc_label}",
                    'message': f"{_('تنتهي في')} {exp_date.strftime('%Y-%m-%d')} ({days_left} {_('أيام متبقية')})",
                })

        alerts_list.append({
            'id': 'welcome_notice',
            'level': 'info',
            'icon': 'fa-bullhorn',
            'title': _('مرحباً بك في البوابة الإلكترونية للخدمات الذاتية'),
            'message': _('يمكنك التنقل من القائمة الجانبية لإدارة المهام، تقديم الطلبات وتحديث ملفك الشخصي.'),
        })

        return {
            'has_employee': True,
            'has_backend_access': has_backend_access,
            'employee_id': employee.id,
            'name': employee.name,
            'job_title': job_title,
            'department_name': department_name,
            'manager_name': manager_name,
            'emp_code': emp_code,
            'avatar_url': avatar_url,
            'work_email': work_email,
            'private_email': private_email,
            'work_phone': work_phone,
            'mobile_phone': mobile_phone,
            'emergency_contact': emergency_contact,
            'emergency_phone': emergency_phone,
            'street': street,
            'city': city,
            'profile': profile_details,
            'is_checked_in': is_checked_in,
            'today_hours': round(today_hours, 2),
            'last_check_in': last_check_in,
            'last_check_in_time_str': last_check_in_time_str,
            'last_check_out_time_str': last_check_out_time_str,
            'leave_balance': total_remaining_leaves,
            'total_remaining_leaves': total_remaining_leaves,
            'leave_balances': leave_balance_list,
            'my_requests': my_requests_list,
            'pending_approvals': pending_approvals,
            'team_members': team_members_list,
            'team_stats': {
                'total_members': len(team_members_list),
                'present_members': team_present_count,
                'pending_tasks': team_pending_tasks_count,
                'pending_approvals': len(pending_approvals),
            },
            'tasks': tasks_list,
            'task_stats': {
                'total': len(tasks_list),
                'todo': todo_count,
                'in_progress': in_progress_count,
                'done': done_count,
            },
            'alerts': alerts_list,
            'is_manager': bool(subordinate_employees),
        }
