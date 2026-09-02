# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
_logger = logging.getLogger(__name__)
from odoo import fields, models, api


class LocationRange(models.Model):
    _name = 'hr.location.range'
    _description = 'Employee Location Range'

    name = fields.Char(string='Location Name', required=True)
    latitude = fields.Float(string='Latitude', digits=(16, 6), required=True)
    longitude = fields.Float(string='Longitude', digits=(16, 6), required=True)
    allowed_distance = fields.Float(
        string='Allowed Distance (km)',
        digits=(16, 0),
        default=1,
        help='Set the allowed distance for check-in or check-out in kilometers.'
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    employee_ids = fields.Many2many(
        'hr.employee',
        'employee_location_range_rel',
        'range_id',
        'employee_id',
        string='Assigned Employees'
    )


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    location_range_ids = fields.Many2many(
        'hr.location.range',
        'employee_location_range_rel',
        'employee_id',
        'range_id',
        string='Allowed Location Ranges'
    )
    use_specific_locations = fields.Boolean(
        string='Use Specific Locations',
        default=True,
        help='If enabled, employee can only check-in from assigned location ranges. Otherwise, company location will be used.'
    )
    free_attendance = fields.Boolean(string='Free Attendance', default=False)
    skip_biometric = fields.Boolean(string='Skip Biometric', default=False)


    @api.onchange("free_attendance")
    def _override_use_specific_locations(self):
        for rec in self:
            if rec.free_attendance:
                rec.use_specific_locations = False
            else:
                rec.use_specific_locations = True


class ResCompany(models.Model):
    _inherit = 'res.company'

    company_latitude = fields.Float(
        string='Company Latitude',
        digits=(16, 6),
        help='Set Company Latitude here'
    )
    company_longitude = fields.Float(
        string='Company Longitude',
        digits=(16, 6),
        help='Set Company Longitude here'
    )
    allowed_distance = fields.Float(
        string='Allowed Distance (km)',
        digits=(16, 0),
        default=1,
        help='Set the allowed distance for check-in or check-out in kilometers. Example: 1.1 kilometers.'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_latitude = fields.Float(string='Company Latitude', related='company_id.company_latitude', readonly=False)
    company_longitude = fields.Float(string='Company Longitude', related='company_id.company_longitude', readonly=False)
    allowed_distance = fields.Float(
        string='Allowed Distance (km)',
        related='company_id.allowed_distance',
        readonly=False
    )

    def execute(self):
        res = super(ResConfigSettings, self).execute()
        _logger.info(
            f"company Latitude: {self.company_latitude},"
            f"company Longitude: {self.company_longitude},"
            f"Allowed Distance: {self.allowed_distance}"
        )
        return res