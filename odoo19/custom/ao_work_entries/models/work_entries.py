from odoo import models, fields, api
from datetime import datetime, timedelta
import calendar

# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import calendar
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeAttendanceGrid(models.Model):
    """
    Model to handle attendance grid operations for Odoo 17
    """
    _name = 'hr.employee.attendance.grid'
    _description = 'Employee Attendance Grid'
    _auto = False  # This is a virtual model, no database table

    @api.model
    def get_attendance_data(self, year, month):
        """
        Get comprehensive attendance data for a specific month and year
        
        Args:
            year (int): Year to fetch data for
            month (int): Month to fetch data for (1-12)
            
        Returns:
            dict: Complete attendance data structure
        """
        try:
            # Validate input parameters
            if not isinstance(year, int) or not isinstance(month, int):
                raise ValidationError(_("Year and month must be integers"))
            
            if month < 1 or month > 12:
                raise ValidationError(_("Month must be between 1 and 12"))
            
            # Get days in month
            days_in_month = calendar.monthrange(year, month)[1]
            days_list = list(range(1, days_in_month + 1))
            
            # Get active employees
            employees = self._get_active_employees()
            
            # Get attendance data for the month
            attendance_data = self._get_month_attendance_data(year, month, days_list, employees)
            
            # Calculate statistics
            statistics = self._calculate_attendance_statistics(attendance_data, employees, days_list, year, month)
            
            return {
                'employees': employees,
                'attendance_data': attendance_data,
                'days_in_month': days_list,
                'statistics': statistics,
                'month_name': calendar.month_name[month],
                'year': year,
                'month': month
            }
            
        except Exception as e:
            _logger.error(f"Error in get_attendance_data: {str(e)}")
            raise ValidationError(_("Error fetching attendance data: %s") % str(e))

    def _get_active_employees(self):
        """
        Get all active employees with required fields
        
        Returns:
            list: List of employee dictionaries
        """
        Employee = self.env['hr.employee']
        employees = Employee.search([('active', '=', True)], order='name asc')
        
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
            }
            employee_list.append(employee_data)
        
        return employee_list

    def _get_month_attendance_data(self, year, month, days_list, employees):
        """
        Get attendance data for all employees for the specified month
        
        Args:
            year (int): Year
            month (int): Month
            days_list (list): List of days in the month
            employees (list): List of employee dictionaries
            
        Returns:
            dict: Nested dictionary with attendance data
        """
        attendance_data = {}
        
        # Create date range for the month
        start_date = datetime(year, month, 1)
        end_date = datetime(year, month, days_list[-1], 23, 59, 59)
        
        # Get all attendance records for the month
        attendance_records = self._get_attendance_records(start_date, end_date, employees)
        
        # Get leave records for the month
        leave_records = self._get_leave_records(start_date, end_date, employees)
        
        # Get public holidays for the month
        public_holidays = self._get_public_holidays(start_date, end_date)
        
        # Process data for each employee
        for employee in employees:
            employee_id = employee['id']
            attendance_data[employee_id] = {}
            
            for day in days_list:
                day_date = datetime(year, month, day)
                date_str = day_date.strftime('%Y-%m-%d')
                
                # Initialize day data
                day_data = {
                    'status': 'absent',
                    'hours': 0.0,
                    'check_in': None,
                    'check_out': None,
                    'record_id': None,
                    'note': ''
                }
                
                # Check if it's a weekend
                if day_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    day_data['status'] = 'weekend'
                    attendance_data[employee_id][day] = day_data
                    continue
                
                # Check for public holidays
                if date_str in public_holidays:
                    day_data['status'] = 'holiday'
                    day_data['note'] = public_holidays[date_str]
                    attendance_data[employee_id][day] = day_data
                    continue
                
                # Check for approved leaves
                leave_data = self._get_employee_leave_for_date(employee_id, date_str, leave_records)
                if leave_data:
                    day_data['status'] = 'leave'
                    day_data['note'] = leave_data['name']
                    attendance_data[employee_id][day] = day_data
                    continue
                
                # Check for attendance records
                attendance_record = self._get_employee_attendance_for_date(employee_id, date_str, attendance_records)
                if attendance_record:
                    day_data['status'] = 'present'
                    day_data['hours'] = attendance_record['worked_hours'] or 0.0
                    day_data['check_in'] = attendance_record['check_in']
                    day_data['check_out'] = attendance_record['check_out']
                    day_data['record_id'] = attendance_record['id']
                
                attendance_data[employee_id][day] = day_data
        
        return attendance_data

    def _get_attendance_records(self, start_date, end_date, employees):
        """
        Get attendance records for the date range and employees
        """
        employee_ids = [emp['id'] for emp in employees]
        
        Attendance = self.env['hr.attendance']
        records = Attendance.search([
            ('employee_id', 'in', employee_ids),
            ('check_in', '>=', start_date),
            ('check_in', '<=', end_date)
        ])
        
        attendance_list = []
        for record in records:
            attendance_list.append({
                'id': record.id,
                'employee_id': record.employee_id.id,
                'check_in': record.check_in.isoformat() if record.check_in else None,
                'check_out': record.check_out.isoformat() if record.check_out else None,
                'worked_hours': record.worked_hours,
                'date': record.check_in.strftime('%Y-%m-%d') if record.check_in else None
            })
        
        return attendance_list

    def _get_leave_records(self, start_date, end_date, employees):
        """
        Get leave records for the date range and employees
        """
        employee_ids = [emp['id'] for emp in employees]
        
        Leave = self.env['hr.leave']
        records = Leave.search([
            ('employee_id', 'in', employee_ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', end_date),
            ('date_to', '>=', start_date)
        ])
        
        leave_list = []
        for record in records:
            leave_list.append({
                'id': record.id,
                'employee_id': record.employee_id.id,
                'date_from': record.date_from.isoformat() if record.date_from else None,
                'date_to': record.date_to.isoformat() if record.date_to else None,
                'name': record.holiday_status_id.name if record.holiday_status_id else 'Leave',
                'number_of_days': record.number_of_days
            })
        
        return leave_list

    def _get_public_holidays(self, start_date, end_date):
        """
        Get public holidays for the date range
        """
        holidays = {}
        
        # Try to get public holidays (this depends on having hr_holidays_public module)
        try:
            PublicHoliday = self.env['hr.holidays.public.line']
            records = PublicHoliday.search([
                ('date', '>=', start_date.strftime('%Y-%m-%d')),
                ('date', '<=', end_date.strftime('%Y-%m-%d'))
            ])
            
            for record in records:
                holidays[record.date.strftime('%Y-%m-%d')] = record.name
                
        except Exception:
            # If public holidays module is not installed, return empty dict
            pass
        
        return holidays

    def _get_employee_leave_for_date(self, employee_id, date_str, leave_records):
        """
        Check if employee has leave on specific date
        """
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        for leave in leave_records:
            if leave['employee_id'] == employee_id:
                date_from = datetime.fromisoformat(leave['date_from']).date()
                date_to = datetime.fromisoformat(leave['date_to']).date()
                
                if date_from <= target_date <= date_to:
                    return leave
        
        return None

    def _get_employee_attendance_for_date(self, employee_id, date_str, attendance_records):
        """
        Get employee attendance record for specific date
        """
        for record in attendance_records:
            if record['employee_id'] == employee_id and record['date'] == date_str:
                return record
        
        return None

    def _calculate_attendance_statistics(self, attendance_data, employees, days_list, year, month):
        """
        Calculate attendance statistics
        """
        stats = {
            'total_employees': len(employees),
            'working_days': 0,
            'total_present': 0,
            'total_absent': 0,
            'total_leaves': 0,
            'total_holidays': 0,
            'avg_attendance': 0
        }
        
        # Count working days (excluding weekends)
        for day in days_list:
            day_date = datetime(year, month, day)
            if day_date.weekday() < 5:  # Monday to Friday
                stats['working_days'] += 1
        
        # Count attendance statuses
        for employee_id in attendance_data:
            for day in days_list:
                day_data = attendance_data[employee_id].get(day, {})
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
    def update_attendance_status(self, employee_id, date, status):
        """
        Update attendance status for a specific employee and date
        
        Args:
            employee_id (int): Employee ID
            date (str): Date in YYYY-MM-DD format
            status (str): New status ('present', 'absent', 'holiday', 'leave')
            
        Returns:
            dict: Success status and message
        """
        try:
            # Validate inputs
            if not employee_id or not date or not status:
                raise ValidationError(_("Employee ID, date, and status are required"))
            
            # Validate employee exists
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                raise ValidationError(_("Employee not found"))
            
            # Parse date
            try:
                target_date = datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                raise ValidationError(_("Invalid date format. Use YYYY-MM-DD"))
            
            # Validate status
            valid_statuses = ['present', 'absent', 'holiday', 'leave']
            if status not in valid_statuses:
                raise ValidationError(_("Invalid status. Must be one of: %s") % ', '.join(valid_statuses))
            
            # Handle different status updates
            if status == 'present':
                self._create_or_update_attendance(employee_id, target_date)
            elif status == 'absent':
                self._remove_attendance_if_exists(employee_id, target_date)
            elif status in ['holiday', 'leave']:
                # For holidays and leaves, we might want to create special records
                # This depends on your business logic
                self._handle_special_status(employee_id, target_date, status)
            
            return {
                'success': True,
                'message': _("Attendance status updated successfully"),
                'employee_name': employee.name,
                'date': date,
                'status': status
            }
            
        except Exception as e:
            _logger.error(f"Error updating attendance status: {str(e)}")
            return {
                'success': False,
                'message': str(e)
            }

    def _create_or_update_attendance(self, employee_id, target_date):
        """
        Create or update attendance record for present status
        """
        Attendance = self.env['hr.attendance']
        
        # Check if attendance record already exists for the date
        existing_record = Attendance.search([
            ('employee_id', '=', employee_id),
            ('check_in', '>=', target_date.replace(hour=0, minute=0, second=0)),
            ('check_in', '<=', target_date.replace(hour=23, minute=59, second=59))
        ], limit=1)
        
        if existing_record:
            # Update existing record if needed
            if not existing_record.check_out:
                existing_record.check_out = target_date.replace(hour=17, minute=0, second=0)
        else:
            # Create new attendance record
            Attendance.create({
                'employee_id': employee_id,
                'check_in': target_date.replace(hour=9, minute=0, second=0),
                'check_out': target_date.replace(hour=17, minute=0, second=0),
            })

    def _remove_attendance_if_exists(self, employee_id, target_date):
        """
        Remove attendance record for absent status
        """
        Attendance = self.env['hr.attendance']
        
        # Find and delete attendance record for the date
        existing_records = Attendance.search([
            ('employee_id', '=', employee_id),
            ('check_in', '>=', target_date.replace(hour=0, minute=0, second=0)),
            ('check_in', '<=', target_date.replace(hour=23, minute=59, second=59))
        ])
        
        if existing_records:
            existing_records.unlink()

    def _handle_special_status(self, employee_id, target_date, status):
        """
        Handle special statuses like holiday or leave
        """
        # Remove any existing attendance for this date
        self._remove_attendance_if_exists(employee_id, target_date)
        
        # For holidays and leaves, you might want to create records in other models
        # This is just a placeholder - implement according to your business logic
        if status == 'leave':
            # You might want to create a leave request here
            # or mark it in a special way
            pass

    @api.model
    def get_employee_details(self, employee_id, date):
        """
        Get detailed information for a specific employee and date
        
        Args:
            employee_id (int): Employee ID
            date (str): Date in YYYY-MM-DD format
            
        Returns:
            dict: Employee details and attendance information
        """
        try:
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                raise ValidationError(_("Employee not found"))
            
            target_date = datetime.strptime(date, '%Y-%m-%d')
            
            # Get attendance records for the date
            Attendance = self.env['hr.attendance']
            attendance_records = Attendance.search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', target_date.replace(hour=0, minute=0, second=0)),
                ('check_in', '<=', target_date.replace(hour=23, minute=59, second=59))
            ])
            
            attendance_details = []
            for record in attendance_records:
                attendance_details.append({
                    'id': record.id,
                    'check_in': record.check_in.isoformat() if record.check_in else None,
                    'check_out': record.check_out.isoformat() if record.check_out else None,
                    'worked_hours': record.worked_hours
                })
            
            return {
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
            _logger.error(f"Error getting employee details: {str(e)}")
            raise ValidationError(_("Error fetching employee details: %s") % str(e))

    @api.model
    def export_attendance_data(self, year, month, format='json'):
        """
        Export attendance data for a specific month
        
        Args:
            year (int): Year to export
            month (int): Month to export
            format (str): Export format ('json', 'csv', 'xlsx')
            
        Returns:
            dict: Export data or file information
        """
        try:
            attendance_data = self.get_attendance_data(year, month)
            
            if format == 'json':
                return {
                    'success': True,
                    'data': attendance_data,
                    'filename': f'attendance_{year}_{month:02d}.json'
                }
            elif format == 'csv':
                return self._export_to_csv(attendance_data, year, month)
            elif format == 'xlsx':
                return self._export_to_xlsx(attendance_data, year, month)
            else:
                raise ValidationError(_("Unsupported export format"))
                
        except Exception as e:
            _logger.error(f"Error exporting attendance data: {str(e)}")
            raise ValidationError(_("Error exporting data: %s") % str(e))

    def _export_to_csv(self, attendance_data, year, month):
        """
        Export attendance data to CSV format
        """
        import csv
        import io
        import base64
        
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

    def _export_to_xlsx(self, attendance_data, year, month):
        """
        Export attendance data to Excel format
        """
        try:
            import xlsxwriter
            import io
            import base64
            
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
            raise ValidationError(_("xlsxwriter library is required for Excel export"))

    @api.model
    def bulk_update_attendance(self, updates):
        """
        Bulk update multiple attendance records
        
        Args:
            updates (list): List of update dictionaries
                Each dict should contain: employee_id, date, status
                
        Returns:
            dict: Bulk update results
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
                        update.get('status')
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
            raise ValidationError(_("Error in bulk update: %s") % str(e))

    @api.model
    def get_attendance_summary(self, employee_id, year, month):
        """
        Get attendance summary for a specific employee and month
        
        Args:
            employee_id (int): Employee ID
            year (int): Year
            month (int): Month
            
        Returns:
            dict: Employee attendance summary
        """
        try:
            employee = self.env['hr.employee'].browse(employee_id)
            if not employee.exists():
                raise ValidationError(_("Employee not found"))
            
            # Get attendance data for the month
            attendance_data = self.get_attendance_data(year, month)
            employee_attendance = attendance_data['attendance_data'].get(employee_id, {})
            
            # Calculate summary
            summary = {
                'employee_name': employee.name,
                'department': employee.department_id.name if employee.department_id else '',
                'year': year,
                'month': month,
                'month_name': calendar.month_name[month],
                'total_days': len(attendance_data['days_in_month']),
                'working_days': 0,
                'present_days': 0,
                'absent_days': 0,
                'leave_days': 0,
                'holiday_days': 0,
                'weekend_days': 0,
                'total_hours': 0.0,
                'attendance_percentage': 0.0
            }
            
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
                
                # Count working days (exclude weekends and holidays)
                if status not in ['weekend', 'holiday']:
                    summary['working_days'] += 1
            
            # Calculate attendance percentage
            if summary['working_days'] > 0:
                summary['attendance_percentage'] = round(
                    (summary['present_days'] / summary['working_days']) * 100, 2
                )
            
            return summary
            
        except Exception as e:
            _logger.error(f"Error getting attendance summary: {str(e)}")
            raise ValidationError(_("Error fetching attendance summary: %s") % str(e))