# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models, _


class SjcDashboard(models.AbstractModel):
    _name = 'sjc.dashboard'
    _description = 'SJC Dashboard Service'

    # ------------------------------------------------------------------ helpers
    def _grace_days(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'ao_sjc_task_management.grace_days', '10'
        )
        try:
            return max(int(raw), 0)
        except (TypeError, ValueError):
            return 10

    def _role(self, user=None):
        user = user or self.env.user
        if user.has_group('ao_sjc_task_management.group_sjc_management'):
            return 'management'
        if user.has_group('ao_sjc_task_management.group_sjc_project_manager'):
            return 'project_manager'
        return 'employee'

    def _is_inbox_user(self, user=None):
        user = user or self.env.user
        return user.has_group('incoming_mail_store.group_incoming_mail_user')

    def _lang_is_ar(self):
        lang = (self.env.user.lang or '').lower()
        return lang.startswith('ar')

    def _tr(self, en, ar):
        """Prefer explicit AR/EN so dashboard labels work even if .po is not loaded."""
        return ar if self._lang_is_ar() else en

    def _avatar_url(self, user_id):
        return '/web/image/res.users/%s/avatar_128' % user_id if user_id else False

    def _empty_po_kpis(self):
        return {
            'total': 0,
            'in_progress': 0,
            'completed': 0,
            'overdue': 0,
        }

    def _po_models(self, team):
        if team == 'makka':
            return 'makka.po.followup', 'makka.po.order', 'po_makka'
        return 'po.followup', 'po.order', 'po_madina'

    def _can_access_team(self, team, role, user):
        if role == 'management':
            return True
        if role == 'project_manager':
            return user.sjc_team == team
        return True  # employee filtered by assignment

    def _is_manager_view(self, role=None):
        role = role or self._role()
        return role in ('management', 'project_manager')

    def _employee_admin_domain(self, user):
        """Requests created by the user or where they are responsible."""
        emp = user.employee_id
        domain = [('created_by', '=', user.id)]
        if emp:
            domain = ['|', ('created_by', '=', user.id), ('employee_ids', 'in', emp.ids)]
        return domain

    def _employee_expense_domain(self, user):
        """Expenses linked to the employee as owner, creator, sender, or manager."""
        domain = [
            '|',
            ('create_uid', '=', user.id),
            ('employee_id.user_id', '=', user.id),
        ]
        Expense = self.env['hr.expense']
        if 'manager' in Expense._fields:
            domain = ['|', ('manager', '=', user.id)] + domain
        if 'sjc_sent_to_manager_by_id' in Expense._fields:
            domain = ['|', ('sjc_sent_to_manager_by_id', '=', user.id)] + domain
        return domain

    def _employee_mail_domain(self, user):
        """Personal emails: shared access OR assignment log.

        Incoming Mail's ``_grant_shared_access`` skips ``shared_user_ids`` when the
        assignee already has the inbox group. SJC employees still need those mails
        on their personal dashboard, so also include ``incoming.mail.assignment``.
        """
        Assignment = self.env['incoming.mail.assignment'].sudo()
        assigned_ids = Assignment.search([('user_id', '=', user.id)]).mapped('mail_id').ids
        if assigned_ids:
            return [
                '|',
                ('shared_user_ids', 'in', user.id),
                ('id', 'in', assigned_ids),
            ]
        return [('shared_user_ids', 'in', user.id)]

    def _to_date(self, value):
        if not value:
            return False
        if isinstance(value, str):
            value = value.split(' ')[0]
        return fields.Date.to_date(value)

    def _effective_due_date(self, sjc_due_date, assigned_date, create_date):
        """Prefer SJC due date; else assigned date; else create date."""
        return (
            self._to_date(sjc_due_date)
            or self._to_date(assigned_date)
            or self._to_date(create_date)
        )

    def _po_status_and_flag(self, disbursement, due, state, today, grace_days):
        if disbursement == 'yes':
            status = 'completed'
        elif due and today > due + timedelta(days=grace_days):
            status = 'overdue'
        else:
            status = 'in_progress'
        # Sent to accounting = assigned or sent_to_portal
        if state in ('assigned', 'sent_to_portal'):
            location = 'accounting'
        else:
            location = 'portal'
        return status, location

    def _location_label(self, location):
        if location == 'accounting':
            return self._tr('Accounting team', 'فريق المحاسبة')
        return self._tr('Portal technicians', 'فنيين البورتال')

    def _status_label(self, status):
        return {
            'completed': self._tr('Done', 'مكتمل'),
            'in_progress': self._tr('Under processing', 'قيد المعالجة'),
            'overdue': self._tr('Late', 'متأخر'),
            'new': self._tr('New', 'جديد'),
        }.get(status, status)

    # ------------------------------------------------------------------ PO page
    def _team_group_xmlid(self, team):
        if team == 'makka':
            return 'ao_makka_po_followup.group_makka_po_followup_user'
        return 'ao_po_followup.group_po_followup_user'

    def _po_team_members(self, team):
        """Users in Madina/Makka group + PO order counts + last assigner."""
        xmlid = self._team_group_xmlid(team)
        group = self.env.ref(xmlid, raise_if_not_found=False)
        if not group:
            return []
        users = self.env['res.users'].sudo().search([
            ('groups_id', 'in', group.id),
            ('share', '=', False),
            ('active', '=', True),
        ], order='name')
        if not users:
            return []

        _followup_model, order_model, _source = self._po_models(team)
        Order = self.env[order_model].sudo().with_context(active_test=False)

        count_groups = Order.read_group(
            [('user_id', 'in', users.ids)],
            ['user_id'],
            ['user_id'],
            lazy=False,
        )
        counts = {
            g['user_id'][0]: g.get('user_id_count') or g.get('__count') or 0
            for g in count_groups if g.get('user_id')
        }

        assigners = {}
        if 'sjc_assigned_by_id' in Order._fields:
            assign_rows = Order.search_read(
                [
                    ('user_id', 'in', users.ids),
                    ('sjc_assigned_by_id', '!=', False),
                ],
                ['user_id', 'sjc_assigned_by_id'],
                order='write_date desc',
            )
            for row in assign_rows:
                uid = row['user_id'][0]
                if uid in assigners:
                    continue
                assigners[uid] = {
                    'id': row['sjc_assigned_by_id'][0],
                    'name': row['sjc_assigned_by_id'][1],
                    'avatar': self._avatar_url(row['sjc_assigned_by_id'][0]),
                }

        members = []
        for u in users:
            members.append({
                'id': u.id,
                'name': u.name,
                'avatar': self._avatar_url(u.id),
                'po_count': counts.get(u.id, 0),
                'assigned_by': assigners.get(u.id),
            })
        members.sort(key=lambda m: m['po_count'], reverse=True)
        return members

    def _po_accounting_senders(self, followup_model):
        Followup = self.env[followup_model].sudo().with_context(active_test=False)
        if 'sjc_sent_to_accounting_by_id' not in Followup._fields:
            return []
        groups = Followup.read_group(
            [
                ('state', 'in', ('assigned', 'sent_to_portal')),
                ('sjc_sent_to_accounting_by_id', '!=', False),
            ],
            ['sjc_sent_to_accounting_by_id'],
            ['sjc_sent_to_accounting_by_id'],
            lazy=False,
        )
        rows = []
        for g in groups:
            if not g.get('sjc_sent_to_accounting_by_id'):
                continue
            uid = g['sjc_sent_to_accounting_by_id'][0]
            rows.append({
                'id': uid,
                'name': g['sjc_sent_to_accounting_by_id'][1],
                'avatar': self._avatar_url(uid),
                'po_count': g.get('sjc_sent_to_accounting_by_id_count') or g.get('__count') or 0,
            })
        rows.sort(key=lambda r: r['po_count'], reverse=True)
        return rows

    def _ui_labels(self):
        L = self._tr
        return {
            'total': L('Total', 'الإجمالي'),
            'in_progress': L('Under processing', 'قيد المعالجة'),
            'completed': L('Done', 'مكتمل'),
            'overdue': L('Late', 'متأخر'),
            'all': L('All', 'الكل'),
            'tasks': L('Tasks', 'المهام'),
            'grace': L('Grace days after due date', 'مهلة الأيام بعد تاريخ الاستحقاق'),
            'empty': L('No data', 'لا توجد بيانات'),
            'portal': L('Portal technicians', 'فنيين البورتال'),
            'accounting': L('Accounting team', 'فريق المحاسبة'),
            'team_members': L('Team members', 'أعضاء الفريق'),
            'accounting_senders': L('Employees who sent to Accounting', 'من أرسل للمحاسبة'),
            'po_sent_count': L('POs sent', 'أوامر مرسلة'),
            'po_assigned_count': L('Assigned POs', 'أوامر مسندة'),
            'assigned_by': L('Assigned by', 'أُسند بواسطة'),
            'loading': L('Loading...', 'جاري التحميل...'),
            'overview': L('Overview', 'نظرة عامة'),
            'makka': L('Makka', 'مكة'),
            'madina': L('Madina', 'المدينة'),
            'mailboxes': L('Mailboxes', 'صناديق البريد'),
            'inbox_staff': L('Incoming mail staff', 'مسؤولو البريد الوارد'),
            'assigned_out': L('Assigned to employees', 'تم إسنادها للموظفين'),
            'assignees': L('Employees with assigned emails', 'الموظفون المعيَّن لهم بريد'),
            'email_count': L('Emails', 'الرسائل'),
            'recent': L('Recent emails', 'أحدث الرسائل'),
            'open_inbox': L('Open inbox', 'فتح صندوق الوارد'),
            'overdue_alert': L('late tasks need attention', 'مهام متأخرة تحتاج متابعة'),
            'send_instructions': L('Send your instructions', 'أرسل تعليماتك'),
            'companies': L('Companies', 'الشركات'),
            'created_by_users': L('Created by', 'أنشئ بواسطة'),
            'responsible_employees': L('Responsible employees', 'الموظف المسؤول'),
            'record_count': L('Records', 'عدد السجلات'),
            'transaction_type': L('Transaction type', 'نوع المعاملة'),
            'company': L('Company', 'الشركة'),
            'new': L('New', 'جديد'),
            'department': L('Department', 'القسم'),
            'end_date': L('End date', 'تاريخ النهاية'),
            'po': L('PO', 'أمر شراء'),
            'wo': L('WO', 'أمر عمل'),
            'due_date': L('Due date', 'تاريخ الاستحقاق'),
            'assignee': L('Assignee', 'المسند إليه'),
            'responsible': L('Responsible', 'المسؤول'),
            'load_more': L('Load more', 'عرض المزيد'),
            'showing': L('Showing', 'المعروض'),
            'go_to_record': L('Go to record', 'الذهاب للسجل'),
            'details': L('Details', 'التفاصيل'),
            'close': L('Close', 'إغلاق'),
            'click_for_details': L('Click for details', 'اضغط لعرض التفاصيل'),
            'departments': L('Departments', 'الأقسام'),
            'managers': L('Assigned to managers', 'مسند للمدير'),
            'sent_to_manager': L('Sent to manager by', 'من أرسل للمدير'),
            'expense_amount': L('Amount', 'المبلغ'),
            'expense_state': L('Status', 'الحالة'),
            'archived': L('Archived', 'مؤرشف'),
            'menu_summary': L('Menus summary', 'ملخص القوائم'),
            'conclusion': L('Conclusion', 'الخلاصة'),
            'employees_sidebar': L('Employees', 'الموظفون'),
            'search_people': L('Search employees...', 'بحث عن موظف...'),
            'menu_po_makka': L('PO - Makka Tasks', 'مهام PO مكة'),
            'menu_po_madina': L('PO - Madina Tasks', 'مهام PO المدينة'),
            'menu_admin_comms': L('Administrative Communications', 'الاتصالات الإدارية'),
            'menu_expenses': L('Expenses', 'المصروفات'),
            'menu_emails': L('Emails Tasks', 'مهام البريد'),
        }

    def _fetch_po_tasks(
        self, team, role, user, today, grace_days,
        limit=None, include_description=False, include_cards=True, overdue_preview_limit=0,
    ):
        """Load PO KPIs and optionally light task cards."""
        if not self._can_access_team(team, role, user):
            return [], self._empty_po_kpis()

        followup_model, order_model, source = self._po_models(team)
        Followup = self.env[followup_model].sudo().with_context(active_test=False)
        Order = self.env[order_model].sudo().with_context(active_test=False)

        domain = []
        if role == 'employee':
            assigned = Order.search([('user_id', '=', user.id)])
            followup_ids = set(assigned.mapped('followup_id').ids)
            # Also include POs this employee sent to accounting (related work).
            if 'sjc_sent_to_accounting_by_id' in Followup._fields:
                sent_ids = Followup.search([
                    ('sjc_sent_to_accounting_by_id', '=', user.id),
                ]).ids
                followup_ids.update(sent_ids)
            if not followup_ids:
                return [], self._empty_po_kpis()
            domain = [('id', 'in', list(followup_ids))]

        fields_list = [
            'name', 'po_number', 'disbursement',
            'sjc_due_date', 'state', 'active', 'create_date',
        ]
        if include_description and include_cards:
            fields_list.append('description')
        if 'assigned_date' in Followup._fields:
            fields_list.append('assigned_date')
        if include_cards and 'work_order_number' in Followup._fields:
            fields_list.append('work_order_number')
        if include_cards and 'employee_name' in Followup._fields:
            fields_list.append('employee_name')
        if include_cards and 'sjc_sent_to_accounting_by_id' in Followup._fields:
            fields_list.append('sjc_sent_to_accounting_by_id')

        search_kwargs = {'order': 'id desc'}
        if limit:
            search_kwargs['limit'] = limit
        rows = Followup.search_read(domain, fields_list, **search_kwargs)
        if not rows:
            return [], self._empty_po_kpis()

        assignees = defaultdict(list)
        if include_cards:
            ids = [r['id'] for r in rows]
            if ids:
                order_rows = Order.search_read(
                    [('followup_id', 'in', ids), ('user_id', '!=', False)],
                    ['followup_id', 'user_id'],
                )
                for o in order_rows:
                    fid = o['followup_id'][0] if o['followup_id'] else False
                    if fid and o['user_id']:
                        assignees[fid].append(o['user_id'][1])

        status_labels = {
            'completed': self._status_label('completed'),
            'in_progress': self._status_label('in_progress'),
            'overdue': self._status_label('overdue'),
            'new': self._status_label('new'),
        }
        location_labels = {
            'accounting': self._location_label('accounting'),
            'portal': self._location_label('portal'),
        }
        po_fallback = self._tr('PO', 'أمر شراء')

        tasks = []
        kpis = self._empty_po_kpis()
        for r in rows:
            due = self._effective_due_date(
                r.get('sjc_due_date'),
                r.get('assigned_date'),
                r.get('create_date'),
            )
            status, location = self._po_status_and_flag(
                r.get('disbursement'), due, r.get('state'), today, grace_days
            )
            kpis['total'] += 1
            if status in kpis:
                kpis[status] += 1

            want_card = include_cards or (
                overdue_preview_limit
                and status == 'overdue'
                and len(tasks) < overdue_preview_limit
            )
            if not want_card:
                continue

            name = r.get('name') or r.get('po_number') or po_fallback
            assignee = ', '.join(assignees.get(r['id'], []))
            if not assignee and r.get('employee_name'):
                assignee = r['employee_name']
            sent_by = ''
            if r.get('sjc_sent_to_accounting_by_id'):
                sent_by = r['sjc_sent_to_accounting_by_id'][1]
            desc = ''
            if include_description:
                desc = (r.get('description') or '')[:240]
            tasks.append({
                'id': '%s,%s' % (followup_model, r['id']),
                'res_model': followup_model,
                'res_id': r['id'],
                'name': name,
                'po_number': r.get('po_number') or '',
                'work_order': r.get('work_order_number') or '',
                'description': desc,
                'source': source,
                'team': team,
                'status': status,
                'status_label': status_labels.get(status, status),
                'location': location,
                'location_label': location_labels.get(location, location),
                'due_date': fields.Date.to_string(due) if due else False,
                'assignee': assignee,
                'sent_by': sent_by,
                'archived': not r.get('active', True),
                'state': r.get('state') or 'draft',
            })
        return tasks, kpis

    @api.model
    def get_po_page_data(self, team):
        """PO Makka / Madina page payload (all KPI records, light cards)."""
        team = 'makka' if team == 'makka' else 'madina'
        user = self.env.user
        role = self._role(user)
        today = fields.Date.context_today(self)
        grace_days = self._grace_days()
        followup_model, _order_model, _source = self._po_models(team)
        tasks, kpis = self._fetch_po_tasks(
            team, role, user, today, grace_days,
            limit=None,
            include_description=False,
            include_cards=True,
        )
        title = {
            'makka': self._tr('PO - Makka Tasks', 'مهام PO مكة'),
            'madina': self._tr('PO - Madina Tasks', 'مهام PO المدينة'),
        }[team]
        if role == 'employee':
            title = self._tr('My tasks — %s', 'مهامي — %s') % title
        show_panels = self._is_manager_view(role)
        return {
            'page': 'po_%s' % team,
            'role': role,
            'user_name': user.name,
            'user_avatar': self._avatar_url(user.id),
            'team': team,
            'title': title,
            'grace_days': grace_days,
            'lang_ar': self._lang_is_ar(),
            'labels': self._ui_labels(),
            'kpis': kpis,
            'tasks': tasks,
            'team_members': self._po_team_members(team) if show_panels else [],
            'accounting_senders': self._po_accounting_senders(followup_model) if show_panels else [],
            'show_people_sidebar': show_panels,
            'show_overview_panels': show_panels,
            'page_size': 80,
        }

    # ------------------------------------------------------------------ Emails
    @api.model
    def get_email_page_data(self):
        user = self.env.user
        role = self._role(user)
        Mail = self.env['incoming.mail'].sudo()
        Assignment = self.env['incoming.mail.assignment'].sudo()
        Users = self.env['res.users'].sudo()
        # SJC employee role = personal mails only (Incoming Mail group ignored here).
        if role == 'employee':
            show_panels = False
            mail_scope = self._employee_mail_domain(user)
        else:
            show_panels = self._is_manager_view(role)
            mail_scope = [] if show_panels else self._employee_mail_domain(user)

        mailbox_groups = Mail.read_group(
            mail_scope, ['mailbox'], ['mailbox'], lazy=False
        )
        mailboxes = []
        total_mails = 0
        for g in mailbox_groups:
            count = g.get('mailbox_count') or g.get('__count') or 0
            total_mails += count
            label = g.get('mailbox') or self._tr('Unknown mailbox', 'صندوق بريد غير معروف')
            mailboxes.append({'name': label, 'count': count})
        mailboxes.sort(key=lambda m: m['count'], reverse=True)

        inbox_staff = []
        assignees = []
        if show_panels:
            inbox_group = self.env.ref(
                'incoming_mail_store.group_incoming_mail_user', raise_if_not_found=False
            )
            inbox_users = Users.browse()
            if inbox_group:
                inbox_users = Users.search([
                    ('groups_id', 'in', inbox_group.id),
                    ('share', '=', False),
                    ('active', '=', True),
                ])
            assign_groups = Assignment.read_group(
                [], ['assigned_by_id'], ['assigned_by_id'], lazy=False
            )
            assign_counts = {
                g['assigned_by_id'][0]: g.get('assigned_by_id_count') or g.get('__count') or 0
                for g in assign_groups if g.get('assigned_by_id')
            }
            for u in inbox_users:
                inbox_staff.append({
                    'id': u.id,
                    'name': u.name,
                    'avatar': self._avatar_url(u.id),
                    'assigned_count': assign_counts.get(u.id, 0),
                })
            inbox_staff.sort(key=lambda r: r['assigned_count'], reverse=True)

            assignee_groups = Assignment.read_group(
                [], ['user_id'], ['user_id'], lazy=False
            )
            self.env.cr.execute("""
                SELECT user_id, COUNT(mail_id)
                FROM incoming_mail_shared_user_rel
                GROUP BY user_id
            """)
            shared_counts = {row[0]: row[1] for row in self.env.cr.fetchall()}
            assignee_ids = set(shared_counts)
            assignee_ids.update(
                g['user_id'][0] for g in assignee_groups if g.get('user_id')
            )
            if assignee_ids:
                users = Users.browse(list(assignee_ids))
                last_assign = {}
                last_rows = Assignment.search_read(
                    [('user_id', 'in', list(assignee_ids))],
                    ['user_id', 'assigned_by_id', 'assigned_date'],
                    order='assigned_date desc',
                )
                for row in last_rows:
                    uid = row['user_id'][0]
                    if uid not in last_assign and row.get('assigned_by_id'):
                        last_assign[uid] = {
                            'id': row['assigned_by_id'][0],
                            'name': row['assigned_by_id'][1],
                            'avatar': self._avatar_url(row['assigned_by_id'][0]),
                        }
                for u in users:
                    count = max(
                        shared_counts.get(u.id, 0),
                        next(
                            (g.get('user_id_count') or g.get('__count') or 0
                             for g in assignee_groups
                             if g.get('user_id') and g['user_id'][0] == u.id),
                            0,
                        ),
                    )
                    assignees.append({
                        'id': u.id,
                        'name': u.name,
                        'avatar': self._avatar_url(u.id),
                        'email_count': count,
                        'assigned_by': last_assign.get(u.id),
                    })
                assignees.sort(key=lambda r: r['email_count'], reverse=True)

        recent = []
        mail_rows = Mail.search_read(
            mail_scope,
            ['name', 'email_from', 'state', 'mailbox', 'shared_user_ids',
             'sjc_assigned_by_id', 'received_date'],
            limit=80,
            order='received_date desc',
        )
        for m in mail_rows:
            assignee_names = []
            if m.get('shared_user_ids'):
                assignee_names = Users.browse(m['shared_user_ids']).mapped('name')
            recent.append({
                'id': 'incoming.mail,%s' % m['id'],
                'res_model': 'incoming.mail',
                'res_id': m['id'],
                'name': m.get('name') or self._tr('No Subject', 'بدون موضوع'),
                'email_from': m.get('email_from') or '',
                'mailbox': m.get('mailbox') or '',
                'state': m.get('state') or 'new',
                'status_label': self._status_label(
                    'completed' if m.get('state') in ('done', 'archived')
                    else ('new' if m.get('state') == 'new' else 'in_progress')
                ),
                'assignees': ', '.join(assignee_names),
                'assigned_by': m['sjc_assigned_by_id'][1] if m.get('sjc_assigned_by_id') else '',
                'received_date': m.get('received_date') or False,
            })

        title = self._tr('Emails Tasks', 'مهام البريد')
        if role == 'employee':
            title = self._tr('My emails', 'بريدي')

        return {
            'page': 'emails',
            'role': role,
            'user_name': user.name,
            'user_avatar': self._avatar_url(user.id),
            'title': title,
            'lang_ar': self._lang_is_ar(),
            'total_mails': total_mails,
            'mailboxes': mailboxes if show_panels else [],
            'inbox_staff': inbox_staff,
            'assignees': assignees,
            'recent': recent,
            # Open inbox is a manager/inbox-staff action, not for employee personal view.
            'can_interact_mail': show_panels and self._is_inbox_user(user),
            'show_people_sidebar': show_panels,
            'show_overview_panels': show_panels,
            'labels': self._ui_labels(),
        }

    # ------------------------------------------------------------------ Admin communications
    def _admin_due_field(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'ao_sjc_task_management.admin_due_field', 'end_date'
        )
        return raw if raw in ('end_date', 'start_date') else 'end_date'

    def _admin_status(self, status, due, today, grace_days):
        """Map employee.request status + due date to SJC dashboard statuses."""
        # Done / منتهية / منتهى
        if status == 'done':
            return 'completed'
        if due and today > due + timedelta(days=grace_days):
            return 'overdue'
        if status == 'in_progress':
            return 'in_progress'
        if status == 'overdue':
            return 'overdue'
        return 'new'

    def _employee_avatar_url(self, employee_id):
        return (
            '/web/image/hr.employee/%s/avatar_128' % employee_id
            if employee_id else False
        )

    def _empty_admin_kpis(self):
        return {
            'total': 0,
            'new': 0,
            'in_progress': 0,
            'completed': 0,
            'overdue': 0,
        }

    @api.model
    def get_admin_comms_page_data(self):
        """الاتصالات الإدارية — employee.request dashboard page."""
        user = self.env.user
        role = self._role(user)
        today = fields.Date.context_today(self)
        grace_days = self._grace_days()
        due_field = self._admin_due_field()
        labels = self._ui_labels()

        empty = {
            'page': 'admin_comms',
            'role': role,
            'user_name': user.name,
            'user_avatar': self._avatar_url(user.id),
            'title': self._tr('Administrative Communications', 'الاتصالات الإدارية'),
            'grace_days': grace_days,
            'due_field': due_field,
            'lang_ar': self._lang_is_ar(),
            'labels': labels,
            'kpis': self._empty_admin_kpis(),
            'companies': [],
            'creators': [],
            'responsibles': [],
            'tasks': [],
            'available': False,
            'show_people_sidebar': False,
            'show_overview_panels': False,
        }

        if 'employee.request' not in self.env:
            return empty

        Request = self.env['employee.request'].sudo().with_context(active_test=False)
        show_panels = self._is_manager_view(role)
        domain = []
        if role == 'employee':
            domain = self._employee_admin_domain(user)

        fields_list = [
            'serial_number', 'company_id', 'partner_id', 'request_topic',
            'transaction_type', 'status', 'employee_ids', 'department',
            'created_by', 'start_date', 'end_date', 'incoming_number', 'active',
        ]
        rows = Request.search_read(domain, fields_list, order='id desc')

        kpis = self._empty_admin_kpis()
        company_counts = defaultdict(lambda: {'id': False, 'name': '', 'count': 0})
        creator_counts = defaultdict(lambda: {'id': False, 'name': '', 'count': 0})
        responsible_counts = defaultdict(lambda: {'id': False, 'name': '', 'count': 0})

        Emp = self.env['hr.employee'].sudo()
        all_emp_ids = set()
        for r in rows:
            all_emp_ids.update(r.get('employee_ids') or [])
        emp_map = {e.id: e for e in Emp.browse(list(all_emp_ids))}

        tasks = []

        for r in rows:
            due = self._to_date(r.get(due_field))
            status = self._admin_status(r.get('status'), due, today, grace_days)
            kpis['total'] += 1
            if status in kpis:
                kpis[status] += 1

            if r.get('company_id'):
                cid, cname = r['company_id'][0], r['company_id'][1]
                company_counts[cid]['id'] = cid
                company_counts[cid]['name'] = cname
                company_counts[cid]['count'] += 1

            if r.get('created_by'):
                uid, uname = r['created_by'][0], r['created_by'][1]
                creator_counts[uid]['id'] = uid
                creator_counts[uid]['name'] = uname
                creator_counts[uid]['count'] += 1

            emp_ids = r.get('employee_ids') or []
            emp_names = []
            for eid in emp_ids:
                emp = emp_map.get(eid)
                if emp:
                    emp_names.append(emp.name)
                    responsible_counts[eid]['id'] = eid
                    responsible_counts[eid]['name'] = emp.name
                    responsible_counts[eid]['count'] += 1

            tx_type = r['transaction_type'][1] if r.get('transaction_type') else ''
            company_name = r['company_id'][1] if r.get('company_id') else ''
            dept = r['department'][1] if r.get('department') else ''
            creator = r['created_by'][1] if r.get('created_by') else ''
            partner = r['partner_id'][1] if r.get('partner_id') else ''

            tasks.append({
                'id': 'employee.request,%s' % r['id'],
                'res_model': 'employee.request',
                'res_id': r['id'],
                'source': 'admin_comms',
                'name': r.get('serial_number') or self._tr('Request', 'معاملة'),
                'po_number': r.get('serial_number') or '',
                'partner': partner,
                'topic': r.get('request_topic') or '',
                'company': company_name,
                'department': dept,
                'transaction_type': tx_type,
                'incoming_number': r.get('incoming_number') or '',
                'status': status,
                'status_label': self._status_label(status),
                'due_date': fields.Date.to_string(due) if due else False,
                'assignee': ', '.join(emp_names),
                'created_by': creator,
                'archived': not r.get('active', True),
            })

        companies = sorted(company_counts.values(), key=lambda x: x['count'], reverse=True)
        creators = []
        responsibles = []
        if show_panels:
            for row in creator_counts.values():
                creators.append({
                    **row,
                    'avatar': self._avatar_url(row['id']),
                })
            creators.sort(key=lambda x: x['count'], reverse=True)

            for row in responsible_counts.values():
                responsibles.append({
                    **row,
                    'avatar': self._employee_avatar_url(row['id']),
                })
            responsibles.sort(key=lambda x: x['count'], reverse=True)

        title = self._tr('Administrative Communications', 'الاتصالات الإدارية')
        if role == 'employee':
            title = self._tr('My administrative tasks', 'مهامي الإدارية')

        return {
            'page': 'admin_comms',
            'role': role,
            'user_name': user.name,
            'user_avatar': self._avatar_url(user.id),
            'title': title,
            'grace_days': grace_days,
            'due_field': due_field,
            'lang_ar': self._lang_is_ar(),
            'labels': labels,
            'kpis': kpis,
            'companies': companies if show_panels else [],
            'creators': creators,
            'responsibles': responsibles,
            'tasks': tasks,
            'available': True,
            'show_people_sidebar': show_panels,
            'show_overview_panels': show_panels,
            'page_size': 80,
        }

    # ------------------------------------------------------------------ Expenses
    def _expense_due_field(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'ao_sjc_task_management.expense_due_field', 'date'
        )
        return raw if raw in ('date', 'sjc_due_date') else 'date'

    def _expense_state_name(self, x_state):
        if not x_state:
            return ''
        if isinstance(x_state, (list, tuple)):
            return (x_state[1] or '').strip()
        return (getattr(x_state, 'name', None) or '').strip()

    def _expense_is_approved_name(self, name):
        name = (name or '').strip()
        tokens = ('تمت الموافقه', 'تمت الموافقة', 'موافقة')
        return any(t in name for t in tokens)

    def _expense_is_sent_name(self, name):
        name = (name or '').strip()
        tokens = ('تم الارسال', 'تم الإرسال', 'تم ارسال', 'ارسال', 'إرسال')
        return any(t in name for t in tokens)

    def _expense_status(self, odoo_state, x_state_name, due, today, grace_days):
        if odoo_state == 'done':
            return 'completed'
        if due and today > due + timedelta(days=grace_days):
            return 'overdue'
        if self._expense_is_approved_name(x_state_name):
            return 'in_progress'
        return 'new'

    @api.model
    def get_expenses_page_data(self):
        """Expenses dashboard — includes archived records."""
        user = self.env.user
        role = self._role(user)
        today = fields.Date.context_today(self)
        grace_days = self._grace_days()
        due_field = self._expense_due_field()
        labels = self._ui_labels()

        empty = {
            'page': 'expenses',
            'role': role,
            'user_name': user.name,
            'user_avatar': self._avatar_url(user.id),
            'title': self._tr('Expenses', 'المصروفات'),
            'grace_days': grace_days,
            'due_field': due_field,
            'lang_ar': self._lang_is_ar(),
            'labels': labels,
            'kpis': self._empty_admin_kpis(),
            'creators': [],
            'managers': [],
            'senders': [],
            'departments': [],
            'tasks': [],
            'available': False,
            'show_people_sidebar': False,
            'show_overview_panels': False,
            'page_size': 80,
        }
        if 'hr.expense' not in self.env:
            return empty

        Expense = self.env['hr.expense'].sudo().with_context(active_test=False)
        show_panels = self._is_manager_view(role)
        domain = []
        if role == 'employee':
            domain = self._employee_expense_domain(user)

        fields_list = [
            'name', 'state', 'active', 'date', 'create_uid', 'create_date',
            'employee_id', 'total_amount', 'company_id',
        ]
        if 'y_section' in Expense._fields:
            fields_list.append('y_section')
        if 'x_state' in Expense._fields:
            fields_list.append('x_state')
        if 'manager' in Expense._fields:
            fields_list.append('manager')
        if 'sjc_due_date' in Expense._fields:
            fields_list.append('sjc_due_date')
        if 'sjc_sent_to_manager_by_id' in Expense._fields:
            fields_list.append('sjc_sent_to_manager_by_id')
        if 'total_amount_currency' in Expense._fields:
            fields_list.append('total_amount_currency')

        rows = Expense.search_read(domain, fields_list, order='id desc')
        kpis = self._empty_admin_kpis()
        creator_counts = defaultdict(lambda: {'id': False, 'name': '', 'count': 0})
        manager_counts = defaultdict(lambda: {'id': False, 'name': '', 'count': 0})
        sender_counts = defaultdict(lambda: {'id': False, 'name': '', 'count': 0})
        dept_counts = defaultdict(lambda: {'id': False, 'name': '', 'count': 0})
        status_labels = {
            'completed': self._status_label('completed'),
            'in_progress': self._status_label('in_progress'),
            'overdue': self._status_label('overdue'),
            'new': self._status_label('new'),
        }
        tasks = []

        for r in rows:
            x_name = self._expense_state_name(r.get('x_state'))
            due_raw = r.get(due_field) if due_field in r else r.get('date')
            if due_field == 'sjc_due_date' and not due_raw:
                due_raw = r.get('date')
            due = self._to_date(due_raw)
            status = self._expense_status(
                r.get('state'), x_name, due, today, grace_days
            )
            kpis['total'] += 1
            if status in kpis:
                kpis[status] += 1

            if r.get('create_uid'):
                uid, uname = r['create_uid'][0], r['create_uid'][1]
                creator_counts[uid]['id'] = uid
                creator_counts[uid]['name'] = uname
                creator_counts[uid]['count'] += 1

            if r.get('manager'):
                mid, mname = r['manager'][0], r['manager'][1]
                manager_counts[mid]['id'] = mid
                manager_counts[mid]['name'] = mname
                manager_counts[mid]['count'] += 1

            # Sent to manager = who forwarded the expense to a manager.
            # 1) tracked field  2) الحالة تم الارسال  3) historical: has manager → create_uid
            sender = r.get('sjc_sent_to_manager_by_id')
            if sender:
                sid, sname = sender[0], sender[1]
                sender_counts[sid]['id'] = sid
                sender_counts[sid]['name'] = sname
                sender_counts[sid]['count'] += 1
            elif r.get('create_uid') and (
                self._expense_is_sent_name(x_name) or r.get('manager')
            ):
                sid, sname = r['create_uid'][0], r['create_uid'][1]
                sender_counts[sid]['id'] = sid
                sender_counts[sid]['name'] = sname
                sender_counts[sid]['count'] += 1

            if r.get('y_section'):
                did, dname = r['y_section'][0], r['y_section'][1]
                dept_counts[did]['id'] = did
                dept_counts[did]['name'] = dname
                dept_counts[did]['count'] += 1

            amount = r.get('total_amount_currency')
            if amount is None:
                amount = r.get('total_amount') or 0
            employee = r['employee_id'][1] if r.get('employee_id') else ''
            company = r['company_id'][1] if r.get('company_id') else ''
            creator = r['create_uid'][1] if r.get('create_uid') else ''
            manager_name = r['manager'][1] if r.get('manager') else ''
            dept = r['y_section'][1] if r.get('y_section') else ''

            tasks.append({
                'id': 'hr.expense,%s' % r['id'],
                'res_model': 'hr.expense',
                'res_id': r['id'],
                'source': 'expenses',
                'name': r.get('name') or self._tr('Expense', 'مصروف'),
                'po_number': r.get('name') or '',
                'status': status,
                'status_label': status_labels.get(status, status),
                'x_state': x_name,
                'due_date': fields.Date.to_string(due) if due else False,
                'amount': amount,
                'employee': employee,
                'company': company,
                'department': dept,
                'created_by': creator,
                'manager': manager_name,
                'assignee': manager_name,
                'archived': not r.get('active', True),
            })

        def _people(rows_map):
            out = []
            for row in rows_map.values():
                out.append({**row, 'avatar': self._avatar_url(row['id'])})
            out.sort(key=lambda x: x['count'], reverse=True)
            return out

        departments = sorted(dept_counts.values(), key=lambda x: x['count'], reverse=True)
        title = self._tr('Expenses', 'المصروفات')
        if role == 'employee':
            title = self._tr('My expenses', 'مصروفاتي')

        return {
            'page': 'expenses',
            'role': role,
            'user_name': user.name,
            'user_avatar': self._avatar_url(user.id),
            'title': title,
            'grace_days': grace_days,
            'due_field': due_field,
            'lang_ar': self._lang_is_ar(),
            'labels': labels,
            'kpis': kpis,
            'creators': _people(creator_counts) if show_panels else [],
            'managers': _people(manager_counts) if show_panels else [],
            'senders': _people(sender_counts) if show_panels else [],
            'departments': departments if show_panels else [],
            'tasks': tasks,
            'available': True,
            'show_people_sidebar': show_panels,
            'show_overview_panels': show_panels,
            'page_size': 80,
        }

    # ------------------------------------------------------------------ Overview dashboard (fast)
    def _format_menu_conclusion(self, kpis, extra=None):
        """Short one-line conclusion for a menu summary card."""
        labels = self._ui_labels()
        parts = [
            '%s: %s' % (labels['total'], kpis.get('total', 0)),
        ]
        if 'new' in kpis and kpis.get('new') is not None:
            parts.append('%s: %s' % (labels['new'], kpis.get('new', 0)))
        parts.extend([
            '%s: %s' % (labels['in_progress'], kpis.get('in_progress', 0)),
            '%s: %s' % (labels['completed'], kpis.get('completed', 0)),
            '%s: %s' % (labels['overdue'], kpis.get('overdue', 0)),
        ])
        if extra:
            parts.append(extra)
        return ' — '.join(parts)

    def _quick_admin_kpis(self, today, grace_days, domain=None):
        if 'employee.request' not in self.env:
            return self._empty_admin_kpis()
        Request = self.env['employee.request'].sudo().with_context(active_test=False)
        due_field = self._admin_due_field()
        fields_list = ['status', 'create_date']
        for fname in (due_field, 'end_date', 'start_date'):
            if fname in Request._fields and fname not in fields_list:
                fields_list.append(fname)
        rows = Request.search_read(domain or [], fields_list)
        kpis = self._empty_admin_kpis()
        for r in rows:
            due = (
                self._to_date(r.get(due_field))
                or self._to_date(r.get('end_date'))
                or self._to_date(r.get('create_date'))
            )
            status = self._admin_status(r.get('status'), due, today, grace_days)
            kpis['total'] += 1
            if status in kpis:
                kpis[status] += 1
        return kpis

    def _quick_expense_kpis(self, today, grace_days, domain=None):
        if 'hr.expense' not in self.env:
            return self._empty_admin_kpis()
        Expense = self.env['hr.expense'].sudo().with_context(active_test=False)
        due_field = self._expense_due_field()
        fields_list = ['state', 'date', 'create_date']
        if 'x_state' in Expense._fields:
            fields_list.append('x_state')
        if 'sjc_due_date' in Expense._fields:
            fields_list.append('sjc_due_date')
        rows = Expense.search_read(domain or [], fields_list)
        kpis = self._empty_admin_kpis()
        for r in rows:
            due_raw = r.get(due_field) if due_field in r else r.get('date')
            if due_field == 'sjc_due_date' and not due_raw:
                due_raw = r.get('date')
            due = self._to_date(due_raw)
            x_name = self._expense_state_name(r.get('x_state'))
            status = self._expense_status(r.get('state'), x_name, due, today, grace_days)
            kpis['total'] += 1
            if status in kpis:
                kpis[status] += 1
        return kpis

    @api.model
    def get_dashboard_data(self):
        """Fast overview: KPI counts + short conclusion per menu."""
        user = self.env.user
        role = self._role(user)
        today = fields.Date.context_today(self)
        grace_days = self._grace_days()

        makka_tasks, makka_kpis = [], self._empty_po_kpis()
        madina_tasks, madina_kpis = [], self._empty_po_kpis()
        if self._can_access_team('makka', role, user) or role == 'employee':
            makka_tasks, makka_kpis = self._fetch_po_tasks(
                'makka', role, user, today, grace_days,
                include_cards=False, overdue_preview_limit=10,
            )
        if self._can_access_team('madina', role, user) or role == 'employee':
            madina_tasks, madina_kpis = self._fetch_po_tasks(
                'madina', role, user, today, grace_days,
                include_cards=False, overdue_preview_limit=10,
            )

        admin_domain = self._employee_admin_domain(user) if role == 'employee' else None
        expense_domain = self._employee_expense_domain(user) if role == 'employee' else None
        admin_kpis = self._quick_admin_kpis(today, grace_days, domain=admin_domain)
        expense_kpis = self._quick_expense_kpis(today, grace_days, domain=expense_domain)

        Mail = self.env['incoming.mail'].sudo()
        if role == 'employee':
            mail_domain_base = self._employee_mail_domain(user)
            mail_count = Mail.search_count(mail_domain_base)
            mail_done = Mail.search_count(mail_domain_base + [('state', 'in', ('done', 'archived'))])
            mail_new = Mail.search_count(mail_domain_base + [('state', '=', 'new')])
            mail_progress = Mail.search_count(mail_domain_base + [('state', '=', 'in_progress')])
        elif role == 'management' or self._is_inbox_user(user):
            mail_count = Mail.search_count([])
            mail_done = Mail.search_count([('state', 'in', ('done', 'archived'))])
            mail_new = Mail.search_count([('state', '=', 'new')])
            mail_progress = Mail.search_count([('state', '=', 'in_progress')])
        else:
            mail_domain_base = self._employee_mail_domain(user)
            mail_count = Mail.search_count(mail_domain_base)
            mail_done = Mail.search_count(mail_domain_base + [('state', 'in', ('done', 'archived'))])
            mail_new = Mail.search_count(mail_domain_base + [('state', '=', 'new')])
            mail_progress = Mail.search_count(mail_domain_base + [('state', '=', 'in_progress')])

        mail_kpis = {
            'total': mail_count,
            'new': mail_new,
            'in_progress': mail_progress,
            'completed': mail_done,
            'overdue': 0,
        }

        kpis = {
            'total': (
                makka_kpis['total'] + madina_kpis['total']
                + admin_kpis['total'] + expense_kpis['total'] + mail_count
            ),
            'in_progress': (
                makka_kpis['in_progress'] + madina_kpis['in_progress']
                + admin_kpis['in_progress'] + expense_kpis['in_progress'] + mail_progress
            ),
            'completed': (
                makka_kpis['completed'] + madina_kpis['completed']
                + admin_kpis['completed'] + expense_kpis['completed'] + mail_done
            ),
            'overdue': (
                makka_kpis['overdue'] + madina_kpis['overdue']
                + admin_kpis['overdue'] + expense_kpis['overdue']
            ),
            'mail': mail_count,
            'new': admin_kpis.get('new', 0) + expense_kpis.get('new', 0) + mail_new,
        }
        overdue_preview = [
            t for t in (makka_tasks + madina_tasks) if t['status'] == 'overdue'
        ][:15]

        def _progress(kpi):
            total = kpi.get('total') or 0
            done = kpi.get('completed') or 0
            return int(round(done * 100.0 / total)) if total else 0

        menu_summaries = [
            {
                'key': 'po_makka',
                'title': self._tr('PO - Makka Tasks', 'مهام PO مكة'),
                'kpis': makka_kpis,
                'progress': _progress(makka_kpis),
                'conclusion': self._format_menu_conclusion(makka_kpis),
            },
            {
                'key': 'po_madina',
                'title': self._tr('PO - Madina Tasks', 'مهام PO المدينة'),
                'kpis': madina_kpis,
                'progress': _progress(madina_kpis),
                'conclusion': self._format_menu_conclusion(madina_kpis),
            },
            {
                'key': 'admin_comms',
                'title': self._tr('Administrative Communications', 'الاتصالات الإدارية'),
                'kpis': admin_kpis,
                'progress': _progress(admin_kpis),
                'conclusion': self._format_menu_conclusion(admin_kpis),
            },
            {
                'key': 'expenses',
                'title': self._tr('Expenses', 'المصروفات'),
                'kpis': expense_kpis,
                'progress': _progress(expense_kpis),
                'conclusion': self._format_menu_conclusion(expense_kpis),
            },
            {
                'key': 'emails',
                'title': self._tr('Emails Tasks', 'مهام البريد'),
                'kpis': mail_kpis,
                'progress': _progress(mail_kpis),
                'conclusion': self._format_menu_conclusion(mail_kpis),
            },
        ]

        return {
            'page': 'dashboard',
            'role': role,
            'user_name': user.name,
            'user_avatar': self._avatar_url(user.id),
            'user_team': user.sjc_team or False,
            'grace_days': grace_days,
            'lang_ar': self._lang_is_ar(),
            'labels': self._ui_labels(),
            'kpis': kpis,
            'branches': {
                'makka': {**makka_kpis, 'team': 'makka', 'progress': _progress(makka_kpis)},
                'madina': {**madina_kpis, 'team': 'madina', 'progress': _progress(madina_kpis)},
            },
            'menu_summaries': menu_summaries,
            'overdue': overdue_preview,
            'title': (
                self._tr('My tasks overview', 'نظرة عامة على مهامي')
                if role == 'employee'
                else self._tr('Overview', 'نظرة عامة')
            ),
            'can_see_mail': mail_count > 0,
            'can_interact_mail': role != 'employee' and self._is_inbox_user(user),
            'show_people_sidebar': False,
            'show_overview_panels': False,
        }

    @api.model
    def get_page_data(self, page='dashboard'):
        """Single entry used by OWL — loads only the requested page."""
        page = page or 'dashboard'
        if page == 'po_makka':
            return self.get_po_page_data('makka')
        if page == 'po_madina':
            return self.get_po_page_data('madina')
        if page == 'emails':
            return self.get_email_page_data()
        if page == 'admin_comms':
            return self.get_admin_comms_page_data()
        if page == 'expenses':
            return self.get_expenses_page_data()
        return self.get_dashboard_data()
