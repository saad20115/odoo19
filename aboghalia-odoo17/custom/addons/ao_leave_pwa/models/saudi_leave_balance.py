# -*- coding: utf-8 -*-
"""Saudi Labor Law annual leave balance (Art. 109).

* 21 days/year for employees with less than 5 years of service
* 30 days/year for employees with 5+ years of service
* Entitlement tier is based on joining date (years of service)
* Leave year is calendar year (1 Jan – 31 Dec); balance resets every 1 January
* Used days = validated canonical paid leave type in the current calendar year
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import float_round

SAUDI_LEAVE_DAYS_UNDER_5 = 21.0
SAUDI_LEAVE_DAYS_5_PLUS = 30.0
SENIORITY_YEARS_THRESHOLD = 5
LEAVE_DAY_PRECISION = 2
HOURS_PER_WORK_DAY = 8.0


class SaudiLeaveBalance(models.AbstractModel):
    _name = 'saudi.leave.balance'
    _description = 'Saudi Labor Law Annual Leave Balance'

    @api.model
    def _round_days(self, value):
        return float_round(float(value or 0.0), precision_digits=LEAVE_DAY_PRECISION)

    @api.model
    def _get_employee_joining_date(self, employee):
        joining = getattr(employee, 'joining_date', False)
        if joining:
            return fields.Date.to_date(joining)
        contract_ids = getattr(employee, 'contract_ids', False)
        if contract_ids:
            starts = contract_ids.filtered('date_start').mapped('date_start')
            if starts:
                return min(starts)
        if employee.create_date:
            return fields.Date.to_date(employee.create_date)
        return fields.Date.context_today(self)

    @api.model
    def _years_of_service(self, joining_date, ref_date):
        if not joining_date or joining_date > ref_date:
            return 0
        delta = relativedelta(ref_date, joining_date)
        return delta.years

    @api.model
    def _annual_entitlement(self, years_of_service):
        if years_of_service >= SENIORITY_YEARS_THRESHOLD:
            return SAUDI_LEAVE_DAYS_5_PLUS
        return SAUDI_LEAVE_DAYS_UNDER_5

    @api.model
    def _leave_year_bounds(self, ref_date):
        """Calendar leave year: 1 January – 31 December."""
        year_start = date(ref_date.year, 1, 1)
        year_end = date(ref_date.year, 12, 31)
        return year_start, year_end

    @api.model
    def _calendar_month_periods(self, year_start, year_end):
        periods = []
        for month in range(1, 13):
            period_start = date(year_start.year, month, 1)
            if month == 12:
                period_end = year_end
            else:
                period_end = date(year_start.year, month + 1, 1) - relativedelta(days=1)
            if period_start > year_end:
                break
            periods.append((period_start, min(period_end, year_end)))
        return periods

    @api.model
    def _year_entitlement(self, joining_date, ref_date):
        """Full calendar-year entitlement (21 or 30 days)."""
        service_years = self._years_of_service(joining_date, ref_date)
        return self._annual_entitlement(service_years)

    @api.model
    def _monthly_breakdown(self, employee, year_start, year_end, ref_date, paid_type_id,
                           year_entitlement, monthly_rate):
        """Per-month accrual (21/12 or 30/12), used days, and running remaining."""
        periods = self._calendar_month_periods(year_start, year_end)
        months = []
        cumulative_used = 0.0
        for idx, (period_start, period_end) in enumerate(periods, start=1):
            used_in_month = self._sum_leave_days(
                employee, period_start, period_end, ('validate',), paid_type_id=paid_type_id,
            )
            cumulative_used = self._round_days(cumulative_used + used_in_month)
            cumulative_accrued = self._round_days(min(monthly_rate * idx, year_entitlement))
            remaining = self._round_days(max(cumulative_accrued - cumulative_used, 0.0))
            months.append({
                'month': idx,
                'year': year_start.year,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'accrued': monthly_rate,
                'used': used_in_month,
                'remaining': remaining,
                'is_current': period_start <= ref_date <= period_end,
            })
        return months

    @api.model
    def _monthly_breakdown_hr_override(self, employee, year_start, year_end, ref_date,
                                       paid_type_id, monthly_rate, hr_record):
        """Monthly table from HR import date forward; earlier months are empty."""
        effective = hr_record.effective_date
        hr_remaining = hr_record.remaining_days
        periods = self._calendar_month_periods(year_start, year_end)
        months = []
        cumulative_used_since = 0.0

        for idx, (period_start, period_end) in enumerate(periods, start=1):
            if period_end < effective:
                months.append({
                    'month': idx,
                    'year': year_start.year,
                    'period_start': period_start.isoformat(),
                    'period_end': period_end.isoformat(),
                    'accrued': 0.0,
                    'used': 0.0,
                    'remaining': None,
                    'is_current': period_start <= ref_date <= period_end,
                    'before_import': True,
                })
                continue

            month_used_start = max(period_start, effective)
            used_in_month = self._sum_leave_days(
                employee, month_used_start, period_end, ('validate',),
                paid_type_id=paid_type_id,
            )
            cumulative_used_since = self._round_days(cumulative_used_since + used_in_month)
            remaining = self._round_days(max(hr_remaining - cumulative_used_since, 0.0))
            months.append({
                'month': idx,
                'year': year_start.year,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'accrued': monthly_rate,
                'used': used_in_month,
                'remaining': remaining,
                'is_current': period_start <= ref_date <= period_end,
                'before_import': False,
            })
        return months

    @api.model
    def _balance_from_hr_import(self, employee, ref_date, hr_record, paid_type, year_start,
                                year_end, year_entitlement, monthly_rate, company_id):
        """Compute balance using HR-uploaded remaining days from effective_date."""
        effective = hr_record.effective_date
        if effective > year_end:
            effective = year_start

        spent_states = ('validate',)
        pending_states = ('confirm', 'validate1')
        spent_since = self._sum_leave_days(
            employee, effective, year_end, spent_states, paid_type_id=paid_type,
        )
        pending_since = self._sum_leave_days(
            employee, effective, year_end, pending_states, paid_type_id=paid_type,
        )
        hr_snapshot = self._round_days(hr_record.remaining_days)
        remaining = self._round_days(max(hr_snapshot - spent_since, 0.0))
        entitlement_from_hr = self._round_days(hr_snapshot + spent_since)

        paid_rec, unpaid_rec = self._get_canonical_types(company_id)
        hours_per_day = self._get_hours_per_day(employee)
        months = self._monthly_breakdown_hr_override(
            employee, year_start, year_end, ref_date, paid_type,
            monthly_rate, hr_record,
        )
        joining_date = self._get_employee_joining_date(employee)
        service_years = self._years_of_service(joining_date, ref_date)
        annual_entitlement = self._annual_entitlement(service_years)

        return {
            'source': 'hr_import',
            'leave_year_type': 'calendar',
            'joining_date': joining_date.isoformat() if joining_date else None,
            'service_years': service_years,
            'annual_entitlement': annual_entitlement,
            'year_entitlement_cap': entitlement_from_hr,
            'monthly_rate': monthly_rate,
            'hours_per_day': hours_per_day,
            'leave_year_start': year_start.isoformat(),
            'leave_year_end': year_end.isoformat(),
            'accrued_to_date': entitlement_from_hr,
            'all_allocated': entitlement_from_hr,
            'all_spent': spent_since,
            'all_pending': pending_since,
            'all_remaining': remaining,
            'paid_leave_type_id': paid_type or None,
            'paid_leave_type_name': paid_rec.name if paid_rec else None,
            'months': months,
            'hr_import_effective_date': effective.isoformat(),
            'hr_import_snapshot': hr_snapshot,
        }

    @api.model
    def _get_hours_per_day(self, employee):
        """One leave day always equals 8 working hours."""
        return HOURS_PER_WORK_DAY

    @api.model
    def _get_canonical_types(self, company_id):
        """Pick exactly one paid + one unpaid type for the PWA (ignore extras)."""
        types = self.env['hr.leave.type'].sudo().search([
            '|', ('company_id', '=', False), ('company_id', '=', company_id),
            ('active', '=', True),
        ], order='sequence, id')
        unpaid = types.filtered(lambda t: bool(getattr(t, 'unpaid', False)))[:1]
        skip_tokens = ('رصيد', 'تجريبي', 'trial', 'test', 'سابق')
        paid_pool = types.filtered(
            lambda t: not bool(getattr(t, 'unpaid', False))
            and not any(token in (t.name or '') for token in skip_tokens)
        )
        preferred = paid_pool.filtered(
            lambda t: 'مدفوع' in (t.name or '') or 'paid' in (t.name or '').lower()
        )
        paid = preferred.filtered(lambda t: t.requires_allocation == 'yes')[:1]
        if not paid:
            paid = paid_pool.filtered(lambda t: t.requires_allocation == 'yes')[:1]
        if not paid:
            paid = preferred[:1]
        if not paid:
            paid = paid_pool[:1]
        return paid, unpaid

    @api.model
    def _paid_leave_type_id(self, company_id):
        paid, _unpaid = self._get_canonical_types(company_id)
        return paid.id if paid else False

    @api.model
    def _overlap_leave_days(self, leave, period_start, period_end):
        leave_start = leave.request_date_from
        leave_end = leave.request_date_to
        if not leave_start or not leave_end:
            return 0.0
        overlap_start = max(leave_start, period_start)
        overlap_end = min(leave_end, period_end)
        if overlap_start > overlap_end:
            return 0.0
        if leave_start >= period_start and leave_end <= period_end:
            return float(leave.number_of_days or 0.0)
        total_cal = (leave_end - leave_start).days + 1
        overlap_cal = (overlap_end - overlap_start).days + 1
        if total_cal <= 0:
            return 0.0
        return float(leave.number_of_days or 0.0) * overlap_cal / total_cal

    @api.model
    def _sum_leave_days(self, employee, period_start, period_end, states, paid_type_id=None):
        domain = [
            ('employee_id', '=', employee.id),
            ('state', 'in', list(states)),
            ('request_date_from', '<=', period_end),
            ('request_date_to', '>=', period_start),
        ]
        if paid_type_id:
            domain.append(('holiday_status_id', '=', paid_type_id))
        leaves = self.env['hr.leave'].sudo().search(domain)
        total = 0.0
        for leave in leaves:
            total += self._overlap_leave_days(leave, period_start, period_end)
        return self._round_days(total)

    @api.model
    def compute_employee_balance(self, employee, ref_date=None):
        ref_date = ref_date or fields.Date.context_today(self)
        joining_date = self._get_employee_joining_date(employee)
        company_id = employee.company_id.id if employee.company_id else False
        paid_type = self._paid_leave_type_id(company_id)
        year_start, year_end = self._leave_year_bounds(ref_date)
        service_years = self._years_of_service(joining_date, ref_date)
        annual_entitlement = self._annual_entitlement(service_years)
        year_entitlement = self._year_entitlement(joining_date, ref_date)
        monthly_rate = self._round_days(year_entitlement / 12.0)

        hr_record = self.env['leave.pwa.employee.balance'].get_active_for_employee(
            employee, ref_date.year,
        )
        if hr_record:
            return self._balance_from_hr_import(
                employee, ref_date, hr_record, paid_type, year_start, year_end,
                year_entitlement, monthly_rate, company_id,
            )

        spent_states = ('validate',)
        pending_states = ('confirm', 'validate1')
        spent = self._sum_leave_days(
            employee, year_start, year_end, spent_states, paid_type_id=paid_type,
        )
        pending = self._sum_leave_days(
            employee, year_start, year_end, pending_states, paid_type_id=paid_type,
        )
        remaining = self._round_days(max(year_entitlement - spent, 0.0))

        paid_rec, unpaid_rec = self._get_canonical_types(company_id)
        hours_per_day = self._get_hours_per_day(employee)
        months = self._monthly_breakdown(
            employee, year_start, year_end, ref_date, paid_type,
            year_entitlement, monthly_rate,
        )
        return {
            'source': 'saudi_labor_law',
            'leave_year_type': 'calendar',
            'joining_date': joining_date.isoformat() if joining_date else None,
            'service_years': service_years,
            'annual_entitlement': annual_entitlement,
            'year_entitlement_cap': year_entitlement,
            'monthly_rate': monthly_rate,
            'hours_per_day': hours_per_day,
            'leave_year_start': year_start.isoformat(),
            'leave_year_end': year_end.isoformat(),
            'accrued_to_date': year_entitlement,
            'all_allocated': year_entitlement,
            'all_spent': spent,
            'all_pending': pending,
            'all_remaining': remaining,
            'paid_leave_type_id': paid_type or None,
            'paid_leave_type_name': paid_rec.name if paid_rec else None,
            'months': months,
        }

    @api.model
    def estimate_request_days(self, date_from, date_to, half_day=False):
        if half_day:
            return 0.5
        return float((date_to - date_from).days + 1)

    @api.model
    def check_paid_leave_request(self, employee, date_from, date_to, half_day=False):
        """Return balance check for a paid leave request (warning only, never blocks)."""
        balance = self.compute_employee_balance(employee, ref_date=date_from)
        remaining = balance['all_remaining']
        requested = self.estimate_request_days(date_from, date_to, half_day=half_day)
        warning = None
        if remaining <= 0:
            warning = 'no_remaining_days'
        elif requested > remaining:
            warning = 'insufficient_days'
        return {
            'remaining': remaining,
            'requested': requested,
            'accrued_to_date': balance['accrued_to_date'],
            'warning': warning,
        }

    @api.model
    def get_pwa_leave_types(self, company_id):
        """Exactly two PWA choices: paid + unpaid."""
        paid, unpaid = self._get_canonical_types(company_id)
        data = []
        if paid:
            data.append({
                'id': paid.id,
                'key': 'paid',
                'name': paid.name or 'Paid',
                'requires_allocation': paid.requires_allocation,
                'active': True,
            })
        if unpaid:
            data.append({
                'id': unpaid.id,
                'key': 'unpaid',
                'name': unpaid.name or 'Unpaid',
                'requires_allocation': unpaid.requires_allocation,
                'active': True,
            })
        return data
