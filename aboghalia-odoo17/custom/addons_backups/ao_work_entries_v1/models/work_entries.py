from odoo import models, fields, api
from datetime import datetime, timedelta
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
            
            # Apply status filter after getting attendance data
            if filters.get('status_filter'):
                all_employees = self._filter_employees_by_status(
                    all_employees, filters['status_filter'], year, month, days_list
                )
                _logger.info(f"Found {len(all_employees)} employees after status filtering")
            
            # Get paginated employees
            paginated_result = self._get_paginated_employees(all_employees, pagination)
            
            # Get attendance data for paginated employees only
            attendance_data = self._get_month_attendance_data(
                year, month, days_list, paginated_result['employees']
            )
            
            # Calculate statistics for all employees
            statistics = self._calculate_attendance_statistics(
                year, month, days_list, all_employees
            )
            
            # Get departments for filters
            departments = self._get_departments()

            # Get Monthly Summary
            monthly_summaries = {}
            for employee in paginated_result['employees']:
                summary_result = self.get_employee_monthly_summary(employee['id'], year, month)
                if summary_result['success']:
                    monthly_summaries[employee['id']] = summary_result['summary']
                else:
                    monthly_summaries[employee['id']] = {
                        'total_absence_days': 0,
                        'total_late_hours': 0.0,
                        'total_overtime_hours': 0.0
                    }
            return {
                'success': True,
                'employees': paginated_result['employees'],
                'attendance_data': attendance_data,
                'monthly_summaries': monthly_summaries,
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
        Filter employees based on attendance status
        """
        if not status_filter:
            return employees
            
        filtered_employees = []
        
        for employee in employees:
            # Get attendance data for this employee
            attendance_data = self._get_month_attendance_data(
                year, month, days_list, [employee]
            )
            
            employee_data = attendance_data.get(employee['id'], {})
            
            # Check if employee has any days with the specified status
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
        domain = [('active', '=', True)]
        
        # Debug log
        _logger.info(f"Processing filters in _get_employees: {filters}")
        
        # Apply department filter
        dept_id = filters.get('departmentId')
        if dept_id and str(dept_id).strip() and dept_id != '':
            try:
                dept_id_int = int(dept_id)
                domain.append(('department_id', '=', dept_id_int))
                _logger.info(f"Applied department filter: department_id = {dept_id_int}")
            except (ValueError, TypeError) as e:
                _logger.warning(f"Invalid department_id: {dept_id}, error: {e}")
        
        # Apply name filter
        emp_name = filters.get('employeeName')
        if emp_name and str(emp_name).strip():
            domain.append(('name', 'ilike', str(emp_name).strip()))
            _logger.info(f"Applied name filter: name ilike '{emp_name}'")
        
        _logger.info(f"Final domain: {domain}")
        
        Employee = self.env['hr.employee']
        employees = Employee.search(domain, order='name asc')
        
        _logger.info(f"Found {len(employees)} employees with domain {domain}")
        
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
        Get attendance data for specific employees for the specified month
        All datetime operations use Asia/Riyadh timezone
        """
        if not employees:
            return {}
            
        attendance_data = {}
        employee_ids = [emp['id'] for emp in employees]
        
        # Create date range for the month in Riyadh timezone
        start_date = self._get_riyadh_datetime(year, month, 1)
        end_date = self._get_riyadh_datetime(year, month, days_list[-1], 23, 59, 59)
        
        # Convert to UTC for database queries
        start_date_utc = self._convert_to_utc_timezone(start_date)
        end_date_utc = self._convert_to_utc_timezone(end_date)
        
        # Get all attendance records for the month (batch query)
        attendance_records = self._get_attendance_records_batch(start_date_utc, end_date_utc, employee_ids)
        
        # Get leave records for the month (batch query)
        leave_records = self._get_leave_records_batch(start_date_utc, end_date_utc, employee_ids)
        
        # Get public holidays for the month
        public_holidays = self._get_public_holidays(start_date, end_date)
        
        # Process data for each employee
        for employee in employees:
            employee_id = employee['id']
            attendance_data[employee_id] = self._process_employee_month_data(
                employee_id, year, month, days_list, 
                attendance_records, leave_records, public_holidays
            )
        
        return attendance_data

    def _process_employee_month_data(self, employee_id, year, month, days_list, 
                                   attendance_records, leave_records, public_holidays):
        """Process attendance data for a single employee for the month"""
        employee_data = {}
        riyadh_tz = self._get_riyadh_timezone()
        
        # Get edit requests for this employee
        start_date = riyadh_tz.localize(datetime(year, month, 1))
        end_date = riyadh_tz.localize(datetime(year, month, days_list[-1], 23, 59, 59))
        start_date_utc = self._convert_to_utc_timezone(start_date)
        end_date_utc = self._convert_to_utc_timezone(end_date)
        edit_requests = self._get_attendance_edit_requests_batch(start_date_utc, end_date_utc, [employee_id])

        for day in days_list:
            day_date = riyadh_tz.localize(datetime(year, month, day))
            date_str = day_date.strftime('%Y-%m-%d')
            
            # Initialize day data
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
            
            # Check for edit request
            edit_request = self._get_employee_edit_request_for_date(employee_id, date_str, edit_requests)
            if edit_request:
                day_data['has_edit_request'] = True
                day_data['edit_request_id'] = edit_request['id']


            # Check if it's a weekend (Friday = 4, Saturday = 5 for Saudi Arabia)
            if day_date.weekday() in [4]:  # Friday = 4, Saturday = 5
                day_data['status'] = 'weekend'
                employee_data[day] = day_data
                continue
            
            # Check for public holidays
            if date_str in public_holidays:
                day_data['status'] = 'holiday'
                day_data['note'] = public_holidays[date_str]
                employee_data[day] = day_data
                continue
            
            # Check for approved leaves
            leave_data = self._get_employee_leave_for_date(employee_id, date_str, leave_records)
            if leave_data:
                day_data['status'] = 'leave'
                day_data['note'] = leave_data['name']
                employee_data[day] = day_data
                continue
            
            # Check for attendance records
            attendance_record = self._get_employee_attendance_for_date(employee_id, date_str, attendance_records)
            if attendance_record:
                day_data['status'] = 'present'
                day_data['hours'] = attendance_record['worked_hours'] or 0.0
                day_data['check_in'] = attendance_record['check_in']
                day_data['check_out'] = attendance_record['check_out']
                day_data['record_id'] = attendance_record['id']
                day_data['auto_checkedout'] = attendance_record['auto_checkedout'] or False
                day_data['holiday_warning'] = attendance_record['holiday_warning'] or False
            
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
            
            # Get days in month
            days_in_month = calendar.monthrange(year, month)[1]
            days_list = list(range(1, days_in_month + 1))
            
            # Get attendance data for the month
            attendance_data = self._get_month_attendance_data(
                year, month, days_list, [{'id': employee_id}]
            )
            
            employee_attendance = attendance_data.get(employee_id, {})
            riyadh_tz = self._get_riyadh_timezone()
            
            # Get all attendance records for the employee in this month
            start_date = self._get_riyadh_datetime(year, month, 1)
            end_date = self._get_riyadh_datetime(year, month, days_list[-1], 23, 59, 59)
            start_date_utc = self._convert_to_utc_timezone(start_date)
            end_date_utc = self._convert_to_utc_timezone(end_date)
            
            attendance_records = self._get_attendance_records_batch(start_date_utc, end_date_utc, [employee_id])
            
            # Group by department
            dept_summary = {}
            last_dept_by_date = {}  # Track last department for each date
            
            # Build department summary structure
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
                    
                    # Track last department for each date
                    record_date = record['date']
                    last_dept_by_date[record_date] = dept_id
                    
                    # Count present days and calculate hours
                    if record['worked_hours']:
                        dept_summary[dept_id]['present_days'] += 1
                        
                        # Simple overtime calculation (over 8 hours)
                        if record['worked_hours'] > 8:
                            dept_summary[dept_id]['overtime_hours'] += record['worked_hours'] - 8
                        
                        # Simple late calculation (less than 7 hours worked)
                        if record['worked_hours'] < 7:
                            dept_summary[dept_id]['late_hours'] += min(1.0, 8.0 - record['worked_hours'])
            
            # Calculate absence days using last known department
            for day in days_list:
                day_data = employee_attendance.get(day, {})
                day_date = riyadh_tz.localize(datetime(year, month, day))
                
                # Skip weekends and holidays
                if day_data.get('status') in ['weekend', 'holiday'] or day_date.weekday() in [4]:
                    continue
                
                if day_data.get('status') == 'absent':
                    # Find the last department this employee worked in before this absence
                    date_str = day_date.strftime('%Y-%m-%d')
                    last_dept_id = None
                    
                    # Look for the most recent attendance record before this date
                    for check_date in sorted(last_dept_by_date.keys(), reverse=True):
                        if check_date < date_str:
                            last_dept_id = last_dept_by_date[check_date]
                            break
                    
                    # If we found a department, attribute the absence to it
                    if last_dept_id and last_dept_id in dept_summary:
                        dept_summary[last_dept_id]['absence_days'] += 1
                    elif dept_summary:
                        # If no previous department found, use the first department in summary
                        first_dept = next(iter(dept_summary.values()))
                        first_dept['absence_days'] += 1
            
            return {
                'success': True,
                'department_summary': dept_summary
            }
            
        except Exception as e:
            _logger.error(f"Error getting department summary: {str(e)}")
            return {'success': False, 'message': str(e)}
        
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
        Get public holidays for the date range in Riyadh timezone
        """
        holidays = {}
        
        try:
            PublicHoliday = self.env['hr.holidays.public.line']
            records = PublicHoliday.search([
                ('date', '>=', start_date.strftime('%Y-%m-%d')),
                ('date', '<=', end_date.strftime('%Y-%m-%d'))
            ])
            
            for record in records:
                # Convert holiday date to Riyadh timezone if needed
                holiday_date = record.date
                if hasattr(holiday_date, 'strftime'):
                    holidays[holiday_date.strftime('%Y-%m-%d')] = record.name
                else:
                    holidays[str(holiday_date)] = record.name
                
        except Exception:
            # If public holidays module is not installed, return empty dict
            pass
        
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

    def _calculate_attendance_statistics(self, year, month, days_list, employees):
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
        
        # Get attendance data for all employees for statistics
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
        
        # Count working days (excluding weekends - Friday and Saturday for Saudi Arabia)
        for day in days_list:
            day_date = riyadh_tz.localize(datetime(year, month, day))
            if day_date.weekday() not in [4]:  # Sunday to Thursday (0-3)
                stats['working_days'] += 1
        
        # Count attendance statuses
        for employee_id in all_attendance_data:
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
        
        # Calculate average attendance percentage
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
                day_date = riyadh_tz.localize(datetime(year, month, day))
                if status not in ['weekend', 'holiday'] and day_date.weekday() < 4:  # Sunday to Thursday
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
    

    @api.model
    def create_payslips_from_attendance(self, year, month, filters=None, pagination=None):
        """
        Create payslips for employees in current page view based on department attendance data
        """
        try:
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
            
            # Get date range for the month
            start_date = datetime(year, month, 1).date()
            end_date = datetime(year, month, days_in_month).date()
            
            # Check if hr.payslip model exists
            if 'hr.payslip' not in self.env:
                return {'success': False, 'message': 'Payslip model not found'}
            
            Payslip = self.env['hr.payslip']
            created_payslips = []
            errors = []
            
            # Process only current page employees
            for employee in current_page_employees:
                try:
                    # Get department summary for this employee
                    dept_summary_result = self.get_employee_department_summary(
                        employee['id'], year, month
                    )
                    
                    if not dept_summary_result.get('success') or not dept_summary_result.get('department_summary'):
                        # UPDATED: Create payslip with empty/null department
                        try:
                            payslip_vals = {
                                'employee_id': employee['id'],
                                'date_from': start_date,
                                'date_to': end_date,
                            }
                            
                            # Add custom fields with zero values
                            if hasattr(Payslip, 'x_number_of_absence_days'):
                                payslip_vals['x_number_of_absence_days'] = 0
                            
                            if hasattr(Payslip, 'x_number_of_hours'):
                                payslip_vals['x_number_of_hours'] = 0.0
                            
                            # UPDATED: Leave x_department empty (null/False)
                            if hasattr(Payslip, 'x_department'):
                                payslip_vals['x_department'] = False  # This will be empty/null
                            
                            payslip = Payslip.create(payslip_vals)
                            
                            created_payslips.append({
                                'id': payslip.id,
                                'employee_name': employee['name'],
                                'department_name': 'No Department',  # Display name only
                                'absence_days': 0,
                                'late_hours': 0.0,
                            })
                            
                        except Exception as e:
                            error_msg = f"Error creating payslip for {employee['name']} (no department): {str(e)}"
                            errors.append(error_msg)
                            _logger.error(error_msg)
                        
                        continue
                    
                    dept_summary = dept_summary_result.get('department_summary', {})
                    
                    # Create payslip for each department
                    for dept_id, dept_data in dept_summary.items():
                        try:
                            payslip_vals = {
                                'employee_id': employee['id'],
                                'date_from': start_date,
                                'date_to': end_date,
                            }
                            
                            # Add custom fields if they exist
                            if hasattr(Payslip, 'x_number_of_absence_days'):
                                payslip_vals['x_number_of_absence_days'] = dept_data.get('absence_days', 0)
                            
                            if hasattr(Payslip, 'x_number_of_hours'):
                                payslip_vals['x_number_of_hours'] = dept_data.get('late_hours', 0.0)
                            
                            if hasattr(Payslip, 'x_department'):
                                payslip_vals['x_department'] = int(dept_id)
                            
                            # Create the payslip
                            payslip = Payslip.create(payslip_vals)
                            
                            created_payslips.append({
                                'id': payslip.id,
                                'employee_name': employee['name'],
                                'department_name': dept_data.get('department_name', 'Unknown'),
                                'absence_days': dept_data.get('absence_days', 0),
                                'late_hours': dept_data.get('late_hours', 0.0),
                            })
                            
                        except Exception as e:
                            error_msg = f"Error creating payslip for {employee['name']} - {dept_data.get('department_name', 'Unknown')}: {str(e)}"
                            errors.append(error_msg)
                            _logger.error(error_msg)
                            
                except Exception as e:
                    error_msg = f"Error processing employee {employee['name']}: {str(e)}"
                    errors.append(error_msg)
                    _logger.error(error_msg)
            
            return {
                'success': True,
                'created_count': len(created_payslips),
                'created_payslips': created_payslips,
                'errors': errors,
                'processed_employees': len(current_page_employees),
                'total_employees': len(all_employees),
                'current_page': pagination.get('page', 1),
                'message': f"Created {len(created_payslips)} payslips for {len(current_page_employees)} employees on current page"
            }
            
        except Exception as e:
            _logger.error(f"Error in create_payslips_from_attendance: {str(e)}")
            return {'success': False, 'message': str(e)}


    @api.model
    def get_employee_monthly_summary(self, employee_id, year, month):
        """
        Get or create monthly summary record for an employee
        All calculations use Riyadh timezone
        """
        try:
            # First check if we have the new model available
            if 'hr.employee.monthly.summary' not in self.env:
                # If model doesn't exist, calculate on the fly
                return self._calculate_summary_on_fly(employee_id, year, month)
            
            Summary = self.env['hr.employee.monthly.summary']
            
            # Try to find existing summary
            summary = Summary.search([
                ('employee_id', '=', employee_id),
                ('year', '=', year),
                ('month', '=', month)
            ], limit=1)
            
            if not summary:
                # Calculate actual values first
                calculated_values = self._calculate_summary_on_fly(employee_id, year, month)
                if calculated_values['success']:
                    metrics = calculated_values['summary']
                else:
                    metrics = {
                        'total_absence_days': 0,
                        'total_late_hours': 0.0,
                        'total_overtime_hours': 0.0
                    }
                
                # Create new summary record with calculated values
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
                    'total_overtime_hours': summary.total_overtime_hours
                }
            }
            
        except Exception as e:
            _logger.error(f"Error getting employee monthly summary: {str(e)}")
            # Fallback to calculation
            return self._calculate_summary_on_fly(employee_id, year, month)

    def _calculate_summary_on_fly(self, employee_id, year, month):
        """
        Calculate summary values on the fly from attendance data
        All calculations use Riyadh timezone
        """
        try:
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                return {'success': False, 'message': 'Employee not found'}
            
            # Get days in month
            days_in_month = calendar.monthrange(year, month)[1]
            days_list = list(range(1, days_in_month + 1))
            
            # Get attendance data for the month
            attendance_data = self._get_month_attendance_data(
                year, month, days_list, [{'id': employee_id}]
            )
            
            employee_attendance = attendance_data.get(employee_id, {})
            riyadh_tz = self._get_riyadh_timezone()
            
            # Calculate metrics
            total_absence_days = 0
            total_late_hours = 0.0
            total_overtime_hours = 0.0
            
            for day in days_list:
                day_data = employee_attendance.get(day, {})
                day_date = riyadh_tz.localize(datetime(year, month, day))
                
                # Skip weekends and holidays (Friday and Saturday for Saudi Arabia)
                if day_data.get('status') in ['weekend', 'holiday'] or day_date.weekday() in [4]:
                    continue
                
                # Count absence days (working days only)
                if day_data.get('status') == 'absent':
                    # Only count if it's a working day (Sunday to Thursday)
                    if day_date.weekday() not in [4]:
                        total_absence_days += 1
                
                # Calculate late and overtime hours for present days
                elif day_data.get('status') == 'present':
                    worked_hours = day_data.get('hours', 0)
                    
                    if worked_hours > 0:
                        # Get expected hours (default 8 hours)
                        expected_hours = 8.0
                        
                        # Calculate overtime hours
                        if worked_hours > expected_hours:
                            overtime_hours = worked_hours - expected_hours
                            total_overtime_hours += overtime_hours
                        
                        # Calculate late hours (simplified - assume 0.5 hours late if less than 7 hours worked)
                        if worked_hours < 7:
                            late_hours = min(1.0, 8.0 - worked_hours)  # Cap at 1 hour late
                            total_late_hours += late_hours
            
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

    @api.model
    def update_employee_monthly_summary(self, employee_id, year, month, field_name, value):
        """
        Update a specific field in employee monthly summary
        """
        try:
            # Validate field name
            if field_name not in ['total_absence_days', 'total_late_hours', 'total_overtime_hours']:
                return {'success': False, 'message': 'Invalid field name'}
            
            # Validate value
            if field_name == 'total_absence_days':
                value = max(0, int(value))
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
                    'total_overtime_hours': 0.0
                })
            
            # Update the field
            summary.write({field_name: value})
            
            return {
                'success': True,
                'message': f'Updated {field_name} for employee',
                'summary': {
                    'id': summary.id,
                    'total_absence_days': summary.total_absence_days,
                    'total_late_hours': summary.total_late_hours,
                    'total_overtime_hours': summary.total_overtime_hours
                }
            }
            
        except Exception as e:
            _logger.error(f"Error updating employee monthly summary: {str(e)}")
            return {'success': False, 'message': str(e)}

    @api.model
    def calculate_attendance_metrics(self, employee_id, year, month):
        """
        Calculate and update attendance metrics based on actual attendance data
        All calculations use Riyadh timezone
        """
        try:
            # Get calculated values
            result = self._calculate_summary_on_fly(employee_id, year, month)
            
            if result['success']:
                metrics = result['summary']
                
                # Update the stored values
                for field_name, value in metrics.items():
                    self.update_employee_monthly_summary(employee_id, year, month, field_name, value)
                
                return {
                    'success': True,
                    'metrics': metrics
                }
            else:
                return result
                
        except Exception as e:
            _logger.error(f"Error calculating attendance metrics: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _get_expected_hours_for_day(self, calendar, date_riyadh):
        """
        Get expected working hours for a specific day based on calendar
        Uses Riyadh timezone for day calculations
        """
        try:
            # Get calendar attendances for the day (using Riyadh timezone weekday)
            weekday = date_riyadh.weekday()
            calendar_attendances = calendar.attendance_ids.filtered(
                lambda a: int(a.dayofweek) == weekday
            )
            
            if not calendar_attendances:
                return 8.0  # Default 8 hours
            
            total_hours = 0
            for attendance in calendar_attendances:
                hours = attendance.hour_to - attendance.hour_from
                total_hours += hours
            
            return total_hours
            
        except Exception:
            return 8.0  # Default fallback

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
                           in_latitude=None, in_longitude=None, out_latitude=None, out_longitude=None, attendance_department_id=None):
        """Create a new attendance record with location using default Odoo fields"""
        try:
            # Debug logging
            _logger.info(f"create_attendance_record called with: employee_id={employee_id}, date={date}, check_in={check_in}, check_out={check_out}, in_lat={in_latitude}, in_lng={in_longitude}")
            
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
            
            # Create the attendance record
            attendance = self.env['hr.attendance'].create(attendance_data)
            
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