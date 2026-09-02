from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Add only the location name field, using existing in_latitude/in_longitude
    in_location_name = fields.Char(string='Check-in Location Name')
    out_location_name = fields.Char(string='Check-out Location Name')

    @api.model
    def get_user_attendance_data(self):
        """Get attendance data for the current logged user"""
        employee = self.env.user.employee_id
        if not employee:
            return {
                'error': True,
                'message': 'No employee record found for current user'
            }

        # Get current attendance (if checked in)
        current_attendance = self.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)

        # Get recent attendances (last 10)
        recent_attendances = self.search([
            ('employee_id', '=', employee.id)
        ], limit=10, order='check_in desc')

        # Calculate today's total hours
        today_start = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_attendances = self.search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', today_start)
        ])
        
        today_hours = sum(att.worked_hours for att in today_attendances if att.worked_hours)

        # Prepare employee image
        employee_image = False
        if employee.image_1920:
            employee_image = employee.image_1920.decode('utf-8')

        return {
            'error': False,
            'employee': {
                'id': employee.id,
                'name': employee.name,
                'image_1920': employee_image,
                'is_checked_in': bool(current_attendance),
                'current_check_in': current_attendance.check_in if current_attendance else False,
                'current_location': {
                    'latitude': current_attendance.in_latitude if current_attendance else None,
                    'longitude': current_attendance.in_longitude if current_attendance else None,
                    'location_name': current_attendance.in_location_name if current_attendance else None,
                } if current_attendance else None,
            },
            'today_hours': today_hours,
            'recent_attendances': [{
                'id': att.id,
                'check_in': att.check_in,
                'check_out': att.check_out,
                'worked_hours': att.worked_hours,
                'check_in_location': {
                    'latitude': att.in_latitude,
                    'longitude': att.in_longitude,
                    'location_name': att.in_location_name,
                } if att.in_latitude and att.in_longitude else None,
                'check_out_location': {
                    'latitude': att.out_latitude,
                    'longitude': att.out_longitude,
                    'location_name': att.out_location_name,
                } if att.out_latitude and att.out_longitude else None,
            } for att in recent_attendances]
        }

    @api.model
    def user_check_in(self, location_data=None):
        """Check in the current user with location"""
        employee = self.env.user.employee_id
        if not employee:
            raise UserError(_('No employee record found for your user account.'))

        # Check if already checked in
        if self.search([('employee_id', '=', employee.id), ('check_out', '=', False)]):
            raise UserError(_('You are already checked in!'))

        # Prepare attendance data
        attendance_data = {
            'employee_id': employee.id,
            'check_in': fields.Datetime.now(),
        }

        # Add location data if provided using standard Odoo fields
        if location_data:
            attendance_data.update({
                'in_latitude': location_data.get('latitude'),
                'in_longitude': location_data.get('longitude'),
                'in_location_name': location_data.get('location_name'),
            })

        # Create new attendance record
        attendance = self.create(attendance_data)

        return {
            'success': True,
            'check_in': attendance.check_in,
            'location': {
                'latitude': attendance.in_latitude,
                'longitude': attendance.in_longitude,
                'location_name': attendance.in_location_name,
            } if attendance.in_latitude and attendance.in_longitude else None,
            'message': _('Successfully checked in!')
        }

    @api.model
    def user_check_out(self, location_data=None):
        """Check out the current user with optional location"""
        employee = self.env.user.employee_id
        if not employee:
            raise UserError(_('No employee record found for your user account.'))

        # Find current attendance
        attendance = self.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)

        if not attendance:
            raise UserError(_('You are not checked in!'))

        # Update check out time
        update_data = {'check_out': fields.Datetime.now()}

        # Add check-out location data if provided
        if location_data:
            update_data.update({
                'out_latitude': location_data.get('latitude'),
                'out_longitude': location_data.get('longitude'),
                'out_location_name': location_data.get('location_name'),
            })

        attendance.write(update_data)

        return {
            'success': True,
            'check_out': attendance.check_out,
            'worked_hours': attendance.worked_hours,
            'location': {
                'latitude': attendance.out_latitude,
                'longitude': attendance.out_longitude,
                'location_name': attendance.out_location_name,
            } if attendance.out_latitude and attendance.out_longitude else None,
            'message': _('Successfully checked out!')
        }