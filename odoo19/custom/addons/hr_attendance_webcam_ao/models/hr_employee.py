# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from random import choice
from string import digits

from odoo import models, fields, api, exceptions, _, SUPERUSER_ID


# class HrEmployee(models.Model):
#     _inherit = "hr.employee"
    
#     image_last_attendance = fields.Binary("Last attendance image", attachment=True)

#     @api.multi
#     def write_last_attendance_img(self, vals):
#         if vals:
#             self.sudo().write(vals)

#     @api.multi
#     def attendance_manual(self, next_action, entered_pin=None, image_data=None):
#         self.ensure_one()
#         if not (entered_pin is None) or self.env['res.users'].browse(SUPERUSER_ID).has_group('hr_attendance.group_hr_attendance_use_pin') and (self.user_id and self.user_id.id != self._uid or not self.user_id):
#             if entered_pin != self.pin:
#                 return {'warning': _('Wrong PIN')}
#         return self.attendance_action(next_action, image_data)
    
#     @api.multi
#     def attendance_action(self, next_action, image_data=None):
#         """ Changes the attendance of the employee.
#             Returns an action to the check in/out message,
#             next_action defines which menu the check in/out message should return to. ("My Attendances" or "Kiosk Mode")
#         """
#         self.ensure_one()
#         action_message = self.env.ref('hr_attendance.hr_attendance_action_greeting_message').read()[0]
#         action_message['previous_attendance_change_date'] = self.last_attendance_id and (self.last_attendance_id.check_out or self.last_attendance_id.check_in) or False
#         action_message['employee_name'] = self.name
#         action_message['next_action'] = next_action

#         if self.user_id:
#             modified_attendance = self.sudo(self.user_id.id).attendance_action_change(image_data)
#         else:
#             modified_attendance = self.sudo().attendance_action_change(image_data)
        
#         #for employee in self:
#         #    if employee.image_last_attendance:
#         #        employee.image_last_attendance = None
#         action_message['attendance'] = modified_attendance.read()[0]
#         return {'action': action_message}
    
#     @api.multi
#     def attendance_action_change(self, image_data=None):
#         """ Check In/Check Out action
#             Check In: create a new attendance record
#             Check Out: modify check_out field of appropriate attendance record
#         """
#         if len(self) > 1:
#             raise exceptions.UserError(_('Cannot perform check in or check out on multiple employees.'))
#         action_date = fields.Datetime.now()
#         #image_last_attend = self.browse(self.id).image_last_attendance or None

#         if self.attendance_state != 'checked_in':
#             vals = {
#                 'employee_id': self.id,
#                 'check_in': action_date,
#                 'image_checkin': image_data,
#             }
#             return self.env['hr.attendance'].create(vals)
#         else:
#             attendance = self.env['hr.attendance'].search([('employee_id', '=', self.id), ('check_out', '=', False)], limit=1)
#             if attendance:
#                 attendance.check_out = action_date
#                 attendance.image_checkout = image_data
#             else:
#                 raise exceptions.UserError(_('Cannot perform check out on %(empl_name)s, could not find corresponding check in. '
#                     'Your attendances have probably been modified manually by human resources.') % {'empl_name': self.name, })
#             return attendance
