from odoo import  fields, models, api


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'
   

    extra_hours = fields.Float(string='Extra Hours', compute="_compute_all_hours")
    lost_hours = fields.Float(string='Lost Hours', compute="_compute_all_hours")


    api.depends('check_in', 'check_out')
    def _compute_all_hours(self):
        for rec in self:
            extra_hours = 0
            lost_hours = 0
            for att_line in rec.employee_id.resource_calendar_id.attendance_ids:
                if att_line.day_period == 'morning' and rec.check_in.weekday() == int(att_line.dayofweek):
                    if rec.check_in.hour <= att_line.hour_from :
                        extra_hours += (att_line.hour_from - rec.check_in.hour)
                    elif rec.check_in.hour > att_line.hour_from:
                        lost_hours += (rec.check_in.hour - att_line.hour_from)
                elif att_line.day_period == 'afternoon' and rec.check_in.weekday() == int(att_line.dayofweek):
                    if rec.check_out.hour >= att_line.hour_to:
                        extra_hours += (rec.check_out.hour - att_line.hour_to)
                    elif rec.check_out.hour < att_line.hour_to:
                        lost_hours += (att_line.hour_to - rec.check_out.hour)
            rec.extra_hours = extra_hours
            rec.lost_hours = lost_hours