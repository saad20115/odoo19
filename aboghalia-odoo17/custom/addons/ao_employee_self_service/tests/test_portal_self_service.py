# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestEmployeeSelfServicePortal(TransactionCase):

    def setUp(self):
        super(TestEmployeeSelfServicePortal, self).setUp()
        self.employee = self.env['hr.employee'].create({
            'name': 'اختبار موظف الخدمات الذاتية',
            'work_email': 'test_self_service@example.com',
            'job_title': 'مهندس برمجيات',
        })
        self.test_user = self.env['res.users'].create({
            'name': 'مستخدم الخدمات الذاتية',
            'login': 'test_self_service_user',
            'email': 'test_self_service@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.employee.user_id = self.test_user.id

    def test_01_get_employee_portal_data(self):
        """Test data aggregation API for employee self service portal."""
        data = self.env['hr.employee.self.service'].with_user(self.test_user).get_employee_portal_data()
        self.assertTrue(data.get('has_employee'))
        self.assertEqual(data.get('employee_id'), self.employee.id)
        self.assertEqual(data.get('job_title'), 'مهندس برمجيات')
        self.assertIn('tasks', data)
        self.assertIn('profile', data)

    def test_02_leave_balance_computation(self):
        """Test calculation of leave balances and remaining days."""
        data = self.env['hr.employee.self.service'].with_user(self.test_user).get_employee_portal_data()
        self.assertIn('total_remaining_leaves', data)
        self.assertIn('leave_balances', data)

    def test_03_create_portal_task(self):
        """Test creating personal and team tasks for self service portal."""
        task = self.env['hr.employee.portal.task'].create({
            'name': 'اختبار مهمة جديدة',
            'description': 'شرح تفاصيل المهمة',
            'employee_id': self.employee.id,
            'assigned_to_id': self.employee.id,
            'task_type': 'personal',
            'priority': '2',
        })
        self.assertEqual(task.name, 'اختبار مهمة جديدة')
        self.assertEqual(task.state, 'todo')
        task.action_set_in_progress()
        self.assertEqual(task.state, 'in_progress')
        task.action_set_done()
        self.assertEqual(task.state, 'done')

    def test_04_profile_update(self):
        """Test updating employee profile contact information."""
        self.employee.sudo().write({
            'mobile_phone': '0501112233',
            'work_phone': '101',
        })
        self.assertEqual(self.employee.mobile_phone, '0501112233')
