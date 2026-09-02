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