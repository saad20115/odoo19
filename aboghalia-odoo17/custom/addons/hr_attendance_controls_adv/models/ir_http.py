from odoo import models
from odoo.http import request

class Http(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super(Http, self).session_info()
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        if self.env.user.has_group('base.group_user'):
            company = self.env.company
            
            result['hr_attendance_geolocation'] = company.hr_attendance_geolocation
            result['hr_attendance_geofence'] = company.hr_attendance_geofence
            result['hr_attendance_face_recognition'] = company.hr_attendance_face_recognition
            result['hr_attendance_ip'] = company.hr_attendance_ip
            result['hr_attendance_reason'] = company.hr_attendance_reason
            
            
            result['hr_attendance_geolocation_k'] = company.hr_attendance_geolocation_k
            result['hr_attendance_geofence_k'] = company.hr_attendance_geofence_k
            result['hr_attendance_face_recognition_k'] = company.hr_attendance_face_recognition_k
            result['hr_attendance_ip_k'] = company.hr_attendance_ip_k
                        
        return result