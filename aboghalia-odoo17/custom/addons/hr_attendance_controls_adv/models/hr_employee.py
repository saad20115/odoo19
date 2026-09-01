from odoo import fields, models, api, _

class HrEmployee(models.Model):
    _inherit = "hr.employee"
    
    user_faces = fields.One2many("hr.employee.faces", "employee_id", "Faces")

    def attendance_manual(self, next_action, entered_pin=None, location=False, ip_address=False, geofence_ids=False, photo_img64= False):
        res = super(HrEmployee, self.with_context(attendance_geolocation=location, attendance_ipaddress=ip_address, attendance_geofence=geofence_ids, attendance_photo=photo_img64)).attendance_manual(next_action, entered_pin)        
        return res

    def _attendance_action_change(self):
        res = super()._attendance_action_change()
        geolocation = self.env.context.get('attendance_geolocation', False)
        geofence = self.env.context.get('attendance_geofence', False)
        ipaddress = self.env.context.get('attendance_ipaddress', False)
        photo = self.env.context.get('attendance_photo', False)
        if geolocation:            
            if self.attendance_state == 'checked_in':
                vals = {
                    'check_in_latitude': geolocation[0],
                    'check_in_longitude': geolocation[1],
                }
                res.write(vals)
            else:
                vals = {
                    'check_out_latitude': geolocation[0],
                    'check_out_longitude': geolocation[1],
                }
                res.write(vals)
        if geofence:
            if self.attendance_state == 'checked_in':
                vals = {
                    'check_in_geofence_ids': geofence,
                }
                res.write(vals)
            else:
                vals = {
                    'check_out_geofence_ids': geofence,
                }
                res.write(vals)
        if photo:
            if self.attendance_state == 'checked_in':
                res.write({
                    'check_in_photo': photo[0],
                })
            else:
                res.write({
                    'check_out_photo': photo[0],
                })
        if ipaddress:
            if self.attendance_state == 'checked_in':
                res.write({
                    'check_in_ipaddress': ipaddress,
                })
            else:
                res.write({
                    'check_out_ipaddress': ipaddress,
                })
        return res
    
    @api.model
    def attendance_kiosk_recognition(self, employee_id=False, location=False, ip_address=False, geofence_ids=False, photo_img64= False):
        employee = self.sudo().search([('id', '=', employee_id)], limit=1)
        if employee:            
            return employee.with_context(attendance_geolocation=location, attendance_ipaddress=ip_address, attendance_geofence=geofence_ids, attendance_photo=photo_img64)._attendance_action('hr_attendance.hr_attendance_action_kiosk_mode')
        return {'warning': _('No employee corresponding to face id %(employee)s') % {'employee': id}}
    
class HrEmployeeFaces(models.Model):
    _name = "hr.employee.faces"
    _description = "Face Recognition Images"
    _inherit = ['image.mixin']
    _order = 'id'

    name = fields.Char("Name", related='employee_id.name')
    image = fields.Binary("Images")
    descriptor = fields.Text(string='Face Descriptor')
    has_descriptor = fields.Boolean(string="Has Face Descriptor",default=False, compute='_compute_has_descriptor', readonly=True, store=True)
    employee_id = fields.Many2one("hr.employee", "User", index=True, ondelete='cascade')

    @api.depends('descriptor')
    def _compute_has_descriptor(self):
        for rec in self:
            rec.has_descriptor = True if rec.descriptor else False