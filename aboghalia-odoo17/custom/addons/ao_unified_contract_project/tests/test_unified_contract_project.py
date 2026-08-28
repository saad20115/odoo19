# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestUnifiedContractProject(TransactionCase):

    def setUp(self):
        super(TestUnifiedContractProject, self).setUp()
        stages = self.env['unified.contract.stage'].search([], order='sequence asc, id asc')
        if len(stages) >= 2:
            self.stage_1 = stages[0]
            self.stage_2 = stages[1]
        else:
            self.stage_1 = self.env['unified.contract.stage'].create({
                'name': 'المعاينة والدراسة',
                'sequence': 10,
                'stage_progress': 20.0,
            })
            self.stage_2 = self.env['unified.contract.stage'].create({
                'name': 'التنفيذ الميداني',
                'sequence': 20,
                'stage_progress': 60.0,
            })
        self.project = self.env['unified.contract.project'].create({
            'name': 'مشروع العقد الموحد تجريبي',
            'code': 'TEST-UC-2026-001',
            'stage_id': self.stage_1.id,
        })
        self.test_user = self.env['res.users'].create({
            'name': 'مهندس تجريبي',
            'login': 'test_engineer_uc',
            'email': 'test_engineer@example.com',
            'groups_id': [(6, 0, [self.env.ref('ao_unified_contract_project.group_unified_contract_user').id])]
        })

    def test_project_creation_and_stage_position(self):
        """ Test project creation, code assignment, and stage position computation """
        self.assertEqual(self.project.code, 'TEST-UC-2026-001')
        self.assertTrue(self.project.is_first_stage)
        self.assertFalse(self.project.is_last_stage)

    def test_project_next_stage_action(self):
        """ Test advancing project to next stage """
        current_seq = self.stage_1.sequence
        next_stages = self.env['unified.contract.stage'].search([('sequence', '>', current_seq)], order='sequence asc, id asc')
        self.project.action_next_stage()
        if next_stages:
            self.assertEqual(self.project.stage_id.id, next_stages[0].id)

    def test_revert_stage_permission_restriction(self):
        """ Verify non-admin user without permission profile option cannot revert stage """
        project_user_env = self.project.with_user(self.test_user)
        with self.assertRaises(UserError):
            project_user_env.write({'stage_id': self.stage_1.id})
