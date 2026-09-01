from odoo import fields, models, api

class ResCompany(models.Model):
    _inherit = 'res.company'
    
    hr_attendance_geolocation = fields.Boolean(string="Geolocation", default=False)
    hr_attendance_geofence = fields.Boolean(string="Geofence", default=False)
    hr_attendance_face_recognition = fields.Boolean(string="Photo", default=False)
    hr_attendance_ip = fields.Boolean(string="IP Address", default=False)
    hr_attendance_reason = fields.Boolean(string="Reason", default=False)
    
    hr_attendance_geolocation_k = fields.Boolean(string="Geolocation", default=False)
    hr_attendance_geofence_k = fields.Boolean(string="Geofence", default=False)
    hr_attendance_face_recognition_k = fields.Boolean(string="Photo", default=False)
    hr_attendance_ip_k = fields.Boolean(string="IP Address", default=False)