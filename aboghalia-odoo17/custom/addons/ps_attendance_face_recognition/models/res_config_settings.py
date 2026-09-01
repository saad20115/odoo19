# -*- coding: utf-8 -*-


from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_face_recognition = fields.Boolean(string="Enable Custom Check-in",config_parameter="ps_attendance_face_recognition.is_face_recognition")
