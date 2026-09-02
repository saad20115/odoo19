# -*- coding: utf-8 -*-


from odoo import api, fields, models, _, Command

class AccountAccount(models.Model):
    _inherit = "hr.attendance"

    is_face_recognition = fields.Boolean('Is Face Recognition Active', compute='_compute_is_face_recognition')
    checkin_image = fields.Image("Check-in Image", readonly=False, store=True)
    checkout_image = fields.Image("Check-out Image", readonly=False, store=True)


    def _compute_is_face_recognition(self):
        self.is_face_recognition = self.env["ir.config_parameter"].sudo().get_param("ps_attendance_face_recognition.is_face_recognition")
