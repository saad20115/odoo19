# -*- coding: utf-8 -*-


from odoo import http
from odoo.http import request
import base64
import face_recognition
import io  # Import BytesIO

class FaceRecognitionController(http.Controller):
    @http.route('/hr_attendance/verify_employee_face', type='json', auth='public')
    def verify_employee_face(self, employee_id, image_data, checkout=False):
        employee = request.env['hr.employee'].sudo().browse(int(employee_id))

        # Decode captured image
        captured_image_data = base64.b64decode(image_data)
        captured_image_file = io.BytesIO(captured_image_data)
        captured_image = face_recognition.load_image_file(captured_image_file)

       
        attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
        ], order='check_in desc', limit=1)

        if attendance:
            # Update the attendance record with the captured image
            if checkout:
                attendance.sudo().write({'checkout_image': image_data})
            else:
                attendance.sudo().write({'checkin_image': image_data})
        return {'matched': True}

    @http.route('/get_checkin_image', type='json', auth='user')
    def _save_checkin_image(self, employee_id, image_data, checkout=False):
        attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee_id),
        ], order='check_in desc', limit=1)
        if attendance and not checkout:
            attendance.sudo().write({'checkin_image': image_data})


    @http.route('/hr_attendance/systray_check_in_out', type='json', auth='user')
    def systray_check_in_out(self, checkout=False):
        # Handle the logic for both check-in and check-out,
        # 'checkout' will determine if it's check-out
        employee = request.env.user.employee_id
        if checkout:
            # Mark the employee as checked-out
            employee.attendance_state = 'checked_out'
        else:
            # Mark the employee as checked-in
            employee.attendance_state = 'checked_in'

        return {'status': 'success'}

    @http.route('/attendance/face_recognition_setting', type='json', auth='user')
    def get_face_recognition_setting(self):
        """ Securely fetch face recognition setting """
        value = request.env["ir.config_parameter"].sudo().get_param("ps_attendance_face_recognition.is_face_recognition")
        return {"is_face_recognition": value == "True"}

