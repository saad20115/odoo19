from odoo import models, fields


class AttendanceSettings(models.Model):
    _inherit = 'res.config.settings'

    is_accept_uuid = fields.Boolean(
        string='Accept New UUIDs',
        default=False,
        config_parameter='ao_attendance_app_api.is_accept_uuid'
    )