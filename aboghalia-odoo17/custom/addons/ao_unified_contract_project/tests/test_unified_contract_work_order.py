# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestUnifiedContractWorkOrder(TransactionCase):

    def setUp(self):
        super(TestUnifiedContractWorkOrder, self).setUp()
        self.project = self.env['unified.contract.project'].create({
            'name': 'مشروع توريد وتنفيد الكابلات الإضافي',
            'code': 'UC-2026-TEST-WO-2',
        })
        self.stage_exec = self.env['unified.contract.work.order.stage'].search([('sequence', '=', 3)], limit=1)
        if not self.stage_exec:
            self.stage_exec = self.env['unified.contract.work.order.stage'].create({
                'name': 'مرحلة التنفيذ الميداني',
                'sequence': 3,
                'stage_progress': 50.0,
            })
        self.stage_close_4 = self.env['unified.contract.work.order.stage'].search([('sequence', '=', 4)], limit=1)
        if not self.stage_close_4:
            self.stage_close_4 = self.env['unified.contract.work.order.stage'].create({
                'name': 'مرحلة الإغلاق والتوثيق',
                'sequence': 4,
                'stage_progress': 90.0,
            })
        self.stage_final_5 = self.env['unified.contract.work.order.stage'].search([('sequence', '=', 5)], limit=1)
        if not self.stage_final_5:
            self.stage_final_5 = self.env['unified.contract.work.order.stage'].create({
                'name': 'المرحلة النهائية والفوترة',
                'sequence': 5,
                'stage_progress': 100.0,
            })
        self.work_order = self.env['unified.contract.work.order'].create({
            'name': '1236254002',
            'work_order_number': '1236254002',
            'project_id': self.project.id,
            'stage_id': self.stage_exec.id,
            'execution_progress': 40.0,
        })
        self.test_user = self.env['res.users'].create({
            'name': 'مستخدم الصلاحيات المحدودة',
            'login': 'test_limited_user_uc',
            'email': 'limited_user@example.com',
            'groups_id': [(6, 0, [self.env.ref('ao_unified_contract_project.group_unified_contract_user').id])]
        })

    def test_work_order_write_orm_validation(self):
        """ Verify write() raises ValidationError when skipping execution without 100% progress """
        with self.assertRaises(ValidationError):
            self.work_order.write({'stage_id': self.stage_close_4.id})

    def test_google_maps_url_coordinates_parser(self):
        """ Test parsing coordinates from standard Google Maps URLs """
        url = 'https://www.google.com/maps/search/?api=1&query=21.5433,39.1728'
        lat, lng = self.env['unified.contract.work.order']._parse_google_maps_url_coordinates(url)
        self.assertEqual(lat, '21.5433')
        self.assertEqual(lng, '39.1728')

    def test_permit_status_date_sync(self):
        """ Test automatic permit status assignment upon permit data entry """
        issued_status = self.env['unified.contract.permit.status'].search([('name', 'ilike', 'ساري')], limit=1)
        if not issued_status:
            issued_status = self.env['unified.contract.permit.status'].create({
                'name': 'ساري المفعول',
                'code': 'issued',
            })
        self.work_order.write({
            'permit_number': '5445000099',
            'permit_end_date': '2026-12-31',
        })
        self.assertTrue(self.work_order.permit_status_id)

    def test_stage_4_5_condition_auto_revert(self):
        """ Test auto-reset of certificate status and auto-reversion to Stage 4 when Stage 5 conditions are broken """
        self.work_order.with_context(skip_execution_check=True, skip_stage_permission_check=True, skip_certificate_reset=True).write({
            'receipt_155_status': 'yes',
            'completion_certificate_status': 'yes',
            'stage_id': self.stage_final_5.id,
        })
        self.assertEqual(self.work_order.stage_id.id, self.stage_final_5.id)

        # Breaking receipt_155_status resets certificate and auto-reverts to Stage 4 safely
        self.work_order.write({'receipt_155_status': 'no'})
        self.assertEqual(self.work_order.completion_certificate_status, 'no')
        self.assertEqual(self.work_order.stage_id.id, self.stage_close_4.id)

    def test_orm_field_permission_enforcement(self):
        """ Test ORM-level field permission enforcement for restricted non-admin users """
        wo_model = self.env['ir.model'].search([('model', '=', 'unified.contract.work.order')], limit=1)
        wo_field = self.env['ir.model.fields'].search([('model_id', '=', wo_model.id), ('name', '=', 'work_order_number')], limit=1)

        profile = self.env['unified.contract.permission.profile'].create({
            'name': 'بروفايل مقيد الحقول',
            'user_ids': [(4, self.test_user.id)],
        })
        self.env['unified.contract.field.permission'].create({
            'name': 'رقم أمر العمل',
            'profile_id': profile.id,
            'model_id': wo_model.id,
            'field_id': wo_field.id,
            'perm_read': True,
            'perm_write': False, # Restricted write!
        })

        wo_user_env = self.work_order.with_user(self.test_user)
        with self.assertRaises(UserError):
            wo_user_env.write({'work_order_number': '1236254099'})

    def test_invoice_referral_and_stage_5_bidirectional_sync(self):
        """ Test strict referral lock, Stage 5 dynamic statuses (referred, issued, uploaded, late, correction_requested, paid) and 100% auto-closure """
        self.work_order.write({
            'extract_service_number': 'EXT-UNIT-9900',
            'amount_before_tax': 15000.00,
            'receipt_155_status': 'yes',
            'completion_certificate_status': 'yes'
        })
        self.assertTrue(self.work_order.can_refer_to_finance)

        # 1. Referral to Finance
        self.work_order.action_refer_to_finance()
        inv = self.work_order.invoice_id
        self.assertTrue(inv)
        self.assertEqual(inv.name, self.work_order.work_order_number)
        self.assertEqual(self.work_order.stage_5_status, 'referred')
        self.assertFalse(self.work_order.can_refer_to_finance)

        # 2. Re-referral lock
        with self.assertRaises(ValidationError):
            self.work_order.action_refer_to_finance()

        # 3. Correction Request Exception
        inv.action_request_correction()
        self.assertEqual(self.work_order.stage_5_status, 'correction_requested')
        self.assertTrue(self.work_order.can_refer_to_finance)

        # 4. Re-referral after correction
        self.work_order.write({'amount_before_tax': 20000.00})
        self.work_order.action_refer_to_finance()
        self.assertEqual(inv.amount_total, 23000.00)
        self.assertEqual(self.work_order.stage_5_status, 'referred')
        self.assertFalse(self.work_order.can_refer_to_finance)

        # 5. Issuance & Upload to SAP
        inv.write({'invoice_number': 'INV-SAP-101'})
        self.assertEqual(self.work_order.stage_5_status, 'issued')
        inv.action_confirm_and_upload()
        self.assertEqual(self.work_order.stage_5_status, 'uploaded')

        # 6. Overdue / Late
        inv.action_set_late()
        self.assertEqual(self.work_order.stage_5_status, 'late')

        # 7. Payment & 100% Auto-Closure
        inv.action_set_paid()
        self.assertEqual(self.work_order.stage_5_status, 'paid')
        self.assertEqual(self.work_order.payment_status, 'paid')
        self.assertEqual(self.work_order.state, 'done')
        self.assertEqual(self.work_order.progress, 100.0)

        # 8. Unlink Exception
        inv.unlink()
        self.assertEqual(self.work_order.payment_status, 'unpaid')
        self.assertTrue(self.work_order.can_refer_to_finance)
