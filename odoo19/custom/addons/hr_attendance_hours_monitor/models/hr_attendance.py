# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, time


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    is_less_than_required_hours = fields.Boolean(
        string='أقل من ساعات العمل المطلوبة',
        compute='_compute_less_hours',
        store=True
    )

    worked_hours_today = fields.Float(
        string='ساعات العمل الفعلية اليوم',
        compute='_compute_less_hours',
        store=True,
        digits=(16, 2)
    )

    required_hours_today = fields.Float(
        string='ساعات العمل المطلوبة اليوم',
        compute='_compute_less_hours',
        store=True,
        digits=(16, 2)
    )

    @api.depends('employee_id', 'check_in', 'check_out')
    def _compute_less_hours(self):
        for rec in self:
            rec.is_less_than_required_hours = False
            rec.worked_hours_today = 0.0
            rec.required_hours_today = 0.0

            if not rec.employee_id or not rec.check_in:
                continue

            # ---------------------------
            # 1 تحديد يوم السجل الحالي
            # ---------------------------
            check_date = rec.check_in.date()

            # ---------------------------
            # 2️ حساب ساعات العمل الفعلية في هذا اليوم
            # ---------------------------
            attendances_today = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('check_in', '>=', datetime.combine(check_date, time.min)),
                ('check_in', '<=', datetime.combine(check_date, time.max)),
                ('check_out', '!=', False),
            ])

            total_work_hours = sum(
                (att.check_out - att.check_in).total_seconds() / 3600.0
                for att in attendances_today
            )
            rec.worked_hours_today = round(total_work_hours, 2)

            # ---------------------------
            # 3 حساب ساعات العمل المطلوبة من جدول العمل
            # ---------------------------
            calendar = rec.employee_id.resource_calendar_id
            if not calendar:
                continue

            weekday = check_date.weekday()  # Monday=0 ... Sunday=6

            # الحصول على الفترات الخاصة بهذا اليوم من الجدول
            attendances = calendar.attendance_ids.filtered(
                lambda a: int(a.dayofweek) == weekday
            )

            rec.required_hours_today = round(sum(a.hour_to - a.hour_from for a in attendances), 2)

            # ---------------------------
            # 4️ المقارنة: هل الموظف عمل أقل من المطلوب؟
            # ---------------------------
            rec.is_less_than_required_hours = rec.worked_hours_today < rec.required_hours_today
