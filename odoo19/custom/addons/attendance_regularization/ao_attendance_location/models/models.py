from math import radians, sin, cos, sqrt, atan2
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    location_range_id = fields.Many2one('hr.location.range', string='Check-in Location')

    @api.model_create_multi
    def create(self, values):
        attendance = super(HrAttendance, self).create(values)
        attendance._check_location_range()
        return attendance

    def write(self, values):
        res = super(HrAttendance, self).write(values)
        self._check_location_range()
        return res

    def _compute_distance(self, lat1, lon1, lat2, lon2):
        # Radius of the earth in kilometers
        R = 6371.0

        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Calculate the change in coordinates
        dlon = lon2 - lon1
        dlat = lat2 - lat1

        # Apply Haversine formula
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c

        return distance

    def _check_location_range(self):
        for attendance in self:
            if not (attendance.in_latitude and attendance.in_longitude):
                raise UserError(
                    _("Oops! It seems we're missing your location information. Could you please allow us to access your location so we can proceed?")
                )

            employee = attendance.employee_id
            user_location = (attendance.in_latitude, attendance.in_longitude)
            if (attendance.out_latitude and attendance.out_longitude):
                user_location = (attendance.out_latitude, attendance.out_longitude)
            # Check if employee has specific location ranges assigned and the feature is enabled
            if employee.use_specific_locations and employee.location_range_ids:
                within_range = False
                closest_range = None
                closest_distance = float('inf')

                # Check all assigned ranges
                for location_range in employee.location_range_ids:
                    range_location = (location_range.latitude, location_range.longitude)
                    distance = self._compute_distance(
                        user_location[0], user_location[1],
                        range_location[0], range_location[1]
                    )

                    # Update the closest range if this one is closer
                    if distance < closest_distance:
                        closest_distance = distance
                        closest_range = location_range

                    # Check if within allowed distance for this range
                    if distance <= location_range.allowed_distance:
                        within_range = True
                        # attendance.location_range_id = closest_range.id
                        # attendance.in_latitude = location_range.latitude
                        # attendance.out_latitude = location_range.longitude
                        break

                if not within_range:
                    # Get the closest range info for the error message
                    range_name = closest_range.name if closest_range else "any allowed location"
                    allowed_distance = closest_range.allowed_distance if closest_range else 0
                    actual_distance = closest_distance if closest_range else 0

                    raise UserError(_(
                        "You are outside all allowed location ranges. "
                        f"Closest location is '{range_name}' which is {actual_distance:.0f}km away, "
                        f"but the allowed distance is {allowed_distance}km."
                    ))
            elif not employee.free_attendance:
                # Fall back to company location check
                company = self.env.company
                company_location = (company.company_latitude or 0.0, company.company_longitude or 0.0)
                allowed_distance = company.allowed_distance or 1

                distance = self._compute_distance(
                    user_location[0], user_location[1],
                    company_location[0], company_location[1]
                )

                if distance > allowed_distance:
                    raise UserError(_(
                        "You are outside the allowed range of the company location. "
                        f"You are {distance:.0f}km away from the company location, "
                        f"but the allowed distance is {allowed_distance}km."
                    ))