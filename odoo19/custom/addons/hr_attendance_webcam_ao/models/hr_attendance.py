# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class HrAttendance(models.Model):
    _inherit = "hr.attendance"
    
    image_checkin = fields.Binary("Check-in image", attachment=True)
    image_checkout = fields.Binary("Check-out image", attachment=True)
