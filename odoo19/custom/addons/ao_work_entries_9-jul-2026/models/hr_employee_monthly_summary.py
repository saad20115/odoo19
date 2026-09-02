# Create a new file: models/hr_employee_monthly_summary.py

from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeMonthlySummary(models.Model):
    """
    Model to store monthly attendance summary for each employee
    """
    _name = 'hr.employee.monthly.summary'
    _description = 'Employee Monthly Attendance Summary'
    _rec_name = 'display_name'
    
    employee_id = fields.Many2one(
        'hr.employee', 
        string='Employee',
        required=True,
        ondelete='cascade'
    )
    
    year = fields.Integer(
        string='Year',
        required=True,
        default=lambda self: datetime.now().year
    )
    
    month = fields.Integer(
        string='Month',
        required=True,
        default=lambda self: datetime.now().month
    )
    
    total_absence_days = fields.Integer(
        string='Total Absence Days',
        default=0,
        help='Total number of absence days for the month'
    )

    absence_days_manually_set = fields.Boolean(
        string='Absence Days Manually Set',
        default=False,
        help='When set, absence days were manually adjusted and should not be overwritten by automatic calculations',
    )
    
    total_late_hours = fields.Float(
        string='Total Late Hours',
        default=0.0,
        digits=(16, 2),
        help='Total late hours for the month'
    )
    
    total_overtime_hours = fields.Float(
        string='Total Overtime Hours',
        default=0.0,
        digits=(16, 2),
        help='Total overtime hours for the month'
    )

    remaining_leave_days = fields.Integer(
        string='Remaining Leave Days',
        default=0,
        help='Manually entered remaining days of leave for the month'
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    created_date = fields.Datetime(
        string='Created Date',
        default=fields.Datetime.now,
        readonly=True
    )
    
    last_updated = fields.Datetime(
        string='Last Updated',
        default=fields.Datetime.now,
        readonly=True
    )
    
    # Constraints
    _sql_constraints = [
        ('unique_employee_month_year', 
         'UNIQUE(employee_id, year, month)',
         'Only one summary record per employee per month is allowed!'),
        ('check_month_range', 
         'CHECK(month >= 1 AND month <= 12)',
         'Month must be between 1 and 12!'),
        ('check_year_range', 
         'CHECK(year >= 2020 AND year <= 2050)',
         'Year must be between 2020 and 2050!'),
        ('check_absence_days_positive',
         'CHECK(total_absence_days >= 0)',
         'Total absence days must be positive or zero!'),
        ('check_late_hours_positive',
         'CHECK(total_late_hours >= 0)',
         'Total late hours must be positive or zero!'),
        ('check_overtime_hours_positive',
         'CHECK(total_overtime_hours >= 0)',
         'Total overtime hours must be positive or zero!'),
        ('check_remaining_leave_days_positive',
         'CHECK(remaining_leave_days >= 0)',
         'Remaining leave days must be positive or zero!')
    ]
    
    @api.depends('employee_id.name', 'year', 'month')
    def _compute_display_name(self):
        """Compute display name for the record"""
        for record in self:
            if record.employee_id:
                month_name = [
                    '', 'January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December'
                ]
                record.display_name = f"{record.employee_id.name} - {month_name[record.month]} {record.year}"
            else:
                record.display_name = f"Summary - {record.month}/{record.year}"
    
    @api.model
    def write(self, vals):
        """Override write to update last_updated timestamp"""
        vals['last_updated'] = fields.Datetime.now()
        return super().write(vals)
    
    @api.model
    def get_or_create_summary(self, employee_id, year, month):
        """
        Get existing summary or create new one for employee/month/year
        """
        try:
            summary = self.search([
                ('employee_id', '=', employee_id),
                ('year', '=', year),
                ('month', '=', month)
            ], limit=1)
            
            if not summary:
                summary = self.create({
                    'employee_id': employee_id,
                    'year': year,
                    'month': month,
                    'total_absence_days': 0,
                    'total_late_hours': 0.0,
                    'total_overtime_hours': 0.0,
                    'remaining_leave_days': 0,
                })
            
            return summary
            
        except Exception as e:
            _logger.error(f"Error getting or creating summary: {str(e)}")
            return None
    
    @api.model
    def update_summary_field(self, employee_id, year, month, field_name, value):
        """
        Update a specific field in the summary
        """
        try:
            summary = self.get_or_create_summary(employee_id, year, month)
            if summary:
                summary.write({field_name: value})
                return True
            return False
        except Exception as e:
            _logger.error(f"Error updating summary field: {str(e)}")
            return False
    
    @api.model
    def get_summary_data(self, employee_id, year, month):
        """
        Get summary data for employee/month/year
        """
        try:
            summary = self.search([
                ('employee_id', '=', employee_id),
                ('year', '=', year),
                ('month', '=', month)
            ], limit=1)
            
            if summary:
                return {
                    'id': summary.id,
                    'total_absence_days': summary.total_absence_days,
                    'total_late_hours': summary.total_late_hours,
                    'total_overtime_hours': summary.total_overtime_hours,
                    'remaining_leave_days': summary.remaining_leave_days,
                }
            else:
                return {
                    'id': None,
                    'total_absence_days': 0,
                    'total_late_hours': 0.0,
                    'total_overtime_hours': 0.0,
                    'remaining_leave_days': 0,
                }
                
        except Exception as e:
            _logger.error(f"Error getting summary data: {str(e)}")
            return {
                'id': None,
                'total_absence_days': 0,
                'total_late_hours': 0.0,
                'total_overtime_hours': 0.0,
                'remaining_leave_days': 0,
            }
    
    @api.model
    def bulk_update_summaries(self, updates):
        """
        Bulk update multiple summary records
        """
        try:
            results = {
                'success_count': 0,
                'error_count': 0,
                'errors': []
            }
            
            for update in updates:
                try:
                    employee_id = update.get('employee_id')
                    year = update.get('year')
                    month = update.get('month')
                    field_name = update.get('field_name')
                    value = update.get('value')
                    
                    if self.update_summary_field(employee_id, year, month, field_name, value):
                        results['success_count'] += 1
                    else:
                        results['error_count'] += 1
                        results['errors'].append({
                            'employee_id': employee_id,
                            'error': 'Failed to update summary field'
                        })
                        
                except Exception as e:
                    results['error_count'] += 1
                    results['errors'].append({
                        'employee_id': update.get('employee_id'),
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            _logger.error(f"Error in bulk update: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def unlink(self):
        """Override unlink to add logging"""
        for record in self:
            _logger.info(f"Deleting monthly summary for {record.employee_id.name} - {record.month}/{record.year}")
        return super().unlink()
    
    @api.model
    def cleanup_old_summaries(self, months_to_keep=24):
        """
        Clean up old summary records (older than specified months)
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=months_to_keep * 30)
            cutoff_year = cutoff_date.year
            cutoff_month = cutoff_date.month
            
            old_summaries = self.search([
                '|',
                ('year', '<', cutoff_year),
                '&',
                ('year', '=', cutoff_year),
                ('month', '<', cutoff_month)
            ])
            
            count = len(old_summaries)
            old_summaries.unlink()
            
            _logger.info(f"Cleaned up {count} old summary records")
            return count
            
        except Exception as e:
            _logger.error(f"Error cleaning up old summaries: {str(e)}")
            return 0