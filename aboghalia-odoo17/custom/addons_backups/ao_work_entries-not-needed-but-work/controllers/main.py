from odoo import http
from odoo.http import request

class WorkEntriesController(http.Controller):
    
    @http.route('/work_entries/calendar', type='http', auth='user', website=False)
    def work_entries_calendar_page(self, **kwargs):
        """Render the work entries calendar page"""
        return request.render('work_entries_calendar.calendar_page', {
            'title': 'Work Entries Calendar'
        })
    
    @http.route('/work_entries/data', type='json', auth='user')
    def get_work_entries_data(self, year=None, month=None):
        """JSON endpoint for getting work entries data"""
        controller = request.env['work.entries.controller']
        return controller.get_work_entries_data(year, month)
    
    @http.route('/work_entries/employee_summary', type='json', auth='user')
    def get_employee_summary(self, employee_id, year, month):
        """JSON endpoint for getting employee attendance summary"""
        controller = request.env['work.entries.controller']
        return controller.get_employee_attendance_summary(employee_id, year, month)
    
    @http.route('/work_entries/update_summary', type='json', auth='user')
    def update_employee_summary(self, employee_id, year, month, field_name, value):
        """JSON endpoint for updating employee monthly summary"""
        controller = request.env['hr.employee.attendance.grid']
        return controller.update_employee_monthly_summary(employee_id, year, month, field_name, value)

    @http.route('/work_entries/calculate_metrics', type='json', auth='user')
    def calculate_metrics(self, employee_id, year, month):
        """JSON endpoint for calculating attendance metrics"""
        controller = request.env['hr.employee.attendance.grid']
        return controller.calculate_attendance_metrics(employee_id, year, month)

    @http.route('/work_entries/bulk_calculate_metrics', type='json', auth='user')
    def bulk_calculate_metrics(self, employee_ids, year, month):
        """JSON endpoint for bulk calculating attendance metrics"""
        controller = request.env['hr.employee.attendance.grid']
        results = []
        
        for employee_id in employee_ids:
            result = controller.calculate_attendance_metrics(employee_id, year, month)
            results.append({
                'employee_id': employee_id,
                'result': result
            })
        
        return {
            'success': True,
            'results': results
        }
    
    @http.route('/work_entries/create_record', type='json', auth='user')
    def create_attendance_record(self, employee_id, date, check_in, check_out=None, notes=None):
        """JSON endpoint for creating attendance records"""
        controller = request.env['hr.employee.attendance.grid']
        return controller.create_attendance_record(employee_id, date, check_in, check_out, notes)