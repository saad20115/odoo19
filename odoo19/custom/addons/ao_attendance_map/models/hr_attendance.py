# models/hr_attendance.py
from odoo import models, fields

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'
    
    # Dummy fields for the map widgets
    dummy_checkin_map = fields.Char(string="Check In Map", compute="_compute_dummy_maps")
    dummy_checkout_map = fields.Char(string="Check Out Map", compute="_compute_dummy_maps")
    
    def _compute_dummy_maps(self):
        """Dummy compute method - these fields just trigger the widget"""
        for record in self:
            record.dummy_checkin_map = "checkin"
            record.dummy_checkout_map = "checkout"