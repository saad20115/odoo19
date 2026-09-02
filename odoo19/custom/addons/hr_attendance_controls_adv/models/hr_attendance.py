import werkzeug.urls
from odoo import fields, models, api
from odoo.addons import decimal_precision as dp

GEOLOCATION = dp.get_precision("Gelocation")

class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    check_in_latitude = fields.Float("Check-in Latitude", digits=GEOLOCATION, readonly=True)
    check_in_longitude = fields.Float("Check-in Longitude", digits=GEOLOCATION, readonly=True)
        
    check_out_latitude = fields.Float("Check-out Latitude", digits=GEOLOCATION, readonly=True)
    check_out_longitude = fields.Float("Check-out Longitude", digits=GEOLOCATION, readonly=True)
    
    check_in_location_link = fields.Char('Check In Location', compute='_compute_check_in_location_url')
    check_out_location_link = fields.Char('Check Out Location', compute='_compute_check_out_location_url')
    
    check_in_geofence_ids = fields.Many2many('hr.attendance.geofence', 'check_in_geofence_attendance_rel', 'attendance_id', 'geofence_id', string='Geofences')
    check_out_geofence_ids = fields.Many2many('hr.attendance.geofence', 'check_out_geofence_attendance_rel', 'attendance_id', 'geofence_id', string='Geofences')
    
    check_in_photo = fields.Binary(string="Check In Photo", readonly=False)
    check_out_photo = fields.Binary(string="Check Out Photo", readonly=False)
    
    check_in_ipaddress = fields.Char(string="Check In IP", readonly=True)
    check_out_ipaddress = fields.Char(string="Check Out IP", readonly=True)
    
    check_in_reason = fields.Char("Check In Reason")
    check_out_reason = fields.Char("Check Out Reason")
    
    @api.depends('check_in_latitude','check_in_longitude')
    def _compute_check_in_location_url(self):
        for attendance in self:
            params = {
                'q': '%s,%s' % (attendance.check_in_latitude or '',attendance.check_in_longitude or ''),'z': 10,
            }
            attendance.check_in_location_link ='%s?%s' % ('https://maps.google.com/maps',werkzeug.urls.url_encode(params or None))

    @api.depends('check_out_latitude','check_out_longitude')
    def _compute_check_out_location_url(self):
        for attendance in self:
            params = {
                'q': '%s,%s' % (attendance.check_out_latitude or '',attendance.check_out_longitude or ''),'z': 10,
            }
            attendance.check_out_location_link = '%s?%s' % ('https://maps.google.com/maps',werkzeug.urls.url_encode(params or None))
            
    def update_reason(self, employee_id, reason=None):
        self.ensure_one()
        if employee_id and reason:            
            employee = self.env['hr.employee'].sudo().search([('id','=',employee_id)])
            if employee.attendance_state == 'checked_in':
                self.sudo().update({'check_in_reason' : reason})
            if employee.attendance_state == 'checked_out':
                self.sudo().update({'check_out_reason' : reason})
