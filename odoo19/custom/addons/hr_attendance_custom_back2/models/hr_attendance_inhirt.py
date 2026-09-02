from odoo import models, fields, api, _
from datetime import datetime, timedelta, timezone, date,time
from pytz import timezone as pytz_timezone
from odoo.exceptions import ValidationError
import pytz
import logging

_logger = logging.getLogger(__name__)

class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    auto_checkedout = fields.Boolean(string="Auto Checked-Out", default=False)

    @api.model
    def cron_auto_checkout(self):
        """Auto checkout employees at 4:15 PM Riyadh time (only today's attendances)"""

        # Import required modules
        import pytz
        from datetime import datetime, timedelta

        # Define Riyadh timezone
        riyadh_tz = pytz.timezone('Asia/Riyadh')

        # Get current time in Riyadh
        now_riyadh = datetime.now(riyadh_tz)

        # Check if current time is 4:15 PM or later
        if now_riyadh.hour < 16 or (now_riyadh.hour == 16 and now_riyadh.minute < 15):
            return  # Exit if it's before 4:15 PM

        # Get today's date in Riyadh timezone
        today_riyadh = now_riyadh.date()

        # Create checkout time (10:00 PM Riyadh time)
        checkout_time_riyadh = riyadh_tz.localize(
            datetime.combine(today_riyadh, datetime.min.time()).replace(hour=22, minute=00)
        )

        # Convert to UTC for database storage
        checkout_time_utc = checkout_time_riyadh.astimezone(pytz.UTC).replace(tzinfo=None)

        # Create datetime range for today in Riyadh timezone
        start_of_day_riyadh = riyadh_tz.localize(
            datetime.combine(today_riyadh, datetime.min.time())
        )
        end_of_day_riyadh = riyadh_tz.localize(
            datetime.combine(today_riyadh + timedelta(days=1), datetime.min.time())
        )

        # Convert to UTC for database query
        start_of_day_utc = start_of_day_riyadh.astimezone(pytz.UTC).replace(tzinfo=None)
        end_of_day_utc = end_of_day_riyadh.astimezone(pytz.UTC).replace(tzinfo=None)

        # Find today's attendances without checkout
        attendances = self.search([
            ("check_in", ">=", start_of_day_utc),
            ("check_in", "<", end_of_day_utc),
            ("check_out", "=", False),
        ])

        # Auto checkout
        for rec in attendances:
            rec.write({
                "check_out": checkout_time_utc,
                "auto_checkedout": True,
            })

        return len(attendances)

    ################################## For Holidays Warning #######
    holiday_warning = fields.Boolean(string="Holiday Warning", default=False)
    expected_holiday_return_date = fields.Date(string="Expected Return Date")

    #########ِ Adding attendance_employee_department #########
    attendance_employee_department = fields.Many2one(
        'hr.department',
        string="Employee Department",
        readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            employee_id = vals.get('employee_id')
            check_in = vals.get('check_in')

            if employee_id and check_in:
                # Convert check_in to date for comparison
                if isinstance(check_in, str):
                    check_in_dt = fields.Datetime.from_string(check_in)
                else:
                    check_in_dt = check_in

                check_in_date = check_in_dt.date()

                leave = self.env['hr.leave'].sudo().search([
                    ('employee_id', '=', employee_id),
                    ('state', '=', 'validate'),
                    ('date_from', '<=', check_in_date),
                    ('date_to', '>=', check_in_date)
                ], limit=1)

                if leave:
                    vals.update({
                        'holiday_warning': True,
                        'expected_holiday_return_date': leave.request_date_to
                    })

            if employee_id:
                employee = self.env['hr.employee'].browse(employee_id)
                if employee.department_id:
                    vals['attendance_employee_department'] = employee.department_id.id

        return super(HrAttendance, self).create(vals_list)


    def action_create_edit_request(self):
        """Simple action to create attendance edit request"""
        # Basic validations
        current_employee = self.env.user.employee_id

        if not current_employee:
            raise ValidationError(_("You must be linked to an employee to create edit requests."))

        # Check if this is today's attendance
        if self.check_in.date() != date.today():
            raise ValidationError(_("You can only request edit for today's attendance."))

        # Check if user can edit this attendance
        if self.employee_id != current_employee:
            raise ValidationError(_("You can only create edit requests for your own attendance."))

        # Check if there's already a pending request
        existing_request = self.env['hr.attendance.edit.request'].search([
            ('attendance_id', '=', self.id),
            ('state', '=', 'pending')
        ])

        if existing_request:
            raise ValidationError(_("There is already a pending edit request for this attendance record."))

        # Create the edit request with basic fields
        edit_request = self.env['hr.attendance.edit.request'].create({
            'employee_id': self.employee_id.id,
            'attendance_id': self.id,
        })

        # Return toast notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Attendance edit request has been created successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.constrains('check_in')
    def _check_checkin_time_limit(self):

        def float_to_time(f):
            hours = int(f)
            minutes = int(round((f - hours) * 60))
            if minutes == 60:
                hours += 1
                minutes = 0
            if hours >= 24:
                hours = 23
                minutes = 59
            return time(hour=hours, minute=minutes)

        for rec in self:


            if self.env.user.has_group('hr_attendance_custom.group_free_checkout'):
                continue

            if not rec.check_in or not rec.employee_id.resource_calendar_id:
                continue

            employee_tz = pytz.timezone(rec.employee_id.tz or 'UTC')

            check_in_utc = rec.check_in
            if check_in_utc.tzinfo is None:
                check_in_utc = pytz.UTC.localize(check_in_utc)
            check_in_local = check_in_utc.astimezone(employee_tz)

            local_date = check_in_local.date()
            day_of_week = str((local_date.weekday() + 1) % 7)

            shifts = self.env['resource.calendar.attendance'].search([
                ('calendar_id', '=', rec.employee_id.resource_calendar_id.id),
                ('dayofweek', '=', day_of_week)
            ])
            if not shifts:
                continue

            shift_starts = []
            for shift in shifts:
                start_time = float_to_time(shift.hour_from)
                start_datetime_naive = datetime.combine(local_date, start_time)
                shift_starts.append(start_datetime_naive)

            earliest_start_naive = min(shift_starts)
            earliest_start_local = employee_tz.localize(earliest_start_naive, is_dst=None)

            earliest_allowed = earliest_start_local - timedelta(minutes=15)

            check_in_local_clean = check_in_local.replace(second=0, microsecond=0)
            earliest_allowed_clean = earliest_allowed.replace(second=0, microsecond=0)

            if check_in_local_clean < earliest_allowed_clean:
                raise ValidationError(_(
                    "لا يمكنك تسجيل الدخول قبل ربع ساعة من بداية ورديتك: %s"
                ) % earliest_start_local.strftime('%H:%M'))
