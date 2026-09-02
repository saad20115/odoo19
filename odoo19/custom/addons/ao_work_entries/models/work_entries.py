from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta, time, date
import calendar
import logging
import json
import base64
import io
import pytz

_logger = logging.getLogger(__name__)


class HrEmployeeAttendanceGrid(models.Model):
    """
    Model to handle attendance grid operations for Odoo 17 with Asia/Riyadh timezone
    """
    _name = 'hr.employee.attendance.grid'
    _description = 'Employee Attendance Grid'
    _auto = False  # This is a virtual model, no database table

    def _get_riyadh_timezone(self):
        """Get Asia/Riyadh timezone object"""
        return pytz.timezone('Asia/Riyadh')

    def _get_utc_timezone(self):
        """Get UTC timezone object"""
        return pytz.UTC

    def _convert_to_riyadh_timezone(self, utc_datetime):
        """Convert UTC datetime to Asia/Riyadh timezone"""
        if not utc_datetime:
            return None

        try:
            # Ensure datetime is UTC
            if utc_datetime.tzinfo is None:
                utc_datetime = self._get_utc_timezone().localize(utc_datetime)

            # Convert to Riyadh timezone
            riyadh_tz = self._get_riyadh_timezone()
            return utc_datetime.astimezone(riyadh_tz)
        except Exception as e:
            _logger.error(f"Error converting timezone: {str(e)}")
            return utc_datetime

    def _convert_to_utc_timezone(self, riyadh_datetime):
        """Convert Asia/Riyadh datetime to UTC timezone"""
        if not riyadh_datetime:
            return None

        try:
            riyadh_tz = self._get_riyadh_timezone()

            # Ensure datetime is in Riyadh timezone
            if riyadh_datetime.tzinfo is None:
                riyadh_datetime = riyadh_tz.localize(riyadh_datetime)

            # Convert to UTC
            return riyadh_datetime.astimezone(self._get_utc_timezone())
        except Exception as e:
            _logger.error(f"Error converting to UTC: {str(e)}")
            return riyadh_datetime

    def _get_riyadh_date(self, year, month, day):
        """Get a date object in Riyadh timezone"""
        try:
            riyadh_tz = self._get_riyadh_timezone()
            return riyadh_tz.localize(datetime(year, month, day))
        except Exception as e:
            _logger.error(f"Error creating Riyadh date: {str(e)}")
            return datetime(year, month, day)

    def _get_riyadh_datetime(self, year, month, day, hour=0, minute=0, second=0):
        """Get a datetime object in Riyadh timezone"""
        try:
            riyadh_tz = self._get_riyadh_timezone()
            return riyadh_tz.localize(datetime(year, month, day, hour, minute, second))
        except Exception as e:
            _logger.error(f"Error creating Riyadh datetime: {str(e)}")
            return datetime(year, month, day, hour, minute, second)

    def _get_current_riyadh_datetime(self):
        """Get current datetime in Riyadh timezone"""
        try:
            utc_now = self._get_utc_timezone().localize(datetime.utcnow())
            return utc_now.astimezone(self._get_riyadh_timezone())
        except Exception as e:
            _logger.error(f"Error getting current Riyadh time: {str(e)}")
            return datetime.now()

    # -------------------------------------------------------------------------
    # Request-scoped performance cache (same HTTP/RPC request only)
    # -------------------------------------------------------------------------

    def _ensure_perf_cache(self):
        """Initialize a per-request cache to avoid duplicate computations."""
        if self.env.context.get('_attendance_grid_perf_cache'):
            return self
        return self.with_context(_attendance_grid_perf_cache={
            'employee_attendance': {},
            'employee_attendance_records': {},
            'weekend_days': {},
            'public_holidays': {},
            'expected_hours': {},
        })

    def _get_perf_cache(self):
        return self.env.context.get('_attendance_grid_perf_cache')

    def _group_list_by_key(self, records, key_name):
        grouped = {}
        for record in records:
            grouped.setdefault(record[key_name], []).append(record)
        return grouped

    def _build_attendance_date_index(self, attendance_records):
        """First record per (employee, date) wins — same as sequential scan."""
        index = {}
        for record in attendance_records:
            key = (record['employee_id'], record['date'])
            if key not in index:
                index[key] = record
        return index

    @api.model
    def get_attendance_data(self, year, month, filters=None, pagination=None):
        """
        Get comprehensive attendance data for a specific month and year
        All datetimes are handled in Asia/Riyadh timezone

        Args:
            year (int): Year to fetch data for
            month (int): Month to fetch data for (1-12)
            filters (dict): Filter options (department_id, employee_name, status_filter)
            pagination (dict): Pagination options (page, page_size)

        Returns:
            dict: Complete attendance data structure with pagination
        """
        try:
            self = self._ensure_perf_cache()

            # Validate input parameters
            if not isinstance(year, int) or not isinstance(month, int):
                return self._error_response("Year and month must be integers")

            if month < 1 or month > 12:
                return self._error_response("Month must be between 1 and 12")

            # Set default filters and pagination
            filters = filters or {}
            pagination = pagination or {'page': 1, 'page_size': 50}

            # Log filters for debugging
            _logger.info(f"Applying filters: {filters}")

            # Get days in month
            days_in_month = calendar.monthrange(year, month)[1]
            days_list = list(range(1, days_in_month + 1))

            # Get all employees first (apply basic filters but not status filter yet)
            basic_filters = {k: v for k, v in filters.items() if k != 'status_filter'}
            all_employees = self._get_employees(basic_filters)
            _logger.info(f"Found {len(all_employees)} employees after basic filtering")

            # Compute attendance once for all employees (reused for filter, grid, stats)
            all_attendance_data = self._get_month_attendance_data(
                year, month, days_list, all_employees
            )

            # Apply status filter using already-computed attendance data
            if filters.get('status_filter'):
                all_employees = self._filter_employees_by_status_with_data(
                    all_employees, filters['status_filter'], all_attendance_data
                )
                _logger.info(f"Found {len(all_employees)} employees after status filtering")

            # Get paginated employees
            paginated_result = self._get_paginated_employees(all_employees, pagination)

            # Slice cached attendance for the current page only
            attendance_data = {
                employee['id']: all_attendance_data[employee['id']]
                for employee in paginated_result['employees']
                if employee['id'] in all_attendance_data
            }

            # Statistics for all filtered employees (reuse cached attendance)
            statistics = self._calculate_attendance_statistics(
                year, month, days_list, all_employees,
                all_attendance_data=all_attendance_data,
            )

            # Get departments for filters
            departments = self._get_departments()

            # Monthly summaries — bulk fetch + reuse cached attendance
            monthly_summaries = self._get_monthly_summaries_for_employees(
                paginated_result['employees'], year, month, all_attendance_data
            )

            # Department summaries for current page (replaces N frontend RPC calls)
            department_summaries = self._get_department_summaries_for_employees(
                paginated_result['employees'], year, month, all_attendance_data
            )

            return {
                'success': True,
                'employees': paginated_result['employees'],
                'attendance_data': attendance_data,
                'monthly_summaries': monthly_summaries,
                'department_summaries': department_summaries,
                'days_in_month': days_list,
                'statistics': statistics,
                'departments': departments,
                'pagination': paginated_result['pagination'],
                'month_name': calendar.month_name[month],
                'year': year,
                'month': month,
                'filters': filters
            }

        except Exception as e:
            _logger.error(f"Error in get_attendance_data: {str(e)}")
            return self._error_response(f"Error fetching attendance data: {str(e)}")

    def _filter_employees_by_status(self, employees, status_filter, year, month, days_list):
        """
        Filter employees based on attendance status.
        Computes attendance in one batch, then filters (same result as per-employee calls).
        """
        if not status_filter:
            return employees

        attendance_data = self._get_month_attendance_data(
            year, month, days_list, employees
        )
        return self._filter_employees_by_status_with_data(
            employees, status_filter, attendance_data
        )

    def _filter_employees_by_status_with_data(self, employees, status_filter, attendance_data):
        """Filter employees using pre-computed attendance data."""
        if not status_filter:
            return employees

        filtered_employees = []
        for employee in employees:
            employee_data = attendance_data.get(employee['id'], {})
            has_status = any(
                day_data.get('status') == status_filter
                for day_data in employee_data.values()
            )
            if has_status:
                filtered_employees.append(employee)

        return filtered_employees

    def _error_response(self, message):
        """Return standardized error response"""
        return {
            'success': False,
            'error': message,
            'employees': [],
            'attendance_data': {},
            'days_in_month': [],
            'statistics': {},
            'departments': [],
            'department_summaries': {},
            'pagination': {'current_page': 1, 'total_pages': 1, 'total_count': 0}
        }

    def _get_employees(self, filters):
        """
        Get employees based on filters

        Args:
            filters (dict): Filter criteria

        Returns:
            list: List of employee dictionaries
        """
        domain = [('active', '=', True), ('resource_id.active', '=', True)]

        # Debug log
        _logger.info(f"Processing filters in _get_employees: {filters}")

        # Apply department filter (support camelCase and snake_case keys)
        dept_id = filters.get('departmentId') or filters.get('department_id')
        if dept_id and str(dept_id).strip() and dept_id != '':
            try:
                dept_id_int = int(dept_id)
                domain.append(('department_id', '=', dept_id_int))
                _logger.info(f"Applied department filter: department_id = {dept_id_int}")
            except (ValueError, TypeError) as e:
                _logger.warning(f"Invalid department_id: {dept_id}, error: {e}")

        # Apply name filter (support camelCase and snake_case keys)
        emp_name = filters.get('employeeName') or filters.get('employee_name')
        if emp_name and str(emp_name).strip():
            domain.append(('name', 'ilike', str(emp_name).strip()))
            _logger.info(f"Applied name filter: name ilike '{emp_name}'")

        _logger.info(f"Final domain: {domain}")

        Employee = self.env['hr.employee'].with_context(active_test=True)
        employees = Employee.search(domain, order='name asc')
        employees = employees.filtered(
            lambda e: e.active and (not e.resource_id or e.resource_id.active)
        )

        _logger.info(f"Found {len(employees)} active employees with domain {domain}")

        employee_list = []
        for employee in employees:
            employee_data = {
                'id': employee.id,
                'name': employee.name,
                'department_id': employee.department_id.id if employee.department_id else False,
                'department_name': employee.department_id.name if employee.department_id else '',
                'work_email': employee.work_email or '',
                'user_id': employee.user_id.id if employee.user_id else False,
                'job_title': employee.job_title or '',
                'work_phone': employee.work_phone or '',
                'avatar_url': f'/web/image/hr.employee/{employee.id}/avatar_128'
            }
            employee_list.append(employee_data)

        return employee_list

    def _safe_timezone_conversion(self, date_obj, time_obj, target_timezone='UTC'):
        """
        Safely convert date and time to target timezone with error handling
        """
        try:
            riyadh_tz = pytz.timezone('Asia/Riyadh')
            utc_tz = pytz.UTC

            # Combine date and time
            naive_datetime = datetime.combine(date_obj, time_obj)

            # Localize to Riyadh timezone first
            riyadh_datetime = riyadh_tz.localize(naive_datetime)

            if target_timezone == 'UTC':
                # Convert to UTC and make naive for Odoo
                utc_datetime = riyadh_datetime.astimezone(utc_tz)
                return utc_datetime.replace(tzinfo=None)  # Remove timezone info for Odoo
            else:
                return riyadh_datetime

        except pytz.exceptions.AmbiguousTimeError:
            # Handle daylight saving time ambiguity
            riyadh_datetime = riyadh_tz.localize(naive_datetime, is_dst=False)
            if target_timezone == 'UTC':
                utc_datetime = riyadh_datetime.astimezone(utc_tz)
                return utc_datetime.replace(tzinfo=None)
            return riyadh_datetime

        except pytz.exceptions.NonExistentTimeError:
            # Handle daylight saving time gaps
            riyadh_datetime = riyadh_tz.localize(naive_datetime, is_dst=False)
            if target_timezone == 'UTC':
                utc_datetime = riyadh_datetime.astimezone(utc_tz)
                return utc_datetime.replace(tzinfo=None)
            return riyadh_datetime

        except Exception as e:
            _logger.error(f"Timezone conversion error: {str(e)}")
            # Fallback: assume naive datetime is already in target timezone
            return naive_datetime

    def _get_paginated_employees(self, employees, pagination):
        """
        Apply pagination to employee list

        Args:
            employees (list): Full employee list
            pagination (dict): Pagination settings

        Returns:
            dict: Paginated result with employees and pagination info
        """
        if not employees:
            return {
                'employees': [],
                'pagination': {
                    'current_page': 1,
                    'total_pages': 1,
                    'total_count': 0,
                    'page_size': pagination.get('page_size', 50),
                    'start_index': 0,
                    'end_index': 0
                }
            }

        page = max(1, int(pagination.get('page', 1)))
        page_size = pagination.get('page_size', 50)

        # Handle 'all' page size
        if page_size == 'all':
            return {
                'employees': employees,
                'pagination': {
                    'current_page': 1,
                    'total_pages': 1,
                    'total_count': len(employees),
                    'page_size': 'all',
                    'start_index': 1,
                    'end_index': len(employees)
                }
            }

        try:
            page_size = int(page_size)
        except (ValueError, TypeError):
            page_size = 50

        total_count = len(employees)
        total_pages = max(1, (total_count + page_size - 1) // page_size)

        # Ensure page is within bounds
        page = min(page, total_pages)

        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_count)

        paginated_employees = employees[start_index:end_index]

        pagination_info = {
            'current_page': page,
            'total_pages': total_pages,
            'total_count': total_count,
            'page_size': page_size,
            'start_index': start_index + 1 if total_count > 0 else 0,
            'end_index': end_index
        }

        _logger.info(f"Pagination: page {page}/{total_pages}, showing {start_index + 1}-{end_index} of {total_count}")

        return {
            'employees': paginated_employees,
            'pagination': pagination_info
        }

    def _get_departments(self):
        """Get all departments for filter dropdown"""
        try:
            Department = self.env['hr.department']
            departments = Department.search([], order='name asc')
            return [{'id': dept.id, 'name': dept.name} for dept in departments]
        except Exception:
            return []

    def _get_month_attendance_data(self, year, month, days_list, employees):
        """
        Get attendance data for specific employees for the specified month.
        Uses per-employee request cache to avoid duplicate computation.
        """
        if not employees:
            return {}

        perf_cache = self._get_perf_cache()
        result = {}
        to_compute = []

        for employee in employees:
            emp_id = employee['id']
            cache_key = (year, month, emp_id)
            if perf_cache and cache_key in perf_cache['employee_attendance']:
                result[emp_id] = perf_cache['employee_attendance'][cache_key]
            else:
                to_compute.append(employee)

        if to_compute:
            computed = self._compute_month_attendance_data(year, month, days_list, to_compute)
            result.update(computed)
            if perf_cache:
                for emp_id, data in computed.items():
                    perf_cache['employee_attendance'][(year, month, emp_id)] = data

        return result

    def _compute_month_attendance_data(self, year, month, days_list, employees):
        """
        Compute attendance data for employees not yet in the request cache.
        All datetime operations use Asia/Riyadh timezone.
        """
        if not employees:
            return {}

        attendance_data = {}
        employee_ids = [emp['id'] for emp in employees]

        start_date = self._get_riyadh_datetime(year, month, 1)
        end_date = self._get_riyadh_datetime(year, month, days_list[-1], 23, 59, 59)
        start_date_utc = self._convert_to_utc_timezone(start_date)
        end_date_utc = self._convert_to_utc_timezone(end_date)

        attendance_records = self._get_attendance_records_batch(
            start_date_utc, end_date_utc, employee_ids
        )
        leave_records = self._get_leave_records_batch(
            start_date_utc, end_date_utc, employee_ids
        )
        public_holidays = self._get_public_holidays(start_date, end_date)

        edit_requests = self._get_attendance_edit_requests_batch(
            start_date_utc, end_date_utc, employee_ids
        )
        edit_requests_by_employee = self._group_list_by_key(edit_requests, 'employee_id')
        leaves_by_employee = self._group_list_by_key(leave_records, 'employee_id')
        attendance_date_index = self._build_attendance_date_index(attendance_records)

        perf_cache = self._get_perf_cache()
        if perf_cache:
            records_by_employee = self._group_list_by_key(attendance_records, 'employee_id')
            for emp_id in employee_ids:
                perf_cache['employee_attendance_records'][emp_id] = records_by_employee.get(emp_id, [])

        self._prefetch_weekend_days_for_employees(employee_ids)

        for employee in employees:
            employee_id = employee['id']
            attendance_data[employee_id] = self._process_employee_month_data(
                employee_id, year, month, days_list,
                attendance_date_index, leaves_by_employee, public_holidays,
                edit_requests_by_employee.get(employee_id, []),
                self._get_employee_weekend_days(employee_id),
            )

        return attendance_data

    def _process_employee_month_data(self, employee_id, year, month, days_list,
                                     attendance_date_index, leaves_by_employee,
                                     public_holidays, edit_requests, employee_weekend_days):
        """Process attendance data for a single employee for the month."""
        employee_data = {}
        riyadh_tz = self._get_riyadh_timezone()
        employee_leaves = leaves_by_employee.get(employee_id, [])

        for day in days_list:
            day_date = riyadh_tz.localize(datetime(year, month, day))
            date_str = day_date.strftime('%Y-%m-%d')

            day_data = {
                'status': 'absent',
                'hours': 0.0,
                'check_in': None,
                'check_out': None,
                'record_id': None,
                'note': '',
                'has_edit_request': False,
                'edit_request_id': None,
            }

            edit_request = self._get_employee_edit_request_for_date(
                employee_id, date_str, edit_requests
            )
            if edit_request:
                day_data['has_edit_request'] = True
                day_data['edit_request_id'] = edit_request['id']

            is_public_holiday = date_str in public_holidays
            if is_public_holiday:
                day_data['public_holiday_name'] = public_holidays[date_str]

            leave_data = self._get_employee_leave_for_date(
                employee_id, date_str, employee_leaves
            )
            if leave_data:
                day_data['leave_name'] = leave_data['name']

            attendance_record = attendance_date_index.get((employee_id, date_str))
            if attendance_record:
                day_data['status'] = 'present'
                day_data['hours'] = attendance_record['worked_hours'] or 0.0
                day_data['check_in'] = attendance_record['check_in']
                day_data['check_out'] = attendance_record['check_out']
                day_data['record_id'] = attendance_record['id']
                day_data['auto_checkedout'] = attendance_record['auto_checkedout'] or False
                day_data['holiday_warning'] = attendance_record['holiday_warning'] or False

                if leave_data or is_public_holiday:
                    day_data['checked_in_during_leave'] = True
                    if leave_data:
                        day_data['note'] = f"Checked in during leave: {leave_data['name']}"
                    elif is_public_holiday:
                        day_data['note'] = f"Checked in during public holiday: {public_holidays[date_str]}"

                employee_data[day] = day_data
                continue

            if day_date.weekday() in employee_weekend_days:
                day_data['status'] = 'weekend'
                employee_data[day] = day_data
                continue

            if is_public_holiday:
                day_data['status'] = 'holiday'
                day_data['note'] = public_holidays[date_str]
                employee_data[day] = day_data
                continue

            if leave_data:
                day_data['status'] = 'leave'
                day_data['note'] = leave_data['name']

            employee_data[day] = day_data

        return employee_data

    def _get_attendance_records_batch(self, start_date_utc, end_date_utc, employee_ids):
        """
        Get attendance records for multiple employees in a single query
        Returns data converted to Riyadh timezone
        """
        if not employee_ids:
            return []

        Attendance = self.env['hr.attendance']
        records = Attendance.search([
            ('employee_id', 'in', employee_ids),
            ('check_in', '>=', start_date_utc),
            ('check_in', '<=', end_date_utc)
        ])

        attendance_list = []
        for record in records:
            # Convert times to Riyadh timezone for display
            check_in_riyadh = self._convert_to_riyadh_timezone(record.check_in)
            check_out_riyadh = self._convert_to_riyadh_timezone(record.check_out)

            attendance_list.append({
                'id': record.id,
                'employee_id': record.employee_id.id,
                'check_in': check_in_riyadh.isoformat() if check_in_riyadh else None,
                'check_out': check_out_riyadh.isoformat() if check_out_riyadh else None,
                'worked_hours': record.worked_hours,
                'date': check_in_riyadh.strftime('%Y-%m-%d') if check_in_riyadh else None,
                'department_id': record.attendance_employee_department.id if record.attendance_employee_department else None,
                'department_name': record.attendance_employee_department.name if record.attendance_employee_department else None,
                'auto_checkedout': record.auto_checkedout if hasattr(record, 'auto_checkedout') else False,
                'holiday_warning': record.holiday_warning if hasattr(record, 'holiday_warning') else False,
            })

        return attendance_list

    @api.model
    def get_employee_department_summary(self, employee_id, year, month):
        """
        Get department-wise breakdown of attendance metrics for an employee
        """
        try:
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                return {'success': False, 'message': 'Employee not found'}

            days_in_month = calendar.monthrange(year, month)[1]
            days_list = list(range(1, days_in_month + 1))

            attendance_data = self._get_month_attendance_data(
                year, month, days_list, [{'id': employee_id}]
            )
            employee_attendance = attendance_data.get(employee_id, {})

            perf_cache = self._get_perf_cache()
            if perf_cache and employee_id in perf_cache.get('employee_attendance_records', {}):
                attendance_records = perf_cache['employee_attendance_records'][employee_id]
            else:
                start_date = self._get_riyadh_datetime(year, month, 1)
                end_date = self._get_riyadh_datetime(year, month, days_list[-1], 23, 59, 59)
                start_date_utc = self._convert_to_utc_timezone(start_date)
                end_date_utc = self._convert_to_utc_timezone(end_date)
                attendance_records = self._get_attendance_records_batch(
                    start_date_utc, end_date_utc, [employee_id]
                )

            dept_summary = self._compute_department_summary_for_employee(
                employee_id, year, month, days_list,
                employee_attendance, attendance_records,
            )

            return {
                'success': True,
                'department_summary': dept_summary
            }

        except Exception as e:
            _logger.error(f"Error getting department summary: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _compute_department_summary_for_employee(
        self, employee_id, year, month, days_list,
        employee_attendance, attendance_records,
    ):
        """Core department summary logic (unchanged formulas)."""
        dept_summary = {}
        last_dept_by_date = {}
        riyadh_tz = self._get_riyadh_timezone()

        for record in attendance_records:
            if record['department_id']:
                dept_id = record['department_id']
                dept_name = record['department_name']

                if dept_id not in dept_summary:
                    dept_summary[dept_id] = {
                        'department_name': dept_name,
                        'absence_days': 0,
                        'late_hours': 0.0,
                        'overtime_hours': 0.0,
                        'present_days': 0
                    }

                record_date = record['date']
                last_dept_by_date[record_date] = dept_id

                if record['worked_hours']:
                    dept_summary[dept_id]['present_days'] += 1

                    if record['worked_hours'] > 8:
                        dept_summary[dept_id]['overtime_hours'] += record['worked_hours'] - 8

                    if record['worked_hours'] < 7:
                        dept_summary[dept_id]['late_hours'] += min(1.0, 8.0 - record['worked_hours'])

        employee_weekend_days = self._get_employee_weekend_days(employee_id)

        for day in days_list:
            day_data = employee_attendance.get(day, {})
            day_date = riyadh_tz.localize(datetime(year, month, day))

            if day_data.get('status') in ['weekend', 'holiday'] or day_date.weekday() in employee_weekend_days:
                continue

            if day_data.get('status') == 'absent':
                date_str = day_date.strftime('%Y-%m-%d')
                last_dept_id = None

                for check_date in sorted(last_dept_by_date.keys(), reverse=True):
                    if check_date < date_str:
                        last_dept_id = last_dept_by_date[check_date]
                        break

                if last_dept_id and last_dept_id in dept_summary:
                    dept_summary[last_dept_id]['absence_days'] += 1
                elif dept_summary:
                    first_dept = next(iter(dept_summary.values()))
                    first_dept['absence_days'] += 1

        return dept_summary

    def _get_department_summaries_for_employees(self, employees, year, month, all_attendance_data):
        """Build department summaries for multiple employees from cached data."""
        if not employees:
            return {}

        days_in_month = calendar.monthrange(year, month)[1]
        days_list = list(range(1, days_in_month + 1))
        department_summaries = {}

        for employee in employees:
            emp_id = employee['id']
            employee_attendance = all_attendance_data.get(emp_id, {})

            perf_cache = self._get_perf_cache()
            if perf_cache and emp_id in perf_cache.get('employee_attendance_records', {}):
                attendance_records = perf_cache['employee_attendance_records'][emp_id]
            else:
                start_date = self._get_riyadh_datetime(year, month, 1)
                end_date = self._get_riyadh_datetime(year, month, days_list[-1], 23, 59, 59)
                start_date_utc = self._convert_to_utc_timezone(start_date)
                end_date_utc = self._convert_to_utc_timezone(end_date)
                attendance_records = self._get_attendance_records_batch(
                    start_date_utc, end_date_utc, [emp_id]
                )

            department_summaries[emp_id] = self._compute_department_summary_for_employee(
                emp_id, year, month, days_list,
                employee_attendance, attendance_records,
            )

        return department_summaries

    def _get_monthly_summaries_for_employees(self, employees, year, month, all_attendance_data):
        """Bulk-fetch stored summaries; calculate missing ones using cached attendance."""
        monthly_summaries = {}
        if not employees:
            return monthly_summaries

        employee_ids = [emp['id'] for emp in employees]
        stored_by_employee = {}

        if 'hr.employee.monthly.summary' in self.env:
            summaries = self.env['hr.employee.monthly.summary'].search([
                ('employee_id', 'in', employee_ids),
                ('year', '=', year),
                ('month', '=', month),
            ])
            for summary in summaries:
                stored_by_employee[summary.employee_id.id] = {
                    'id': summary.id,
                    'total_absence_days': summary.total_absence_days,
                    'total_late_hours': summary.total_late_hours,
                    'total_overtime_hours': summary.total_overtime_hours,
                    'remaining_leave_days': summary.remaining_leave_days,
                }

        for employee in employees:
            emp_id = employee['id']
            if emp_id in stored_by_employee:
                monthly_summaries[emp_id] = stored_by_employee[emp_id]
            else:
                summary_result = self.get_employee_monthly_summary(
                    emp_id, year, month,
                    employee_attendance=all_attendance_data.get(emp_id),
                )
                if summary_result['success']:
                    monthly_summaries[emp_id] = summary_result['summary']
                else:
                    monthly_summaries[emp_id] = {
                        'total_absence_days': 0,
                        'total_late_hours': 0.0,
                        'total_overtime_hours': 0.0,
                        'remaining_leave_days': 0,
                    }

        return monthly_summaries

    def _get_leave_records_batch(self, start_date_utc, end_date_utc, employee_ids):
        """
        Get leave records for multiple employees in a single query
        Returns data converted to Riyadh timezone
        """
        if not employee_ids:
            return []

        Leave = self.env['hr.leave']
        records = Leave.search([
            ('employee_id', 'in', employee_ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', end_date_utc),
            ('date_to', '>=', start_date_utc)
        ])

        leave_list = []
        for record in records:
            # Convert leave dates to Riyadh timezone for display
            date_from_riyadh = self._convert_to_riyadh_timezone(record.date_from)
            date_to_riyadh = self._convert_to_riyadh_timezone(record.date_to)

            leave_list.append({
                'id': record.id,
                'employee_id': record.employee_id.id,
                'date_from': date_from_riyadh.isoformat() if date_from_riyadh else None,
                'date_to': date_to_riyadh.isoformat() if date_to_riyadh else None,
                'name': record.holiday_status_id.name if record.holiday_status_id else 'Leave',
                'number_of_days': record.number_of_days
            })

        return leave_list

    def _get_public_holidays(self, start_date, end_date):
        """
        Get public holidays for the date range in Riyadh timezone.
        Cached per request by month boundaries.
        """
        perf_cache = self._get_perf_cache()
        cache_key = (
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
        )
        if perf_cache and cache_key in perf_cache['public_holidays']:
            return perf_cache['public_holidays'][cache_key]

        holidays = {}

        try:
            PublicHoliday = self.env['hr.holidays.public.line']
            records = PublicHoliday.search([
                ('date', '>=', start_date.strftime('%Y-%m-%d')),
                ('date', '<=', end_date.strftime('%Y-%m-%d'))
            ])

            for record in records:
                holiday_date = record.date
                if hasattr(holiday_date, 'strftime'):
                    holidays[holiday_date.strftime('%Y-%m-%d')] = record.name
                else:
                    holidays[str(holiday_date)] = record.name

        except Exception:
            pass

        if perf_cache is not None:
            perf_cache['public_holidays'][cache_key] = holidays

        return holidays

    def _get_employee_leave_for_date(self, employee_id, date_str, leave_records):
        """
        Check if employee has leave on specific date (Riyadh timezone)
        """
        try:
            riyadh_tz = self._get_riyadh_timezone()
            target_date = riyadh_tz.localize(datetime.strptime(date_str, '%Y-%m-%d')).date()

            for leave in leave_records:
                if leave['employee_id'] == employee_id:
                    date_from = datetime.fromisoformat(leave['date_from']).date()
                    date_to = datetime.fromisoformat(leave['date_to']).date()

                    if date_from <= target_date <= date_to:
                        return leave
        except Exception as e:
            _logger.error(f"Error checking leave for date {date_str}: {str(e)}")

        return None

    def _get_employee_attendance_for_date(self, employee_id, date_str, attendance_records):
        """
        Get employee attendance record for specific date (Riyadh timezone)
        """
        for record in attendance_records:
            if record['employee_id'] == employee_id and record['date'] == date_str:
                return record

        return None

    def _calculate_attendance_statistics(self, year, month, days_list, employees, all_attendance_data=None):
        """
        Calculate attendance statistics for all employees (not just paginated)
        Using Riyadh timezone for working day calculations
        """
        if not employees:
            return {
                'total_employees': 0,
                'working_days': 0,
                'total_present': 0,
                'total_absent': 0,
                'total_leaves': 0,
                'total_holidays': 0,
                'avg_attendance': 0
            }

        if all_attendance_data is None:
            all_attendance_data = self._get_month_attendance_data(year, month, days_list, employees)

        riyadh_tz = self._get_riyadh_timezone()

        stats = {
            'total_employees': len(employees),
            'working_days': 0,
            'total_present': 0,
            'total_absent': 0,
            'total_leaves': 0,
            'total_holidays': 0,
            'avg_attendance': 0
        }

        working_days_set = set()
        for employee in employees:
            employee_weekend_days = self._get_employee_weekend_days(employee['id'])
            for day in days_list:
                day_date = riyadh_tz.localize(datetime(year, month, day))
                if day_date.weekday() not in employee_weekend_days:
                    working_days_set.add(day)

        stats['working_days'] = len(working_days_set)

        for employee in employees:
            employee_id = employee['id']
            if employee_id not in all_attendance_data:
                continue
            for day in days_list:
                day_data = all_attendance_data[employee_id].get(day, {})
                status = day_data.get('status', 'absent')

                if status == 'present':
                    stats['total_present'] += 1
                elif status == 'absent':
                    stats['total_absent'] += 1
                elif status == 'leave':
                    stats['total_leaves'] += 1
                elif status == 'holiday':
                    stats['total_holidays'] += 1

        total_working_slots = stats['working_days'] * stats['total_employees']
        if total_working_slots > 0:
            stats['avg_attendance'] = round((stats['total_present'] / total_working_slots) * 100, 2)

        return stats

    @api.model
    def update_attendance_status(self, employee_id, date, status, check_in=None, check_out=None):
        """
        Update attendance status for a specific employee and date
        All datetime operations use Riyadh timezone
        """
        try:
            # Validate inputs
            if not employee_id or not date or not status:
                return {'success': False, 'message': "Employee ID, date, and status are required"}

            # Validate employee exists
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                return {'success': False, 'message': "Employee not found"}

            # Parse date in Riyadh timezone
            try:
                riyadh_tz = self._get_riyadh_timezone()
                target_date = riyadh_tz.localize(datetime.strptime(date, '%Y-%m-%d'))
            except ValueError:
                return {'success': False, 'message': "Invalid date format. Use YYYY-MM-DD"}

            # Validate status
            valid_statuses = ['present', 'absent', 'holiday', 'leave']
            if status not in valid_statuses:
                return {'success': False, 'message': f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}

            # Handle different status updates
            if status == 'present':
                self._create_or_update_attendance(employee_id, target_date, check_in, check_out)
            elif status == 'absent':
                self._remove_attendance_if_exists(employee_id, target_date)
            elif status in ['holiday', 'leave']:
                self._handle_special_status(employee_id, target_date, status)

            return {
                'success': True,
                'message': "Attendance status updated successfully",
                'employee_name': employee.name,
                'date': date,
                'status': status
            }

        except Exception as e:
            _logger.error(f"Error updating attendance status: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _create_or_update_attendance(self, employee_id, target_date_riyadh, check_in=None, check_out=None):
        """
        Create or update attendance record for present status
        Uses Riyadh timezone for time handling
        """
        Attendance = self.env['hr.attendance']

        # Set default times in Riyadh timezone
        check_in_time_riyadh = target_date_riyadh.replace(hour=9, minute=0, second=0)
        check_out_time_riyadh = target_date_riyadh.replace(hour=17, minute=0, second=0)

        # Parse custom time strings if provided
        if check_in:
            try:
                time_parts = check_in.split(':')
                check_in_time_riyadh = target_date_riyadh.replace(
                    hour=int(time_parts[0]),
                    minute=int(time_parts[1]),
                    second=0
                )
            except (ValueError, IndexError):
                pass

        if check_out:
            try:
                time_parts = check_out.split(':')
                check_out_time_riyadh = target_date_riyadh.replace(
                    hour=int(time_parts[0]),
                    minute=int(time_parts[1]),
                    second=0
                )
            except (ValueError, IndexError):
                pass

        # Convert to UTC for database storage
        check_in_utc = self._convert_to_utc_timezone(check_in_time_riyadh)
        check_out_utc = self._convert_to_utc_timezone(check_out_time_riyadh)

        # Make datetime objects naive (remove timezone info) for Odoo
        if check_in_utc and hasattr(check_in_utc, 'replace'):
            check_in_utc = check_in_utc.replace(tzinfo=None)
        if check_out_utc and hasattr(check_out_utc, 'replace'):
            check_out_utc = check_out_utc.replace(tzinfo=None)

        # Check if attendance record already exists for the date
        start_of_day_utc = self._convert_to_utc_timezone(target_date_riyadh.replace(hour=0, minute=0, second=0))
        end_of_day_utc = self._convert_to_utc_timezone(target_date_riyadh.replace(hour=23, minute=59, second=59))

        # Make naive for database queries
        if start_of_day_utc and hasattr(start_of_day_utc, 'replace'):
            start_of_day_utc = start_of_day_utc.replace(tzinfo=None)
        if end_of_day_utc and hasattr(end_of_day_utc, 'replace'):
            end_of_day_utc = end_of_day_utc.replace(tzinfo=None)

        existing_record = Attendance.search([
            ('employee_id', '=', employee_id),
            ('check_in', '>=', start_of_day_utc),
            ('check_in', '<=', end_of_day_utc)
        ], limit=1)

        if existing_record:
            # Update existing record
            existing_record.write({
                'check_in': check_in_utc,
                'check_out': check_out_utc,
            })
        else:
            # Create new attendance record
            Attendance.create({
                'employee_id': employee_id,
                'check_in': check_in_utc,
                'check_out': check_out_utc,
            })

    def _remove_attendance_if_exists(self, employee_id, target_date_riyadh):
        """
        Remove attendance record for absent status
        Uses Riyadh timezone for date range
        """
        Attendance = self.env['hr.attendance']

        # Convert Riyadh date range to UTC for database query
        start_of_day_utc = self._convert_to_utc_timezone(target_date_riyadh.replace(hour=0, minute=0, second=0))
        end_of_day_utc = self._convert_to_utc_timezone(target_date_riyadh.replace(hour=23, minute=59, second=59))

        # Find and delete attendance record for the date
        existing_records = Attendance.search([
            ('employee_id', '=', employee_id),
            ('check_in', '>=', start_of_day_utc),
            ('check_in', '<=', end_of_day_utc)
        ])

        if existing_records:
            existing_records.unlink()

    def _handle_special_status(self, employee_id, target_date_riyadh, status):
        """
        Handle special statuses like holiday or leave
        """
        # Remove any existing attendance for this date
        self._remove_attendance_if_exists(employee_id, target_date_riyadh)

    @api.model
    def get_employee_summary(self, employee_id, year, month):
        """
        Get attendance summary for a specific employee and month
        All calculations use Riyadh timezone
        """
        try:
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                return {'success': False, 'message': "Employee not found"}

            # Get attendance data for the month
            days_in_month = calendar.monthrange(year, month)[1]
            days_list = list(range(1, days_in_month + 1))

            attendance_data = self._get_month_attendance_data(
                year, month, days_list, [{'id': employee_id}]
            )
            employee_attendance = attendance_data.get(employee_id, {})

            # Calculate summary
            summary = {
                'employee_name': employee.name,
                'department': employee.department_id.name if employee.department_id else '',
                'year': year,
                'month': month,
                'month_name': calendar.month_name[month],
                'total_days': len(days_list),
                'working_days': 0,
                'present_days': 0,
                'absent_days': 0,
                'leave_days': 0,
                'holiday_days': 0,
                'weekend_days': 0,
                'total_hours': 0.0,
                'attendance_percentage': 0.0
            }

            riyadh_tz = self._get_riyadh_timezone()

            for day, day_data in employee_attendance.items():
                status = day_data.get('status', 'absent')
                hours = day_data.get('hours', 0)

                if status == 'present':
                    summary['present_days'] += 1
                    summary['total_hours'] += hours
                elif status == 'absent':
                    summary['absent_days'] += 1
                elif status == 'leave':
                    summary['leave_days'] += 1
                elif status == 'holiday':
                    summary['holiday_days'] += 1
                elif status == 'weekend':
                    summary['weekend_days'] += 1

                # Count working days (exclude weekends and holidays) using Riyadh timezone
                # M&A
                employee_weekend_days = self._get_employee_weekend_days(employee_id)

                # Count working days based on employee's calendar
                day_date = riyadh_tz.localize(datetime(year, month, day))
                if status not in ['weekend', 'holiday'] and day_date.weekday() not in employee_weekend_days:
                    summary['working_days'] += 1

            # Calculate attendance percentage
            if summary['working_days'] > 0:
                summary['attendance_percentage'] = round(
                    (summary['present_days'] / summary['working_days']) * 100, 2
                )

            return {'success': True, 'summary': summary}

        except Exception as e:
            _logger.error(f"Error getting attendance summary: {str(e)}")
            return {'success': False, 'message': str(e)}

    @api.model
    def bulk_update_attendance(self, updates):
        """
        Bulk update multiple attendance records
        All datetime operations use Riyadh timezone
        """
        try:
            results = {
                'success_count': 0,
                'error_count': 0,
                'errors': []
            }

            for update in updates:
                try:
                    result = self.update_attendance_status(
                        update.get('employee_id'),
                        update.get('date'),
                        update.get('status'),
                        update.get('check_in'),
                        update.get('check_out')
                    )

                    if result.get('success'):
                        results['success_count'] += 1
                    else:
                        results['error_count'] += 1
                        results['errors'].append({
                            'employee_id': update.get('employee_id'),
                            'date': update.get('date'),
                            'error': result.get('message')
                        })

                except Exception as e:
                    results['error_count'] += 1
                    results['errors'].append({
                        'employee_id': update.get('employee_id'),
                        'date': update.get('date'),
                        'error': str(e)
                    })

            return results

        except Exception as e:
            _logger.error(f"Error in bulk update: {str(e)}")
            return {'success': False, 'message': str(e)}

    @api.model
    def _get_months_in_date_range(self, date_from, date_to):
        """Return sorted list of (year, month) tuples covering a date range."""
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        months = set()
        current = date_from
        while current <= date_to:
            months.add((current.year, current.month))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
        return sorted(months)

    @api.model
    def _load_period_attendance_data(self, employee_ids, date_from, date_to):
        """Batch-load per-day attendance data for employees across a date range."""
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        employees = [{'id': emp_id} for emp_id in employee_ids]
        period_data = {emp_id: {} for emp_id in employee_ids}

        for year, month in self._get_months_in_date_range(date_from, date_to):
            days_in_month = calendar.monthrange(year, month)[1]
            days_list = list(range(1, days_in_month + 1))
            month_data = self._get_month_attendance_data(year, month, days_list, employees)
            for emp_id in employee_ids:
                for day, day_data in month_data.get(emp_id, {}).items():
                    period_data[emp_id][(year, month, day)] = day_data

        return period_data

    @api.model
    def _compute_employee_period_metrics(self, employee_id, date_from, date_to, period_day_data):
        """Compute attendance and absence metrics for one employee over a date range."""
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        riyadh_tz = self._get_riyadh_timezone()
        employee_weekend_days = self._get_employee_weekend_days(employee_id)

        attendance_hours = 0.0
        absent_hours = 0.0
        absence_days = 0
        attendance_days = 0

        current = date_from
        while current <= date_to:
            day_key = (current.year, current.month, current.day)
            day_data = period_day_data.get(day_key, {})
            status = day_data.get('status', 'absent')
            day_date = riyadh_tz.localize(
                datetime(current.year, current.month, current.day)
            )

            if day_date.weekday() not in employee_weekend_days:
                if status == 'present':
                    attendance_days += 1
                    attendance_hours += day_data.get('hours', 0.0)
                elif status == 'absent':
                    absence_days += 1
                    absent_hours += self._get_expected_hours_for_day(employee_id, day_date)

            current += timedelta(days=1)

        return {
            'attendance_hours': round(attendance_hours, 2),
            'absent_hours': round(absent_hours, 2),
            'absence_days': absence_days,
            'attendance_days': attendance_days,
        }

    @api.model
    def _get_employee_period_daily_details(self, employee_id, date_from, date_to, period_day_data):
        """Return per-day attendance breakdown for one employee over a date range."""
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        riyadh_tz = self._get_riyadh_timezone()
        employee_weekend_days = self._get_employee_weekend_days(employee_id)
        details = []

        current = date_from
        while current <= date_to:
            day_key = (current.year, current.month, current.day)
            day_data = period_day_data.get(day_key, {})
            status = day_data.get('status', 'absent')
            day_date = riyadh_tz.localize(
                datetime(current.year, current.month, current.day)
            )

            if day_date.weekday() in employee_weekend_days and status != 'present':
                details.append({
                    'date': current,
                    'weekday_en': self._bilingual_weekday_name(current)[0],
                    'weekday_ar': self._bilingual_weekday_name(current)[1],
                    'status': 'weekend',
                    'attendance_hours': 0.0,
                    'absent_hours': 0.0,
                })
                current += timedelta(days=1)
                continue

            attendance_hours = 0.0
            absent_hours = 0.0
            if status == 'present':
                attendance_hours = round(day_data.get('hours', 0.0), 2)
            elif status == 'absent':
                absent_hours = round(
                    self._get_expected_hours_for_day(employee_id, day_date), 2
                )

            details.append({
                'date': current,
                'weekday_en': self._bilingual_weekday_name(current)[0],
                'weekday_ar': self._bilingual_weekday_name(current)[1],
                'status': status,
                'attendance_hours': attendance_hours,
                'absent_hours': absent_hours,
            })
            current += timedelta(days=1)

        return details

    @api.model
    def _get_period_days(self, date_from, date_to):
        """Return all dates in the selected period."""
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        days = []
        current = date_from
        while current <= date_to:
            days.append(current)
            current += timedelta(days=1)
        return days

    def _bilingual_weekday_name(self, day_date):
        """Return English and Arabic weekday names."""
        weekday_names = {
            0: ('Monday', 'الاثنين'),
            1: ('Tuesday', 'الثلاثاء'),
            2: ('Wednesday', 'الأربعاء'),
            3: ('Thursday', 'الخميس'),
            4: ('Friday', 'الجمعة'),
            5: ('Saturday', 'السبت'),
            6: ('Sunday', 'الأحد'),
        }
        return weekday_names.get(day_date.weekday(), (day_date.strftime('%A'), day_date.strftime('%A')))

    def _weekday_short_en(self, day_date):
        """Return short English weekday label for compact column headers."""
        shorts = {
            0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu',
            4: 'Fri', 5: 'Sat', 6: 'Sun',
        }
        return shorts.get(day_date.weekday(), day_date.strftime('%a'))

    def _bilingual_day_name_header(self, day_date):
        """Return compact bilingual weekday header using short English label."""
        weekday_ar = self._bilingual_weekday_name(day_date)[1]
        return '%s\n%s' % (self._weekday_short_en(day_date), weekday_ar)

    def _day_date_header(self, day_date):
        """Return compact date sub-header."""
        return day_date.strftime('%d-%m-%Y')

    def _parse_attendance_datetime(self, value):
        """Parse check-in/out values stored on day data."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                try:
                    return fields.Datetime.from_string(value)
                except (ValueError, TypeError):
                    return None
        return None

    def _format_attendance_day_cell(self, day_data):
        """
        Build daily cell text and style key.
        Present days show check-in / check-out times.
        Late check-in colors: >=08:45 yellow, >=08:50 dark yellow, >=09:00 red.
        Early check-out (before 16:30) uses yellow when there is no worse late check-in.
        """
        status = day_data.get('status', 'absent')
        if status == 'present':
            check_in_dt = self._parse_attendance_datetime(day_data.get('check_in'))
            check_out_dt = self._parse_attendance_datetime(day_data.get('check_out'))
            in_label = check_in_dt.strftime('%H:%M') if check_in_dt else '--'
            out_label = check_out_dt.strftime('%H:%M') if check_out_dt else '--'
            text = '%s\n%s' % (in_label, out_label)

            if check_in_dt:
                check_in_time = check_in_dt.time()
                if check_in_time >= time(9, 0):
                    return text, 'late_red'
                if check_in_time >= time(8, 50):
                    return text, 'late_dark'
                if check_in_time >= time(8, 45):
                    return text, 'warning'

            early_out = bool(
                check_out_dt and check_out_dt.time() < time(16, 30)
            )
            if early_out:
                return text, 'warning'
            return text, 'present'

        value, style_key = self._get_day_cell_display(day_data)
        return value, style_key

    def _write_employee_daily_cells(self, worksheet, row, employee_period_data, period_days, col_offset, formats, is_odd):
        """Write daily attendance values for one employee row."""
        present_fmt = formats['present_odd'] if is_odd else formats['present_even']
        warning_fmt = formats['warning_odd'] if is_odd else formats['warning_even']
        late_dark_fmt = formats['late_dark_odd'] if is_odd else formats['late_dark_even']
        late_red_fmt = formats['late_red_odd'] if is_odd else formats['late_red_even']
        day_num_fmt = formats['day_odd'] if is_odd else formats['day_even']
        day_text_fmt = formats['day_text_odd'] if is_odd else formats['day_text_even']
        weekend_fmt = formats['weekend_odd'] if is_odd else formats['weekend_even']
        absent_fmt = formats['absent_odd'] if is_odd else formats['absent_even']

        for offset, day_date in enumerate(period_days):
            day_key = (day_date.year, day_date.month, day_date.day)
            day_data = employee_period_data.get(day_key, {'status': 'absent', 'hours': 0.0})
            value, style_key = self._format_attendance_day_cell(day_data)
            col = col_offset + offset
            if style_key == 'present':
                worksheet.write(row, col, value, present_fmt)
            elif style_key == 'warning':
                worksheet.write(row, col, value, warning_fmt)
            elif style_key == 'late_dark':
                worksheet.write(row, col, value, late_dark_fmt)
            elif style_key == 'late_red':
                worksheet.write(row, col, value, late_red_fmt)
            elif style_key == 'day' and isinstance(value, (int, float)):
                worksheet.write(row, col, value, day_num_fmt)
            elif style_key == 'weekend':
                worksheet.write(row, col, value, weekend_fmt)
            elif style_key == 'absent':
                worksheet.write(row, col, value, absent_fmt)
            else:
                worksheet.write(row, col, value, day_text_fmt)

    def _bilingual_day_date_cell(self, day_date):
        """Return bilingual day and date for a detail row cell."""
        weekday_en, weekday_ar = self._bilingual_weekday_name(day_date)
        date_str = day_date.strftime('%Y-%m-%d')
        return '%s\n%s\n%s' % (weekday_en, weekday_ar, date_str)

    def _get_day_cell_display(self, day_data):
        """Return display value and style key for a daily summary cell."""
        status = day_data.get('status', 'absent')
        hours = day_data.get('hours', 0.0)
        if status == 'present' and hours > 0:
            return round(hours, 2), 'day'
        if status == 'weekend':
            return '-', 'weekend'
        if status == 'leave':
            return 'L', 'leave'
        if status == 'holiday':
            return 'H', 'holiday'
        if status == 'absent':
            return 'A', 'absent'
        return '', 'day'

    def _bilingual_status_label(self, status):
        """Return bilingual status label for detail rows."""
        status_labels = {
            'present': ('Present', 'حاضر'),
            'absent': ('Absent', 'غائب'),
            'leave': ('Leave', 'إجازة'),
            'holiday': ('Holiday', 'عطلة'),
            'weekend': ('Weekend', 'عطلة نهاية الأسبوع'),
        }
        english, arabic = status_labels.get(status, (status.title(), status))
        return '%s\n%s' % (english, arabic)

    def _bilingual_report_label(self, english_text):
        """Return a bilingual English/Arabic label for Excel report output."""
        arabic_labels = {
            'Attendance Summary Report': 'تقرير ملخص الحضور',
            'Period': 'الفترة',
            'Department': 'القسم',
            'All Departments': 'جميع الأقسام',
            'Employee': 'الموظف',
            'Attendance Hours': 'ساعات الحضور',
            'Absent Hours': 'ساعات الغياب',
            'Absence Days': 'أيام الغياب',
            'Attendance Days': 'أيام الحضور',
            'Total': 'الإجمالي',
            'Employees': 'الموظفون',
            'Generated on': 'تاريخ الإنشاء',
            'Attendance Details': 'تفاصيل الحضور',
            'Date': 'التاريخ',
            'Day': 'اليوم',
            'Status': 'الحالة',
        }
        arabic_text = arabic_labels.get(english_text)
        if arabic_text:
            return '%s\n%s' % (english_text, arabic_text)
        return english_text

    def _bilingual_meta_value(self, label_key, value_en, value_ar=None):
        """Format a bilingual metadata line with full English and Arabic values."""
        if value_ar is None:
            value_ar = value_en
        arabic_labels = {
            'Period': 'الفترة',
            'Department': 'القسم',
        }
        arabic_label = arabic_labels.get(label_key, label_key)
        return '%s: %s\n%s: %s' % (label_key, value_en, arabic_label, value_ar)

    def _get_attendance_report_formats(self, workbook):
        """Return reusable cell formats for the attendance summary Excel report."""
        base_font = {'font_name': 'Arial', 'font_size': 10, 'reading_order': 2}
        soft_border = {'border': 1, 'border_color': '#D0D7DE'}
        return {
            'title_banner': workbook.add_format(dict(base_font, **{
                'bold': True,
                'font_size': 14,
                'font_color': '#FFFFFF',
                'bg_color': '#714B67',
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
            })),
            'meta': workbook.add_format(dict(base_font, **{
                'font_size': 11,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'font_color': '#4A5568',
                'bg_color': '#F4F6F8',
                'border': 1,
                'border_color': '#E2E8F0',
            })),
            'header': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'font_color': '#FFFFFF',
                'bg_color': '#5C4D56',
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
            })),
            'header_date': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'font_size': 9,
                'font_color': '#FFFFFF',
                'bg_color': '#6B5D65',
                'align': 'center',
                'valign': 'vcenter',
            })),
            'header_day': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'font_size': 9,
                'font_color': '#FFFFFF',
                'bg_color': '#5C4D56',
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': False,
            })),
            'header_compact': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'font_size': 9,
                'font_color': '#FFFFFF',
                'bg_color': '#5C4D56',
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
            })),
            'text_even': workbook.add_format(dict(base_font, **soft_border, **{
                'align': 'right',
                'valign': 'vcenter',
                'bg_color': '#FFFFFF',
            })),
            'text_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'align': 'right',
                'valign': 'vcenter',
                'bg_color': '#F8F9FA',
            })),
            'number_even': workbook.add_format(dict(base_font, **soft_border, **{
                'num_format': '#,##0.00',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#FFFFFF',
            })),
            'number_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'num_format': '#,##0.00',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#F8F9FA',
            })),
            'int_even': workbook.add_format(dict(base_font, **soft_border, **{
                'num_format': '#,##0',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#FFFFFF',
            })),
            'int_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'num_format': '#,##0',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#F8F9FA',
            })),
            'total_label': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'align': 'right',
                'valign': 'vcenter',
                'bg_color': '#EDE7EB',
                'font_color': '#714B67',
                'top': 2,
                'top_color': '#714B67',
            })),
            'total_number': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'num_format': '#,##0.00',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#EDE7EB',
                'font_color': '#714B67',
                'top': 2,
                'top_color': '#714B67',
            })),
            'total_int': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'num_format': '#,##0',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#EDE7EB',
                'font_color': '#714B67',
                'top': 2,
                'top_color': '#714B67',
            })),
            'footer': workbook.add_format(dict(base_font, **{
                'align': 'right',
                'font_color': '#9CA3AF',
                'font_size': 9,
                'italic': True,
            })),
            'date_even': workbook.add_format(dict(base_font, **soft_border, **{
                'num_format': 'yyyy-mm-dd',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#FFFFFF',
            })),
            'date_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'num_format': 'yyyy-mm-dd',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#F8F9FA',
            })),
            'status_even': workbook.add_format(dict(base_font, **soft_border, **{
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'bg_color': '#FFFFFF',
            })),
            'status_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'bg_color': '#F8F9FA',
            })),
            'day_even': workbook.add_format(dict(base_font, **soft_border, **{
                'num_format': '#,##0.00',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#FFFFFF',
            })),
            'day_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'num_format': '#,##0.00',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#F8F9FA',
            })),
            'day_text_even': workbook.add_format(dict(base_font, **soft_border, **{
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#FFFFFF',
                'font_color': '#6B7280',
            })),
            'day_text_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#F8F9FA',
                'font_color': '#6B7280',
            })),
            'weekend_even': workbook.add_format(dict(base_font, **soft_border, **{
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#E9ECEF',
                'font_color': '#9CA3AF',
            })),
            'weekend_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#DEE2E6',
                'font_color': '#9CA3AF',
            })),
            'absent_even': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#FFC7CE',
                'font_color': '#9C0006',
            })),
            'absent_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#FFB3BA',
                'font_color': '#9C0006',
            })),
            'present_even': workbook.add_format(dict(base_font, **soft_border, **{
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'font_size': 9,
                'bg_color': '#FFFFFF',
            })),
            'present_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'font_size': 9,
                'bg_color': '#F8F9FA',
            })),
            'warning_even': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'font_size': 9,
                'bg_color': '#FFEB9C',
                'font_color': '#9C6500',
            })),
            'warning_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'font_size': 9,
                'bg_color': '#FFF2CC',
                'font_color': '#9C6500',
            })),
            'late_dark_even': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'font_size': 9,
                'bg_color': '#FFFF00',
                'font_color': '#5C3317',
            })),
            'late_dark_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'font_size': 9,
                'bg_color': '#FFFF00',
                'font_color': '#5C3317',
            })),
            'late_red_even': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'font_size': 9,
                'bg_color': '#FF4D4D',
                'font_color': '#7A0000',
            })),
            'late_red_odd': workbook.add_format(dict(base_font, **soft_border, **{
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'font_size': 9,
                'bg_color': '#FF6B6B',
                'font_color': '#7A0000',
            })),
        }

    def _write_attendance_summary_sheet(
        self, workbook, formats, employees, period_data, date_from, date_to,
        department_line, period_value,
    ):
        """Write the summary worksheet with per-employee totals."""
        worksheet = workbook.add_worksheet('Attendance Summary')
        worksheet.right_to_left()
        worksheet.hide_gridlines(2)
        worksheet.set_landscape()
        worksheet.set_margins(left=0.5, right=0.5, top=0.6, bottom=0.6)

        headers = [
            'Employee', 'Department', 'Attendance Hours',
            'Absent Hours', 'Absence Days', 'Attendance Days',
        ]
        last_col = len(headers) - 1
        header_row = 5
        data_start_row = header_row + 1

        worksheet.set_row(0, 8)
        worksheet.set_row(1, 52)
        worksheet.set_row(2, 42)
        worksheet.set_row(3, 42)
        worksheet.set_row(4, 10)
        worksheet.set_row(header_row, 50)

        worksheet.merge_range(
            1, 0, 1, last_col,
            self._bilingual_report_label('Attendance Summary Report'),
            formats['title_banner'],
        )
        worksheet.merge_range(
            2, 0, 2, last_col,
            self._bilingual_meta_value('Period', period_value),
            formats['meta'],
        )
        worksheet.merge_range(
            3, 0, 3, last_col,
            department_line,
            formats['meta'],
        )

        for col, header in enumerate(headers):
            worksheet.write(header_row, col, self._bilingual_report_label(header), formats['header'])

        worksheet.set_column(0, 0, 32)
        worksheet.set_column(1, 1, 26)
        worksheet.set_column(2, 3, 16)
        worksheet.set_column(4, 5, 14)

        totals = {
            'attendance_hours': 0.0,
            'absent_hours': 0.0,
            'absence_days': 0,
            'attendance_days': 0,
        }
        row = data_start_row
        for index, employee in enumerate(employees):
            metrics = self._compute_employee_period_metrics(
                employee.id, date_from, date_to, period_data.get(employee.id, {})
            )
            is_odd = index % 2 == 1
            text_fmt = formats['text_odd'] if is_odd else formats['text_even']
            num_fmt = formats['number_odd'] if is_odd else formats['number_even']
            int_fmt = formats['int_odd'] if is_odd else formats['int_even']

            worksheet.set_row(row, 22)
            worksheet.write(row, 0, employee.name, text_fmt)
            worksheet.write(row, 1, employee.department_id.name or '', text_fmt)
            worksheet.write(row, 2, metrics['attendance_hours'], num_fmt)
            worksheet.write(row, 3, metrics['absent_hours'], num_fmt)
            worksheet.write(row, 4, metrics['absence_days'], int_fmt)
            worksheet.write(row, 5, metrics['attendance_days'], int_fmt)

            totals['attendance_hours'] += metrics['attendance_hours']
            totals['absent_hours'] += metrics['absent_hours']
            totals['absence_days'] += metrics['absence_days']
            totals['attendance_days'] += metrics['attendance_days']
            row += 1

        worksheet.set_row(row, 26)
        worksheet.write(row, 0, self._bilingual_report_label('Total'), formats['total_label'])
        worksheet.write(
            row, 1,
            '%s: %s' % (self._bilingual_report_label('Employees'), len(employees)),
            formats['total_label'],
        )
        worksheet.write(row, 2, totals['attendance_hours'], formats['total_number'])
        worksheet.write(row, 3, totals['absent_hours'], formats['total_number'])
        worksheet.write(row, 4, totals['absence_days'], formats['total_int'])
        worksheet.write(row, 5, totals['attendance_days'], formats['total_int'])

        footer_row = row + 2
        generated_on = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        ).strftime('%Y-%m-%d %H:%M')
        worksheet.merge_range(
            footer_row, 0, footer_row, last_col,
            '%s: %s' % (self._bilingual_report_label('Generated on'), generated_on),
            formats['footer'],
        )

        worksheet.freeze_panes(data_start_row, 0)
        worksheet.autofilter(header_row, 0, row, last_col)
        worksheet.print_area(0, 0, footer_row, last_col)
        return worksheet

    def _write_attendance_details_sheet(
        self, workbook, formats, employees, period_data, date_from, date_to,
        department_line, period_value,
    ):
        """Write daily grid with totals plus one column per day (two-row headers)."""
        worksheet = workbook.add_worksheet('Attendance Details')
        worksheet.right_to_left()
        worksheet.hide_gridlines(2)
        worksheet.set_landscape()
        worksheet.set_margins(left=0.5, right=0.5, top=0.6, bottom=0.6)

        summary_headers = [
            'Employee', 'Department', 'Attendance Hours',
            'Absent Hours', 'Absence Days', 'Attendance Days',
        ]
        period_days = self._get_period_days(date_from, date_to)
        summary_col_count = len(summary_headers)
        last_col = summary_col_count + len(period_days) - 1
        header_row = 5
        date_header_row = 6
        data_start_row = 7

        worksheet.set_row(0, 8)
        worksheet.set_row(1, 52)
        worksheet.set_row(2, 42)
        worksheet.set_row(3, 42)
        worksheet.set_row(4, 10)
        worksheet.set_row(header_row, 30)
        worksheet.set_row(date_header_row, 16)

        worksheet.merge_range(
            1, 0, 1, last_col,
            self._bilingual_report_label('Attendance Details'),
            formats['title_banner'],
        )
        worksheet.merge_range(
            2, 0, 2, last_col,
            self._bilingual_meta_value('Period', period_value),
            formats['meta'],
        )
        worksheet.merge_range(
            3, 0, 3, last_col,
            department_line,
            formats['meta'],
        )

        for col, header in enumerate(summary_headers):
            worksheet.merge_range(
                header_row, col, date_header_row, col,
                self._bilingual_report_label(header),
                formats['header_compact'],
            )

        for offset, day_date in enumerate(period_days):
            col = summary_col_count + offset
            worksheet.write(
                header_row, col,
                self._bilingual_day_name_header(day_date),
                formats['header_day'],
            )
            worksheet.write(
                date_header_row, col,
                self._day_date_header(day_date),
                formats['header_date'],
            )

        worksheet.set_column(0, 0, 24)
        worksheet.set_column(1, 1, 18)
        worksheet.set_column(2, 3, 15)
        worksheet.set_column(4, 5, 14)
        if period_days:
            worksheet.set_column(summary_col_count, last_col, 12)

        totals = {
            'attendance_hours': 0.0,
            'absent_hours': 0.0,
            'absence_days': 0,
            'attendance_days': 0,
        }
        row = data_start_row
        for index, employee in enumerate(employees):
            metrics = self._compute_employee_period_metrics(
                employee.id, date_from, date_to, period_data.get(employee.id, {})
            )
            is_odd = index % 2 == 1
            text_fmt = formats['text_odd'] if is_odd else formats['text_even']
            num_fmt = formats['number_odd'] if is_odd else formats['number_even']
            int_fmt = formats['int_odd'] if is_odd else formats['int_even']
            employee_period_data = period_data.get(employee.id, {})

            worksheet.set_row(row, 30)
            worksheet.write(row, 0, employee.name, text_fmt)
            worksheet.write(row, 1, employee.department_id.name or '', text_fmt)
            worksheet.write(row, 2, metrics['attendance_hours'], num_fmt)
            worksheet.write(row, 3, metrics['absent_hours'], num_fmt)
            worksheet.write(row, 4, metrics['absence_days'], int_fmt)
            worksheet.write(row, 5, metrics['attendance_days'], int_fmt)
            self._write_employee_daily_cells(
                worksheet, row, employee_period_data, period_days,
                summary_col_count, formats, is_odd,
            )

            totals['attendance_hours'] += metrics['attendance_hours']
            totals['absent_hours'] += metrics['absent_hours']
            totals['absence_days'] += metrics['absence_days']
            totals['attendance_days'] += metrics['attendance_days']
            row += 1

        worksheet.set_row(row, 26)
        worksheet.write(row, 0, self._bilingual_report_label('Total'), formats['total_label'])
        worksheet.write(
            row, 1,
            '%s: %s' % (self._bilingual_report_label('Employees'), len(employees)),
            formats['total_label'],
        )
        worksheet.write(row, 2, totals['attendance_hours'], formats['total_number'])
        worksheet.write(row, 3, totals['absent_hours'], formats['total_number'])
        worksheet.write(row, 4, totals['absence_days'], formats['total_int'])
        worksheet.write(row, 5, totals['attendance_days'], formats['total_int'])

        footer_row = row + 2
        generated_on = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        ).strftime('%Y-%m-%d %H:%M')
        worksheet.merge_range(
            footer_row, 0, footer_row, last_col,
            '%s: %s' % (self._bilingual_report_label('Generated on'), generated_on),
            formats['footer'],
        )

        worksheet.freeze_panes(data_start_row, summary_col_count)
        worksheet.autofilter(header_row, 0, row, last_col)
        worksheet.print_area(0, 0, footer_row, last_col)
        return worksheet

    @api.model
    def generate_attendance_summary_excel(self, date_from, date_to, department_ids=None, print_all=False):
        """Generate an Excel report with per-employee attendance summary for a date range."""
        try:
            import xlsxwriter

            date_from = fields.Date.to_date(date_from)
            date_to = fields.Date.to_date(date_to)
            department_ids = department_ids or []

            domain = [('active', '=', True)]
            if not print_all and department_ids:
                domain.append(('department_id', 'in', department_ids))

            employees = self.env['hr.employee'].search(domain, order='name')
            if not employees:
                raise UserError(_("No employees found for the selected criteria."))

            period_data = self._load_period_attendance_data(employees.ids, date_from, date_to)

            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            formats = self._get_attendance_report_formats(workbook)

            departments = self.env['hr.department'].browse(department_ids) if department_ids else self.env['hr.department']
            department_name = ', '.join(departments.mapped('name')) if departments else False
            period_value = '%s - %s' % (date_from, date_to)
            if print_all or not department_name:
                department_line = self._bilingual_meta_value(
                    'Department', 'All Departments', 'جميع الأقسام'
                )
            else:
                department_line = self._bilingual_meta_value(
                    'Department', department_name, department_name
                )

            self._write_attendance_summary_sheet(
                workbook, formats, employees, period_data, date_from, date_to,
                department_line, period_value,
            )
            self._write_attendance_details_sheet(
                workbook, formats, employees, period_data, date_from, date_to,
                department_line, period_value,
            )

            workbook.close()

            filename = 'attendance_summary_%s_%s.xlsx' % (
                date_from.strftime('%Y%m%d'),
                date_to.strftime('%Y%m%d'),
            )
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(output.getvalue()),
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            })

            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'self',
            }

        except ImportError:
            raise UserError(_("xlsxwriter library is required for Excel export."))
        except UserError:
            raise
        except Exception as e:
            _logger.error("Error generating attendance summary report: %s", str(e))
            raise UserError(_("Error generating report: %s") % str(e))

    @api.model
    def export_attendance_data(self, year, month, format='xlsx', filters=None):
        """
        Export attendance data for a specific month
        All datetime operations use Riyadh timezone
        """
        try:
            # Get all attendance data (no pagination for export)
            result = self.get_attendance_data(year, month, filters, {'page': 1, 'page_size': 'all'})

            if not result['success']:
                return result

            if format == 'json':
                return {
                    'success': True,
                    'data': result,
                    'filename': f'attendance_{year}_{month:02d}.json'
                }
            elif format == 'csv':
                return self._export_to_csv(result, year, month)
            elif format == 'xlsx':
                return self._export_to_xlsx(result, year, month)
            else:
                return {'success': False, 'message': "Unsupported export format"}

        except Exception as e:
            _logger.error(f"Error exporting attendance data: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _export_to_csv(self, attendance_data, year, month):
        """Export attendance data to CSV format"""
        try:
            import csv

            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            header = ['Employee Name', 'Department'] + [f'Day {day}' for day in attendance_data['days_in_month']]
            writer.writerow(header)

            # Write data rows
            for employee in attendance_data['employees']:
                row = [employee['name'], employee['department_name']]
                employee_attendance = attendance_data['attendance_data'].get(employee['id'], {})

                for day in attendance_data['days_in_month']:
                    day_data = employee_attendance.get(day, {})
                    status = day_data.get('status', 'absent')
                    hours = day_data.get('hours', 0)

                    if status == 'present' and hours > 0:
                        cell_value = f"{status} ({hours}h)"
                    else:
                        cell_value = status

                    row.append(cell_value)

                writer.writerow(row)

            # Convert to base64 for download
            csv_data = output.getvalue().encode('utf-8')
            csv_base64 = base64.b64encode(csv_data).decode('utf-8')

            return {
                'success': True,
                'file_content': csv_base64,
                'filename': f'attendance_{year}_{month:02d}.csv',
                'mimetype': 'text/csv'
            }

        except Exception as e:
            return {'success': False, 'message': f"CSV export error: {str(e)}"}

    def _export_to_xlsx(self, attendance_data, year, month):
        """Export attendance data to Excel format"""
        try:
            import xlsxwriter

            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet('Attendance')

            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'align': 'center'
            })

            present_format = workbook.add_format({'bg_color': '#C6EFCE'})
            absent_format = workbook.add_format({'bg_color': '#FFC7CE'})
            holiday_format = workbook.add_format({'bg_color': '#FFEB9C'})
            leave_format = workbook.add_format({'bg_color': '#D7E4BC'})
            weekend_format = workbook.add_format({'bg_color': '#F2F2F2'})

            # Write headers
            worksheet.write(0, 0, 'Employee Name', header_format)
            worksheet.write(0, 1, 'Department', header_format)

            for i, day in enumerate(attendance_data['days_in_month']):
                worksheet.write(0, i + 2, f'Day {day}', header_format)

            # Write data
            for row_idx, employee in enumerate(attendance_data['employees'], 1):
                worksheet.write(row_idx, 0, employee['name'])
                worksheet.write(row_idx, 1, employee['department_name'])

                employee_attendance = attendance_data['attendance_data'].get(employee['id'], {})

                for col_idx, day in enumerate(attendance_data['days_in_month']):
                    day_data = employee_attendance.get(day, {})
                    status = day_data.get('status', 'absent')
                    hours = day_data.get('hours', 0)

                    cell_value = status
                    cell_format = None

                    if status == 'present':
                        if hours > 0:
                            cell_value = f"{status} ({hours}h)"
                        cell_format = present_format
                    elif status == 'absent':
                        cell_format = absent_format
                    elif status == 'holiday':
                        cell_format = holiday_format
                    elif status == 'leave':
                        cell_format = leave_format
                    elif status == 'weekend':
                        cell_format = weekend_format

                    worksheet.write(row_idx, col_idx + 2, cell_value, cell_format)

            # Add statistics sheet
            stats_sheet = workbook.add_worksheet('Statistics')
            stats = attendance_data['statistics']

            stats_sheet.write(0, 0, 'Attendance Statistics', header_format)
            stats_sheet.write(2, 0, 'Total Employees:', header_format)
            stats_sheet.write(2, 1, stats['total_employees'])
            stats_sheet.write(3, 0, 'Working Days:', header_format)
            stats_sheet.write(3, 1, stats['working_days'])
            stats_sheet.write(4, 0, 'Average Attendance:', header_format)
            stats_sheet.write(4, 1, f"{stats['avg_attendance']}%")
            stats_sheet.write(5, 0, 'Total Present:', header_format)
            stats_sheet.write(5, 1, stats['total_present'])
            stats_sheet.write(6, 0, 'Total Absent:', header_format)
            stats_sheet.write(6, 1, stats['total_absent'])

            workbook.close()

            # Convert to base64
            xlsx_data = output.getvalue()
            xlsx_base64 = base64.b64encode(xlsx_data).decode('utf-8')

            return {
                'success': True,
                'file_content': xlsx_base64,
                'filename': f'attendance_{year}_{month:02d}.xlsx',
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }

        except ImportError:
            return {'success': False, 'message': "xlsxwriter library is required for Excel export"}
        except Exception as e:
            return {'success': False, 'message': f"Excel export error: {str(e)}"}

    @api.model
    def get_day_details(self, employee_id, date):
        """
        Get detailed information for a specific employee and date
        All datetime operations use Riyadh timezone
        """
        try:
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                return {'success': False, 'message': "Employee not found"}

            # Parse date in Riyadh timezone
            riyadh_tz = self._get_riyadh_timezone()
            target_date_riyadh = riyadh_tz.localize(datetime.strptime(date, '%Y-%m-%d'))

            # Convert to UTC for database query
            start_of_day_utc = self._convert_to_utc_timezone(target_date_riyadh.replace(hour=0, minute=0, second=0))
            end_of_day_utc = self._convert_to_utc_timezone(target_date_riyadh.replace(hour=23, minute=59, second=59))

            # Get attendance records for the date
            Attendance = self.env['hr.attendance']
            attendance_records = Attendance.search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', start_of_day_utc),
                ('check_in', '<=', end_of_day_utc)
            ])

            attendance_details = []
            for record in attendance_records:
                # Convert times back to Riyadh timezone for display
                check_in_riyadh = self._convert_to_riyadh_timezone(record.check_in)
                check_out_riyadh = self._convert_to_riyadh_timezone(record.check_out)

                attendance_details.append({
                    'id': record.id,
                    'check_in': check_in_riyadh.isoformat() if check_in_riyadh else None,
                    'check_out': check_out_riyadh.isoformat() if check_out_riyadh else None,
                    'worked_hours': record.worked_hours,
                    'department_id': record.attendance_employee_department.id if record.attendance_employee_department else None,
                    'department_name': record.attendance_employee_department.name if record.attendance_employee_department else 'No Department'
                })

            return {
                'success': True,
                'employee': {
                    'id': employee.id,
                    'name': employee.name,
                    'department': employee.department_id.name if employee.department_id else '',
                    'job_title': employee.job_title or '',
                    'work_email': employee.work_email or '',
                    'work_phone': employee.work_phone or ''
                },
                'date': date,
                'attendance_records': attendance_details
            }

        except Exception as e:
            _logger.error(f"Error getting day details: {str(e)}")
            return {'success': False, 'message': str(e)}

    @api.model
    def update_day_details(self, employee_id, date, status, check_in=None, check_out=None, break_time=0, notes=""):
        """
        Update detailed day information
        All datetime operations use Riyadh timezone
        """
        try:
            # Update basic attendance status
            result = self.update_attendance_status(employee_id, date, status, check_in, check_out)

            if result['success'] and status == 'present':
                # Calculate total hours if both times provided (in Riyadh timezone)
                total_hours = 0
                if check_in and check_out:
                    try:
                        riyadh_tz = self._get_riyadh_timezone()
                        check_in_time = riyadh_tz.localize(datetime.strptime(f"{date} {check_in}", '%Y-%m-%d %H:%M'))
                        check_out_time = riyadh_tz.localize(datetime.strptime(f"{date} {check_out}", '%Y-%m-%d %H:%M'))

                        # Convert to UTC and make naive for Odoo
                        check_in_utc_naive = check_in_time.astimezone(pytz.UTC).replace(tzinfo=None)
                        check_out_utc_naive = check_out_time.astimezone(pytz.UTC).replace(tzinfo=None)

                        diff_hours = (check_out_utc_naive - check_in_utc_naive).total_seconds() / 3600
                        total_hours = max(0, diff_hours - float(break_time or 0))

                        # If updating an existing attendance record, use naive UTC times
                        result['check_in_utc'] = check_in_utc_naive
                        result['check_out_utc'] = check_out_utc_naive

                    except (ValueError, TypeError):
                        pass

                result['total_hours'] = round(total_hours, 2)

            return result

        except Exception as e:
            _logger.error(f"Error updating day details: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _get_manual_absence_days(self, employee_id, year, month):
        """Return manually overridden absence days when set, otherwise None."""
        if 'hr.employee.monthly.summary' not in self.env:
            return None

        summary = self.env['hr.employee.monthly.summary'].search([
            ('employee_id', '=', employee_id),
            ('year', '=', year),
            ('month', '=', month),
        ], limit=1)
        if summary and summary.absence_days_manually_set:
            return summary.total_absence_days
        return None

    def _get_manual_late_hours(self, employee_id, year, month):
        """Return manually overridden late hours when set, otherwise None."""
        if 'hr.employee.monthly.summary' not in self.env:
            return None

        summary = self.env['hr.employee.monthly.summary'].search([
            ('employee_id', '=', employee_id),
            ('year', '=', year),
            ('month', '=', month),
        ], limit=1)
        if summary and summary.late_hours_manually_set:
            return summary.total_late_hours
        return None

    def _get_dashboard_metrics_for_payslip(self, employee_id, year, month):
        """Same totals shown on the Attendance dashboard (monthly summary columns)."""
        result = self.get_employee_monthly_summary(employee_id, year, month)
        if result.get('success') and result.get('summary'):
            summary = result['summary']
            return {
                'absence_days': summary.get('total_absence_days', 0) or 0,
                'late_hours': summary.get('total_late_hours', 0.0) or 0.0,
                'overtime_hours': summary.get('total_overtime_hours', 0.0) or 0.0,
                'remaining_leave_days': summary.get('remaining_leave_days', 0) or 0,
            }
        return {
            'absence_days': 0,
            'late_hours': 0.0,
            'overtime_hours': 0.0,
            'remaining_leave_days': 0,
        }

    def _get_payslip_primary_dept_id(self, employee_id, dept_summary):
        """Department that receives the full dashboard totals (avoid double-counting)."""
        employee = self.env['hr.employee'].browse(employee_id)
        main_dept_id = employee.department_id.id if employee.department_id else None
        if main_dept_id and main_dept_id in dept_summary:
            return main_dept_id
        if dept_summary:
            return next(iter(dept_summary.keys()))
        return None

    def _get_payslip_absence_days(self, employee_id, year, month, dept_id, dept_summary, dept_data):
        """Use dashboard monthly absence totals on the primary department payslip only."""
        metrics = self._get_dashboard_metrics_for_payslip(employee_id, year, month)
        target_dept_id = self._get_payslip_primary_dept_id(employee_id, dept_summary)
        if target_dept_id is None:
            return metrics['absence_days']
        return metrics['absence_days'] if dept_id == target_dept_id else 0

    def _get_payslip_late_hours(self, employee_id, year, month, dept_id, dept_summary, dept_data):
        """Use dashboard monthly late-hour totals on the primary department payslip only."""
        metrics = self._get_dashboard_metrics_for_payslip(employee_id, year, month)
        target_dept_id = self._get_payslip_primary_dept_id(employee_id, dept_summary)
        if target_dept_id is None:
            return metrics['late_hours']
        return metrics['late_hours'] if dept_id == target_dept_id else 0.0

    @api.model
    def create_payslips_from_attendance(self, year, month, filters=None, pagination=None):
        """
        Create payslips for employees in current page view based on department attendance data
        """
        try:
            self = self._ensure_perf_cache()

            # Get paginated employees (same logic as get_attendance_data)
            filters = filters or {}
            pagination = pagination or {'page': 1, 'page_size': 50}

            # Get all employees first (apply basic filters)
            basic_filters = {k: v for k, v in filters.items() if k != 'status_filter'}
            all_employees = self._get_employees(basic_filters)

            if not all_employees:
                return {'success': False, 'message': 'No employees found'}

            # Apply status filter if needed
            days_in_month = calendar.monthrange(year, month)[1]
            days_list = list(range(1, days_in_month + 1))

            if filters.get('status_filter'):
                all_employees = self._filter_employees_by_status(
                    all_employees, filters['status_filter'], year, month, days_list
                )

            # Get paginated employees (only process current page)
            paginated_result = self._get_paginated_employees(all_employees, pagination)
            current_page_employees = paginated_result['employees']

            if not current_page_employees:
                return {'success': False, 'message': 'No employees in current page'}

            # Warm request cache so per-employee department summaries reuse attendance data
            self._get_month_attendance_data(year, month, days_list, current_page_employees)

            # Get date range for the month
            start_date = datetime(year, month, 1).date()
            end_date = datetime(year, month, days_in_month).date()

            # Check if hr.payslip model exists
            if 'hr.payslip' not in self.env:
                return {'success': False, 'message': 'Payslip model not found'}

            Payslip = self.env['hr.payslip']
            created_payslips = []
            skipped = []
            errors = []

            # ONE payslip per employee (dashboard metrics + employee department).
            # Never create per-attendance-department — that caused duplicate employees.
            for employee in current_page_employees:
                try:
                    if not self._is_employee_active(employee['id']):
                        continue

                    employee_rec = self.env['hr.employee'].browse(employee['id'])

                    # Skip if a payslip already exists for this employee in the month
                    existing = Payslip.search([
                        ('employee_id', '=', employee['id']),
                        ('date_from', '<=', end_date),
                        ('date_to', '>=', start_date),
                        ('state', '!=', 'cancel'),
                    ], limit=1)
                    if existing:
                        skipped.append(employee['name'])
                        continue

                    metrics = self._get_dashboard_metrics_for_payslip(
                        employee['id'], year, month
                    )

                    payslip_vals = {
                        'employee_id': employee['id'],
                        'date_from': start_date,
                        'date_to': end_date,
                    }

                    # Fill contract / structure / name like the batch wizard
                    slip_data = Payslip.onchange_employee_id(
                        start_date, end_date, employee['id'], contract_id=False
                    )
                    slip_value = slip_data.get('value') or {}
                    if slip_value.get('name'):
                        payslip_vals['name'] = slip_value['name']
                    if slip_value.get('contract_id'):
                        payslip_vals['contract_id'] = slip_value['contract_id']
                    if slip_value.get('struct_id'):
                        payslip_vals['struct_id'] = slip_value['struct_id']
                    if slip_value.get('company_id'):
                        payslip_vals['company_id'] = slip_value['company_id']

                    if hasattr(Payslip, 'x_number_of_absence_days'):
                        payslip_vals['x_number_of_absence_days'] = metrics['absence_days']
                    if hasattr(Payslip, 'x_number_of_hours'):
                        payslip_vals['x_number_of_hours'] = metrics['late_hours']
                    if hasattr(Payslip, 'x_number_of_overtime_hours'):
                        payslip_vals['x_number_of_overtime_hours'] = metrics['overtime_hours']
                    if hasattr(Payslip, 'remaining_leave_days'):
                        payslip_vals['remaining_leave_days'] = metrics['remaining_leave_days']
                    if hasattr(Payslip, 'x_department') and employee_rec.department_id:
                        payslip_vals['x_department'] = employee_rec.department_id.id

                    payslip = Payslip.create(payslip_vals)

                     # Same chatter note as when Remaining Leave Days is edited manually
                    remaining = metrics.get('remaining_leave_days')
                    if remaining:
                        self._post_remaining_leave_days_to_payslip(
                            employee['id'], year, month, remaining
                        )

                    created_payslips.append({
                        'id': payslip.id,
                        'employee_name': employee['name'],
                        'department_name': employee_rec.department_id.name or 'No Department',
                        'absence_days': metrics['absence_days'],
                        'late_hours': metrics['late_hours'],
                    })

                except Exception as e:
                    error_msg = f"Error creating payslip for {employee['name']}: {str(e)}"
                    errors.append(error_msg)
                    _logger.error(error_msg)

            message = (
                f"Created {len(created_payslips)} payslips for "
                f"{len(current_page_employees)} employees on current page"
            )
            if skipped:
                message += f" (skipped {len(skipped)} already having a payslip this month)"

            return {
                'success': True,
                'created_count': len(created_payslips),
                'created_payslips': created_payslips,
                'skipped_employees': skipped,
                'errors': errors,
                'processed_employees': len(current_page_employees),
                'total_employees': len(all_employees),
                'current_page': pagination.get('page', 1),
                'message': message,
            }

        except Exception as e:
            _logger.error(f"Error in create_payslips_from_attendance: {str(e)}")
            return {'success': False, 'message': str(e)}

    @api.model
    def get_employee_monthly_summary(self, employee_id, year, month, employee_attendance=None):
        """
        Get or create monthly summary record for an employee
        All calculations use Riyadh timezone
        """
        try:
            if 'hr.employee.monthly.summary' not in self.env:
                return self._calculate_summary_on_fly(
                    employee_id, year, month, employee_attendance=employee_attendance
                )

            Summary = self.env['hr.employee.monthly.summary']

            summary = Summary.search([
                ('employee_id', '=', employee_id),
                ('year', '=', year),
                ('month', '=', month)
            ], limit=1)

            if not summary:
                calculated_values = self._calculate_summary_on_fly(
                    employee_id, year, month, employee_attendance=employee_attendance
                )
                if calculated_values['success']:
                    metrics = calculated_values['summary']
                else:
                    metrics = {
                        'total_absence_days': 0,
                        'total_late_hours': 0.0,
                        'total_overtime_hours': 0.0
                    }

                summary = Summary.create({
                    'employee_id': employee_id,
                    'year': year,
                    'month': month,
                    'total_absence_days': metrics['total_absence_days'],
                    'total_late_hours': metrics['total_late_hours'],
                    'total_overtime_hours': metrics['total_overtime_hours']
                })

            return {
                'success': True,
                'summary': {
                    'id': summary.id,
                    'total_absence_days': summary.total_absence_days,
                    'total_late_hours': summary.total_late_hours,
                    'total_overtime_hours': summary.total_overtime_hours,
                    'remaining_leave_days': summary.remaining_leave_days,
                }
            }

        except Exception as e:
            _logger.error(f"Error getting employee monthly summary: {str(e)}")
            return self._calculate_summary_on_fly(
                employee_id, year, month, employee_attendance=employee_attendance
            )

    def _calculate_summary_on_fly(self, employee_id, year, month, employee_attendance=None):
        """
        Calculate summary values on the fly from attendance data
        All calculations use Riyadh timezone
        """
        try:
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                return {'success': False, 'message': 'Employee not found'}

            days_in_month = calendar.monthrange(year, month)[1]
            days_list = list(range(1, days_in_month + 1))

            if employee_attendance is None:
                attendance_data = self._get_month_attendance_data(
                    year, month, days_list, [{'id': employee_id}]
                )
                employee_attendance = attendance_data.get(employee_id, {})

            riyadh_tz = self._get_riyadh_timezone()

            total_absence_days = 0
            total_late_hours = 0.0
            total_overtime_hours = 0.0

            employee_weekend_days = self._get_employee_weekend_days(employee_id)

            for day in days_list:
                day_data = employee_attendance.get(day, {})
                day_date = riyadh_tz.localize(datetime(year, month, day))

                if day_date.weekday() in employee_weekend_days:
                    continue

                if day_data.get('status') == 'absent':
                    total_absence_days += 1

                elif day_data.get('status') == 'present':
                    worked_hours = day_data.get('hours', 0)

                    if worked_hours > 0:
                        expected_hours = self._get_expected_hours_for_day(employee_id, day_date)

                        _logger.info(f"Day {day}: Worked={worked_hours}h, Expected={expected_hours}h")

                        if worked_hours > expected_hours:
                            overtime_hours = worked_hours - expected_hours
                            total_overtime_hours += overtime_hours
                            _logger.info(f"  → Overtime: {overtime_hours}h")

                        if worked_hours < expected_hours and expected_hours > 0:
                            late_hours = min(expected_hours - worked_hours, 2.0)
                            total_late_hours += late_hours
                            _logger.info(f"  → Late: {late_hours}h")

            return {
                'success': True,
                'summary': {
                    'total_absence_days': total_absence_days,
                    'total_late_hours': round(total_late_hours, 2),
                    'total_overtime_hours': round(total_overtime_hours, 2)
                }
            }

        except Exception as e:
            _logger.error(f"Error calculating summary on fly: {str(e)}")
            return {
                'success': False,
                'message': str(e),
                'summary': {
                    'total_absence_days': 0,
                    'total_late_hours': 0.0,
                    'total_overtime_hours': 0.0
                }
            }
    def _get_arabic_month_name(self, month):
        """Return Arabic month name for chatter messages."""
        arabic_months = {
            1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
            5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
            9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر',
        }
        return arabic_months.get(month, '')

    def _post_remaining_leave_days_to_payslip(self, employee_id, year, month, days):
        """Write remaining leave days on payslip and post Arabic chatter note."""
        if 'hr.payslip' not in self.env:
            return

        try:
            start_date = date(year, month, 1)
            end_date = date(year, month, calendar.monthrange(year, month)[1])
            payslips = self.env['hr.payslip'].search([
                ('employee_id', '=', employee_id),
                ('date_from', '<=', end_date),
                ('date_to', '>=', start_date),
            ])

            if not payslips:
                _logger.warning(
                    "No payslip found for employee %s for %s/%s",
                    employee_id, month, year,
                )
                return

            month_name = self._get_arabic_month_name(month)
            message = f"اجازه {days} ايام من شهر {month_name}"

            for payslip in payslips:
                if hasattr(payslip, 'remaining_leave_days'):
                    payslip.write({'remaining_leave_days': days})
                payslip.message_post(
                    body=message,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
        except Exception as e:
            _logger.error(
                "Error posting remaining leave days to payslip: %s", str(e)
            )

    @api.model
    def update_employee_monthly_summary(self, employee_id, year, month, field_name, value, mark_absence_manual=False, mark_late_manual=False):
        """
        Update a specific field in employee monthly summary
        """
        try:
            # Validate field name
            if field_name not in [
                'total_absence_days', 'total_late_hours', 'total_overtime_hours',
                'remaining_leave_days',
            ]:
                return {'success': False, 'message': 'Invalid field name'}

            # Validate value
            if field_name == 'total_absence_days':
                value = max(0, int(value))
            elif field_name == 'remaining_leave_days':
                value = max(0.0, float(value))
            else:
                value = max(0.0, float(value))

            # Check if we have the model
            if 'hr.employee.monthly.summary' not in self.env:
                return {'success': False, 'message': 'Monthly summary model not available'}

            Summary = self.env['hr.employee.monthly.summary']

            # Get or create summary
            summary = Summary.search([
                ('employee_id', '=', employee_id),
                ('year', '=', year),
                ('month', '=', month)
            ], limit=1)

            if not summary:
                # Create new summary
                summary = Summary.create({
                    'employee_id': employee_id,
                    'year': year,
                    'month': month,
                    'total_absence_days': 0,
                    'total_late_hours': 0.0,
                    'total_overtime_hours': 0.0,
                    'remaining_leave_days': 0,
                })

            write_vals = {field_name: value}
            if field_name == 'total_absence_days' and mark_absence_manual:
                write_vals['absence_days_manually_set'] = True
            if field_name == 'total_late_hours' and mark_late_manual:
                write_vals['late_hours_manually_set'] = True

            # Update the field
            summary.write(write_vals)

            if field_name == 'remaining_leave_days':
                self._post_remaining_leave_days_to_payslip(
                    employee_id, year, month, value
                )

            return {
                'success': True,
                'message': f'Updated {field_name} for employee',
                'summary': {
                    'id': summary.id,
                    'total_absence_days': summary.total_absence_days,
                    'total_late_hours': summary.total_late_hours,
                    'total_overtime_hours': summary.total_overtime_hours,
                    'remaining_leave_days': summary.remaining_leave_days,
                    'absence_days_manually_set': summary.absence_days_manually_set,
                    'late_hours_manually_set': summary.late_hours_manually_set,
                }
            }

        except Exception as e:
            _logger.error(f"Error updating employee monthly summary: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _is_employee_active(self, employee_id):
        """Return whether the employee is active and should appear in attendance flows."""
        employee = self.env['hr.employee'].browse(employee_id)
        if not employee.exists():
            return False
        return employee.active and (not employee.resource_id or employee.resource_id.active)

    @api.model
    def archive_employee_from_grid(self, employee_id):
        """Archive an employee from the attendance dashboard (same as archiving in Employees)."""
        try:
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                return {'success': False, 'message': _('Employee not found')}

            if not employee.active:
                return {'success': False, 'message': _('Employee is already archived')}

            employee.write({'active': False})

            return {
                'success': True,
                'message': _('Employee %(name)s has been archived.', name=employee.name),
                'employee_id': employee.id,
            }
        except Exception as e:
            _logger.error(f"Error archiving employee {employee_id}: {str(e)}")
            return {'success': False, 'message': str(e)}

    @api.model
    def calculate_attendance_metrics(self, employee_id, year, month):
        """
        Calculate and update attendance metrics based on actual attendance data
        All calculations use Riyadh timezone
        """
        try:
            if not self._is_employee_active(employee_id):
                return {'success': False, 'message': _('Employee is archived or inactive')}

            # Get calculated values
            result = self._calculate_summary_on_fly(employee_id, year, month)

            if result['success']:
                metrics = result['summary']

                preserve_manual_absence = False
                preserve_manual_late = False
                if 'hr.employee.monthly.summary' in self.env:
                    summary = self.env['hr.employee.monthly.summary'].search([
                        ('employee_id', '=', employee_id),
                        ('year', '=', year),
                        ('month', '=', month),
                    ], limit=1)
                    if summary and summary.absence_days_manually_set:
                        preserve_manual_absence = True
                        metrics['total_absence_days'] = summary.total_absence_days
                    if summary and summary.late_hours_manually_set:
                        preserve_manual_late = True
                        metrics['total_late_hours'] = summary.total_late_hours

                # Update the stored values
                for field_name, value in metrics.items():
                    if field_name == 'total_absence_days' and preserve_manual_absence:
                        continue
                    if field_name == 'total_late_hours' and preserve_manual_late:
                        continue
                    self.update_employee_monthly_summary(employee_id, year, month, field_name, value)

                if preserve_manual_absence:
                    metrics['total_absence_days'] = summary.total_absence_days
                if preserve_manual_late:
                    metrics['total_late_hours'] = summary.total_late_hours

                return {
                    'success': True,
                    'metrics': metrics
                }
            else:
                return result

        except Exception as e:
            _logger.error(f"Error calculating attendance metrics: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _get_expected_hours_for_day(self, employee_id, date_riyadh):
        """
        Get expected working hours for a specific employee on a specific day
        Uses employee's resource calendar
        """
        perf_cache = self._get_perf_cache()
        date_key = date_riyadh.strftime('%Y-%m-%d')
        cache_key = (employee_id, date_key)
        if perf_cache and cache_key in perf_cache['expected_hours']:
            return perf_cache['expected_hours'][cache_key]

        try:
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                result = 8.0
            else:
                calendar = employee.resource_calendar_id
                if not calendar:
                    calendar = self.env.company.resource_calendar_id

                if not calendar:
                    result = 8.0
                else:
                    weekday = date_riyadh.weekday()
                    calendar_attendances = calendar.attendance_ids.filtered(
                        lambda a: int(a.dayofweek) == weekday
                    )

                    if not calendar_attendances:
                        result = 0.0
                    else:
                        total_hours = 0.0
                        for attendance in calendar_attendances:
                            hours = attendance.hour_to - attendance.hour_from
                            total_hours += hours
                        _logger.info(
                            f"Employee {employee.name} - Expected hours on {date_riyadh.date()}: {total_hours}"
                        )
                        result = total_hours

        except Exception as e:
            _logger.error(f"Error getting expected hours: {str(e)}")
            result = 8.0

        if perf_cache is not None:
            perf_cache['expected_hours'][cache_key] = result

        return result
    def _calculate_late_hours(self, employee_id, date_riyadh, calendar):
        """
        Calculate late hours for a specific day
        All calculations use Riyadh timezone
        """
        try:
            # Convert Riyadh date range to UTC for database query
            start_of_day_utc = self._convert_to_utc_timezone(date_riyadh.replace(hour=0, minute=0, second=0))
            end_of_day_utc = self._convert_to_utc_timezone(date_riyadh.replace(hour=23, minute=59, second=59))

            # Get attendance records for the day
            Attendance = self.env['hr.attendance']
            attendance_records = Attendance.search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', start_of_day_utc),
                ('check_in', '<=', end_of_day_utc)
            ], limit=1)

            if not attendance_records:
                return 0.0

            record = attendance_records[0]
            check_in_time_riyadh = self._convert_to_riyadh_timezone(record.check_in)

            # Get expected start time from calendar (using Riyadh timezone weekday)
            weekday = date_riyadh.weekday()
            calendar_attendances = calendar.attendance_ids.filtered(
                lambda a: int(a.dayofweek) == weekday
            ).sorted('hour_from')

            if not calendar_attendances:
                return 0.0

            # Get first attendance period start time (in Riyadh timezone)
            expected_start_hour = calendar_attendances[0].hour_from
            expected_start_time = date_riyadh.replace(
                hour=int(expected_start_hour),
                minute=int((expected_start_hour % 1) * 60),
                second=0,
                microsecond=0
            )

            # Calculate late hours (both times in Riyadh timezone)
            if check_in_time_riyadh > expected_start_time:
                late_delta = check_in_time_riyadh - expected_start_time
                late_hours = late_delta.total_seconds() / 3600
                return late_hours

            return 0.0

        except Exception:
            return 0.0

    def _debug_timezone_info(self, date_obj, time_obj, operation="create"):
        """Debug timezone conversion issues"""
        try:
            riyadh_tz = pytz.timezone('Asia/Riyadh')
            naive_dt = datetime.combine(date_obj, time_obj)
            riyadh_dt = riyadh_tz.localize(naive_dt)
            utc_dt = riyadh_dt.astimezone(pytz.UTC)

            _logger.info(f"Timezone Debug - {operation}:")
            _logger.info(f"  Input date: {date_obj}, time: {time_obj}")
            _logger.info(f"  Naive datetime: {naive_dt}")
            _logger.info(f"  Riyadh datetime: {riyadh_dt}")
            _logger.info(f"  UTC datetime: {utc_dt}")
            _logger.info(f"  UTC naive: {utc_dt.replace(tzinfo=None)}")

        except Exception as e:
            _logger.error(f"Debug timezone error: {str(e)}")

    def create_attendance_record(self, employee_id, date, check_in, check_out=None, notes=None,
                                 in_latitude=None, in_longitude=None, out_latitude=None, out_longitude=None,
                                 attendance_department_id=None):
        """Create a new attendance record with location using default Odoo fields"""
        try:
            # Debug logging
            _logger.info(
                f"create_attendance_record called with: employee_id={employee_id}, date={date}, check_in={check_in}, check_out={check_out}, in_lat={in_latitude}, in_lng={in_longitude}")

            # Your existing validation code...
            # Convert and validate employee_id
            try:
                employee_id = int(employee_id)
            except (ValueError, TypeError):
                return {'success': False, 'message': f'Invalid employee ID: {employee_id}'}

            # Validate input
            if not employee_id or employee_id <= 0:
                return {'success': False, 'message': 'Invalid employee ID'}

            if not date or not check_in:
                return {'success': False, 'message': 'Missing required fields (date or check_in)'}

            # Handle empty strings
            if check_out == "":
                check_out = None
            if notes == "":
                notes = None

            # Check if employee exists
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                return {'success': False, 'message': f'Employee with ID {employee_id} not found'}

            # Your existing date/time parsing code...
            from datetime import datetime
            import pytz

            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                return {'success': False, 'message': f'Invalid date format: {date}. Expected YYYY-MM-DD'}

            try:
                check_in_time = datetime.strptime(check_in, '%H:%M').time()
            except ValueError:
                return {'success': False, 'message': f'Invalid check-in time format: {check_in}. Expected HH:MM'}

            # Convert to UTC naive datetime
            riyadh_tz = pytz.timezone('Asia/Riyadh')
            check_in_datetime = datetime.combine(date_obj, check_in_time)
            check_in_utc = riyadh_tz.localize(check_in_datetime).astimezone(pytz.UTC)
            check_in_naive = check_in_utc.replace(tzinfo=None)

            # Prepare attendance data with location
            attendance_data = {
                'employee_id': employee_id,
                'check_in': check_in_naive,
            }
            if attendance_department_id:
                try:
                    dept_id = int(attendance_department_id)
                    # Validate department exists
                    department = self.env['hr.department'].browse(dept_id)
                    if department.exists():
                        attendance_data['attendance_employee_department'] = dept_id
                    else:
                        _logger.warning(f"Invalid department ID: {dept_id}")
                except (ValueError, TypeError):
                    _logger.warning(f"Could not parse department ID: {attendance_department_id}")
            # Add check-in location if provided
            if in_latitude is not None and in_longitude is not None:
                try:
                    lat = float(in_latitude)
                    lng = float(in_longitude)

                    # Validate ranges
                    if -90 <= lat <= 90 and -180 <= lng <= 180:
                        attendance_data['in_latitude'] = lat
                        attendance_data['in_longitude'] = lng
                        _logger.info(f"Added check-in location: {lat}, {lng}")
                    else:
                        _logger.warning(f"Invalid location coordinates: {lat}, {lng}")
                except (ValueError, TypeError):
                    _logger.warning("Could not parse location coordinates")

            # Handle check-out if provided
            check_out_naive = None
            if check_out:
                try:
                    check_out_time = datetime.strptime(check_out, '%H:%M').time()
                    check_out_datetime = datetime.combine(date_obj, check_out_time)
                    check_out_utc = riyadh_tz.localize(check_out_datetime).astimezone(pytz.UTC)
                    check_out_naive = check_out_utc.replace(tzinfo=None)

                    # Validate that check_out is after check_in
                    if check_out_naive <= check_in_naive:
                        return {'success': False, 'message': 'Check-out time must be after check-in time'}

                    attendance_data['check_out'] = check_out_naive

                    # Add check-out location if provided
                    if out_latitude is not None and out_longitude is not None:
                        try:
                            out_lat = float(out_latitude)
                            out_lng = float(out_longitude)

                            # Validate ranges
                            if -90 <= out_lat <= 90 and -180 <= out_lng <= 180:
                                attendance_data['out_latitude'] = out_lat
                                attendance_data['out_longitude'] = out_lng
                                _logger.info(f"Added check-out location: {out_lat}, {out_lng}")
                            else:
                                _logger.warning(f"Invalid check-out coordinates: {out_lat}, {out_lng}")
                        except (ValueError, TypeError):
                            _logger.warning("Could not parse check-out location coordinates")

                except ValueError:
                    return {'success': False, 'message': f'Invalid check-out time format: {check_out}. Expected HH:MM'}

            # Log what we're about to create
            _logger.info(
                f"Creating attendance record with check_in: {check_in_naive} (UTC) for employee {employee_id} on date {date}")

            # Create the attendance record
            attendance = self.env['hr.attendance'].create(attendance_data)

            _logger.info(f"Successfully created attendance record ID: {attendance.id}")

            # Calculate worked hours
            total_hours = 0
            if check_out_naive:
                time_diff = check_out_naive - check_in_naive
                total_hours = time_diff.total_seconds() / 3600

            return {
                'success': True,
                'message': 'Attendance record created successfully with location',
                'record_id': attendance.id,
                'total_hours': round(total_hours, 2),
                'location_captured': {
                    'check_in': bool(in_latitude and in_longitude),
                    'check_out': bool(out_latitude and out_longitude)
                }
            }

        except Exception as e:
            _logger.error(f"Error creating attendance record: {str(e)}")
            return {
                'success': False,
                'message': f'Error creating record: {str(e)}'
            }

    def _get_attendance_edit_requests_batch(self, start_date_utc, end_date_utc, employee_ids):
        """
        Get attendance edit requests for multiple employees in a single query
        """
        if not employee_ids:
            return []

        if 'hr.attendance.edit.request' not in self.env:
            return []  # Model doesn't exist

        EditRequest = self.env['hr.attendance.edit.request']

        # Get all edit requests for the date range and employees
        requests = EditRequest.search([
            ('employee_id', 'in', employee_ids),
            ('date', '>=', start_date_utc),
            ('date', '<=', end_date_utc),
            ('state', '=', 'pending')  # Only pending requests
        ])

        request_list = []
        for request in requests:
            # Convert date to Riyadh timezone for matching
            request_date_riyadh = self._convert_to_riyadh_timezone(request.date)

            request_list.append({
                'id': request.id,
                'employee_id': request.employee_id.id,
                'attendance_id': request.attendance_id.id,
                'date': request_date_riyadh.strftime('%Y-%m-%d') if request_date_riyadh else None,
                'state': request.state
            })

        return request_list

    def _get_employee_edit_request_for_date(self, employee_id, date_str, edit_requests):
        """
        Check if employee has pending edit request for specific date
        """
        for request in edit_requests:
            if request['employee_id'] == employee_id and request['date'] == date_str:
                return request
        return None

    @api.model
    def get_edit_request_details(self, request_id):
        """
        Get details of a specific edit request
        """
        try:
            if 'hr.attendance.edit.request' not in self.env:
                return {'success': False, 'message': 'Edit request model not found'}

            EditRequest = self.env['hr.attendance.edit.request']
            request = EditRequest.browse(request_id)

            if not request.exists():
                return {'success': False, 'message': 'Edit request not found'}

            return {
                'success': True,
                'request': {
                    'id': request.id,
                    'employee_name': request.employee_id.name,
                    'attendance_id': request.attendance_id.id,
                    'state': request.state,
                    'check_in_new': request.check_in_new.isoformat() if request.check_in_new else None,
                    'check_out_new': request.check_out_new.isoformat() if request.check_out_new else None,
                }
            }

        except Exception as e:
            _logger.error(f"Error getting edit request details: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _prefetch_weekend_days_for_employees(self, employee_ids):
        """Populate weekend-day cache in one employee browse (same results as individual calls)."""
        perf_cache = self._get_perf_cache()
        if not employee_ids or not perf_cache:
            return

        missing_ids = [eid for eid in employee_ids if eid not in perf_cache['weekend_days']]
        if not missing_ids:
            return

        company_calendar = self.env.company.resource_calendar_id
        for employee in self.env['hr.employee'].browse(missing_ids):
            try:
                calendar = employee.resource_calendar_id or company_calendar
                if not calendar:
                    result = [4]
                else:
                    working_days = {int(a.dayofweek) for a in calendar.attendance_ids}
                    weekend_days = list(set(range(7)) - working_days)
                    _logger.info(
                        f"Employee {employee.name} - Working days: {working_days}, Weekend: {weekend_days}"
                    )
                    result = weekend_days if weekend_days else [4, 5]
            except Exception as e:
                _logger.error(f"Error getting employee weekend days: {str(e)}")
                result = [4, 5]

            if perf_cache is not None:
                perf_cache['weekend_days'][employee.id] = result

    ##########################
    def _get_employee_weekend_days(self, employee_id):
        """
        Get weekend days for specific employee from their resource calendar
        Returns list of weekday numbers (0=Monday, 6=Sunday)
        """
        perf_cache = self._get_perf_cache()
        if perf_cache and employee_id in perf_cache['weekend_days']:
            return perf_cache['weekend_days'][employee_id]

        try:
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                result = [4]
            else:
                calendar = employee.resource_calendar_id

                if not calendar:
                    calendar = self.env.company.resource_calendar_id

                if not calendar:
                    result = [4]
                else:
                    working_days = set()
                    for attendance in calendar.attendance_ids:
                        working_days.add(int(attendance.dayofweek))

                    all_days = set(range(7))
                    weekend_days = list(all_days - working_days)

                    _logger.info(
                        f"Employee {employee.name} - Working days: {working_days}, Weekend: {weekend_days}"
                    )

                    result = weekend_days if weekend_days else [4, 5]

        except Exception as e:
            _logger.error(f"Error getting employee weekend days: {str(e)}")
            result = [4, 5]

        if perf_cache is not None:
            perf_cache['weekend_days'][employee_id] = result

        return result
