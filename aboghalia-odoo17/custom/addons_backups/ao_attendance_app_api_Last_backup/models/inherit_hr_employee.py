import json
import re
from odoo import models, fields, api, _
from datetime import datetime
from odoo.exceptions import UserError
from firebase_admin import messaging
from odoo.tools import html2plaintext


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # image_table = fields.One2many('image.model', 'employee_id_rel', string="images")
    uuids = fields.Text(string="Employee UUIDs")
    uuid_ids = fields.One2many('uuid.model', 'employee_id', string="UUIDs")
    checked_toggle_flag = fields.Boolean(string="Accept new UUIDs")
    fcm_token = fields.Text(string="Firebase Cloud Messaging Token")

    def accept_checked_toggle_flag(self):
        for rec in self:
            rec.checked_toggle_flag = True

    def dont_accept_checked_toggle_flag(self):
        for rec in self:
            rec.checked_toggle_flag = False

    def send_start_shift_notification(self):
        message = messaging.Message(
            # topic="shift",
            topic="user_admin",
            # token="fHbSbkyfTGO-c6ogN33p5R:APA91bGkmxbgLsenfNE7DnaTOZ0fAVcLgL3TiIPBHbvOmbRNm4awCIGxgKKC75KTTrtlr0v4vE0lZRG89UNmkLqp3MprJydSVmLjBRCXJNuVmIOOKjQ0iWk",
            notification=messaging.Notification(
                title="Check in!",
                body="This is a reminder to check in at 8 o'clock!"
            )
        )
        try:
            response = messaging.send(message)
        except Exception as e:
            print("/////////////// notification cron error")
            print(str(e))

    def send_end_shift_notification(self):
        message = messaging.Message(
            topic="shift",
            # token="fHbSbkyfTGO-c6ogN33p5R:APA91bGkmxbgLsenfNE7DnaTOZ0fAVcLgL3TiIPBHbvOmbRNm4awCIGxgKKC75KTTrtlr0v4vE0lZRG89UNmkLqp3MprJydSVmLjBRCXJNuVmIOOKjQ0iWk",
            notification=messaging.Notification(
                title="Check out!",
                body="This is a reminder to check out at 4 o'clock!"
            )
        )
        try:
            response = messaging.send(message)
        except Exception as e:
            print("/////////////// notification cron error")
            print(str(e))

    def send_location_verification_notification(self):
        employees_recs = self.env["hr.employee"].sudo().search([])
        tokens = []
        for employee_rec in employees_recs:
            if employee_rec.last_attendance_id.check_in:
                if employee_rec.free_attendance == False:
                    if employee_rec.fcm_token:
                        tokens.append(employee_rec.fcm_token)

        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title="Verifying location..."),
            data={ "check": "location" }
        )
        try:
            response = messaging.send_each_for_multicast(message)
        except Exception as e:
            print("/////////////// notification cron error")
            print(str(e))


    def send_employee_request_notification(self, employee_ids=None, serial_number=None,  end_date=None):
        """
        Send shift notification to multiple employees
        
        :param employee_ids: List of employee IDs or recordset of employees
        """
        # If no employee_ids provided, you might want to get them from a many2many field
        # For example: employee_ids = self.employee_ids
        if not employee_ids:
            return False  # Assuming this is your many2many field
        
        # If employee_ids is a recordset, convert to list of IDs

        
        # Get employee records
        employees = employee_ids
        
        notification_results = []
        
        for employee in employees:
            # Skip if employee doesn't have a user (login)
            if not employee.user_id or not employee.user_id.login:
                print(f"Skipping employee {employee.name} - No user/login found")
                continue
                
            # Create topic using user login
            topic = f"user_{employee.user_id.login}".split("@")[0].replace('.', '_').lower()
            
            message = messaging.Message(
                topic=topic,
                notification=messaging.Notification(
                     title="معاملة جديدة",
                     body=f"تم تسجيل معاملة رقم {serial_number or 'غير محدد'} "
                             f"وتاريخ الانتهاء {end_date or 'غير محدد'}"
                )
            )
            
            try:
                response = messaging.send(message)
                notification_results.append({
                    'employee_id': employee.id,
                    'employee_name': employee.name,
                    'topic': topic,
                    'success': True,
                    'response': response
                })
                print(f"Notification sent successfully to {employee.name} (topic: {topic})")
                
            except Exception as e:
                notification_results.append({
                    'employee_id': employee.id,
                    'employee_name': employee.name,
                    'topic': topic,
                    'success': False,
                    'error': str(e)
                })
                print(f"Failed to send notification to {employee.name} (topic: {topic})")
                print(f"Error: {str(e)}")
        
        return notification_results


    def _clean_html(self, html_content):
        """
        Removes HTML tags and cleans up the text for push notifications.
        Uses Odoo's built-in html2plaintext utility.
        
        :param html_content: HTML string to clean
        :return: Plain text string
        
        Developer: Odoo Developer Mohamed Adel
        """
        if not html_content:
            return ''
        
        # Use Odoo's built-in converter
        text = html2plaintext(html_content)
        
        # Additional cleanup
        text = text.strip()
        
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text

    def send_employee_chatter_notification(self, employee_ids=None, message=None, serial_number=None):
        """
        Sends push notifications to employees for a specific chatter message.
        
        :param employee_ids: recordset of employees to notify
        :param message: the message body/content to send
        :param serial_number: the serial number of the request
        :return: list of notification delivery results
        
        Developer: Odoo Developer Mohamed Adel
        """
        
        if not employee_ids or not message:
            return False
        
        if not serial_number:
            serial_number = 'غير محدد'
        
        notification_results = []
        
        for employee in employee_ids:
            if not employee.user_id or not employee.user_id.login:
                print(f"Skipping employee {employee.name} - No user/login found")
                continue
            
            topic = f"user_{employee.user_id.login}".split("@")[0].replace('.', '_').lower()
            
            # Clean the message body
            message_body = self._clean_html(message)
            
            fcm_message = messaging.Message(
                topic=topic,
                notification=messaging.Notification(
                    title=f"رسالة جديدة - في المعاملة رقم {serial_number}",
                    body=message_body[:200]  # Truncate to 200 chars
                )
            )
            
            try:
                response = messaging.send(fcm_message)
                notification_results.append({
                    'employee_id': employee.id,
                    'employee_name': employee.name,
                    'topic': topic,
                    'success': True,
                    'response': response
                })
                print(f"Chatter notification sent successfully to {employee.name} (topic: {topic})")
            
            except Exception as e:
                notification_results.append({
                    'employee_id': employee.id,
                    'employee_name': employee.name,
                    'topic': topic,
                    'success': False,
                    'error': str(e)
                })
                print(f"Failed to send chatter notification to {employee.name} (topic: {topic})")
                print(f"Error: {str(e)}")
        
        return notification_results

class Images(models.Model):
    _name = 'image.model'

    images = fields.Binary(string="images")
    employee_id_rel = fields.Many2one('hr.employee')


class LeapMergePurchaseOrders(models.TransientModel):
    _name = 'leap.accept.employee.uuid'
    _description = 'Wizard for accept employee uuid'


    def default_get(self, fields):
        default = super(LeapMergePurchaseOrders, self).default_get(fields)
        employee_ids = self.env[self._context.get('active_model')].browse(self._context.get('active_ids'))
        return default

    # def button_action_accept_for_multi_employee(self):
    #     employee_ids = self.env['hr.employee'].browse(self._context.get('active_ids', []))
    #
    #     if employee_ids:
    #         employee_ids.dis_active_check_bio()
    #
    # def button_action_check_for_multi_employee(self):
    #     employee_ids = self.env['hr.employee'].browse(self._context.get('active_ids', []))
    #     if employee_ids:
    #         employee_ids.active_check_bio()


class UUIDTable(models.Model):
    _name = 'uuid.model'

    uuid = fields.Char(string="UUID", readonly=True)
    employee_id = fields.Many2one('hr.employee')
    employee_connect = fields.Many2one('hr.employee')
    approval_flag = fields.Boolean(string="Approved")
    # uuid_status= fields.Selection([('approved', 'Approved'), ('reject', 'Rejected')], string='uuid status')
    approval_date = fields.Datetime(string="Approval Date")
    rejection_date = fields.Datetime(string="Rejection Date")

    @api.onchange('approval_flag')
    def _change_date(self):
        for rec in self:
            now = datetime.now()
            if rec.approval_flag == True:
                rec.approval_date = now
            else:
                rec.rejection_date = now

    def accepted(self):
        for rec in self:
            rec.approval_flag = True
            # rec.uuid_status= False

    def check_and_update_uuid(self, uuid_data, employee_id):
        """
        - check if checked_toggle_flag (accepts new UUIDs) is true or false
        - if false:
            # check if it exists, check if it's approved or not
            # if it doesn't exist, send a message that's saying "UUID is not approved, and cannot create new ones!"
        - if true:
            # check if it exists, check if it's approved or not
            # if it doesn't exist, create new one
        """
        employee = self.env['hr.employee'].sudo().search([('id', '=', employee_id)], limit=1)
        existing_uuid = self.sudo().search([
            ('uuid', '=', uuid_data),
            ('employee_id', '=', employee_id)
            ], limit=1
        )

        if employee.sudo().checked_toggle_flag == False:
            if existing_uuid:
                if existing_uuid.approval_flag:
                    return {
                        'state': 'approved',
                        'message': 'UUID is approved!'
                    }
                else:
                    raise UserError(_(
                        "UUID is not approved!"
                    ))
                    # return {
                    #     'state': 'rejected',
                    #     'message': 'UUID is not approved!'
                    # }
            else:
                raise UserError(_(
                    "UUID is not accepted, and cannot create new ones!"
                ))
                # return {
                #     'state': 'rejected',
                #     'message': 'UUID is not approved, and cannot create new ones!'
                # }
        else:
            if existing_uuid:
                if existing_uuid.approval_flag:
                    return {
                        'state': 'approved',
                        'message': 'UUID is approved!'
                    }
                else:
                    raise UserError(_(
                        "UUID is not approved!"
                    ))
                    # return {
                    #     'state': 'rejected',
                    #     'message': 'UUID is not approved!'
                    # }
            else:
                self.create({
                    'uuid': uuid_data,
                    'employee_id': employee_id,
                    'approval_flag': True,
                    # 'uuid_status': False
                })
                return {
                    'state': 'created',
                    'message': 'UUID registered, and pending approval!'
                }

    def check_and_update_bio(self, uuid_data, employee_id):
        """
        Checks if uuid data exists and is accepted, then updates status accordingly.
        """
        employee= self.env['hr.employee'].sudo().search([('id', '=', employee_id)], limit=1)
        existing_uuid = self.sudo().search([
            ('uuid', '=', uuid_data),
            ('employee_id', '=', employee_id)
        ], limit=1)
        if employee.sudo().checked_toggle_flag:
            return {
                'state': 'approved',
                'message': 'UUID verification successful'
            }
            # if existing_uuid.accept_flag:
            #     existing_uuid.write({'uuid_status': 'approved','approval_date':fields.Datetime.now(),})
            #     return {
            #         'state': 'approved',
            #         'message': 'UUID verification successful'
            #     }
            # else:
            #     existing_uuid.write({'uuid_status': 'reject'})
            #     return {
            #         'state': 'rejected',
            #         'message': 'UUID verification failed'
            #     }
        else:
            return {
                'state': 'rejected',
                'message': 'UUID verification failed'
            }
        # elif existing_uuid and not employee.checked_toggle_flag:
        #         return {
        #             'state': 'approved',
        #             'message': 'UUID Accept successful'
        #         }
        # elif not existing_uuid and not employee.checked_toggle_flag:
        #         self.create({
        #             'uuid': uuid_data,
        #             'employee_id': employee_id,
        #             'accept_flag': True,
        #             'uuid_status': False
        #         })
        #         return {
        #             'state': 'approved',
        #             'message': 'UUID Accept successful'
        #         }