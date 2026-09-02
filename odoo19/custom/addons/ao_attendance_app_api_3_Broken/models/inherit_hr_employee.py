import json
import re
from odoo import models, fields, api, _
from datetime import datetime, timedelta
from datetime import date as date_module
from odoo.exceptions import UserError
from firebase_admin import messaging



class AoSection(models.Model):
    _name = "ao.section.samir"

    name = fields.Char(string="name")
    color = fields.Selection(selection=[
        ('0', 'None'),
        ('1', 'Dark Blue'),
        ('2', 'Tan'),
        ('3', 'Maximum Blue Green'),
        ('4', 'Skobeloff'),
        ('5', 'Platinum'),
        ('6', 'Black'),

    ],
        string="Color",
        default='0'
    )


class AoRequest(models.Model):
    _name = "ao.request.samir"
    name = fields.Char(string="name")


class AoExchange(models.Model):
    _name = "ao.exchange.samir"
    name = fields.Char(string="name")


class AoManagement(models.Model):
    _name = "ao.management.samir"

    name = fields.Char(string="name")


class State(models.Model):
    _name = "ao.state.samir"

    name = fields.Char(string="name")



from odoo import models, fields, api


class AppNotification(models.Model):
    _name = 'app.notification'
    _description = 'App Notifications'
    _order = 'create_date desc'

    title = fields.Char(string='Title', required=True)
    body = fields.Text(string='Body', required=True)
    user_id = fields.Many2one('res.users', string='User', ondelete='set null')
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed')
    ], string='Status', default='success')



class HrEmployee(models.Model):
    _inherit = "hr.expense"

    y_section = fields.Many2one('ao.section.samir', string = "القسم")
    x_request_type = fields.Many2one('ao.request.samir', string = "نوع الطلب")
    x_exchange_method = fields.Many2one('ao.exchange.samir', string = "طريقة الصرف")
    x_management_approval = fields.Many2one('ao.management.samir', string = "اعتماد اإلدارة")
    x_state = fields.Many2one('ao.state.samir', string = "الحالة")
    x_responses = fields.Text(string = "الردود")
    x_notes = fields.Text(string = "الملاحظات")
    priority = fields.Selection(
        [('0', 'Low'), ('1', 'Normal'), ('2', 'High'), ('3', 'Very High')],
        string='الأولوية',
        default='1'
    )

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
            topic="global",
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


    def send_notification_to_user(self, employee_id, title, body, data=None):
        """
        Send notification to a specific employee/user

        :param employee_id: Employee record or ID
        :param title: Notification title
        :param body: Notification body message
        :param data: Optional dictionary of additional data to send
        :return: dict with success status and response/error
        """
        # Get employee record if ID is passed
        if isinstance(employee_id, int):
            employee = self.env['hr.employee'].sudo().browse(employee_id)
        else:
            employee = employee_id

        if not employee.exists():
            return {
                'success': False,
                'error': 'Employee not found'
            }

        # Check if employee has a user with login
        if not employee.user_id or not employee.user_id.login:
            return {
                'success': False,
                'error': f'Employee {employee.name} has no user/login'
            }

        # Create topic using user login
        topic = f"user_{employee.user_id.login}".split("@")[0].replace('.', '_').lower()

        message_params = {
            'topic': topic,
            'notification': messaging.Notification(
                title=title,
                body=body
            )
        }

        # Add data payload if provided
        if data:
            message_params['data'] = data

        message = messaging.Message(**message_params)

        try:
            response = messaging.send(message)
            
            # Create notification record on success
            self.env['app.notification'].sudo().create({
                'title': title,
                'body': body,
                'user_id': employee.user_id.id,
                'status': 'success',
            })
            
            return {
                'success': True,
                'employee_id': employee.id,
                'employee_name': employee.name,
                'topic': topic,
                'response': response
            }
        except Exception as e:
            # Create notification record on failure
            self.env['app.notification'].sudo().create({
                'title': title,
                'body': body,
                'user_id': employee.user_id.id,
                'is_general': False,
                'topic': topic,
                'status': 'failed',
                'error_message': str(e),
                'data': json.dumps(data) if data else False,
            })
            
            return {
                'success': False,
                'employee_id': employee.id,
                'employee_name': employee.name,
                'topic': topic,
                'error': str(e)
            }


    def send_general_notification(self, title, body, topic="general", data=None):
        """
        Send a general/broadcast notification to all subscribed users

        :param title: Notification title
        :param body: Notification body message
        :param topic: Topic to send to (default: 'general')
        :param data: Optional dictionary of additional data to send
        :return: dict with success status and response/error
        """
        message_params = {
            'topic': topic,
            'notification': messaging.Notification(
                title=title,
                body=body
            )
        }

        # Add data payload if provided
        if data:
            message_params['data'] = data

        message = messaging.Message(**message_params)

        try:
            response = messaging.send(message)
            
            # Create notification record on success (no user_id for general)
            self.env['app.notification'].sudo().create({
                'title': title,
                'body': body,
                'user_id': False,  # No user for general notifications
                'status': 'success',
            })
            
            return {
                'success': True,
                'topic': topic,
                'response': response
            }
        except Exception as e:
            print(f"/////////////// general notification error: {str(e)}")
            
            # Create notification record on failure (no user_id for general)
            self.env['app.notification'].sudo().create({
                'title': title,
                'body': body,
                'user_id': False,  # No user for general notifications
                'status': 'failed',
            })
            
            return {
                'success': False,
                'topic': topic,
                'error': str(e)
            }


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

    # =====================================================
    # DOCUMENT/ID EXPIRY NOTIFICATION (Cron Job)
    # =====================================================

    def send_document_expiry_notifications(self):
        """
        Cron job to check for documents expiring within 2 months
        and send notifications to employee and admin.
        Repeats every 10 days for documents in the warning period.
        """
        today = date_module.today()
        two_months_later = today + timedelta(days=60)

        # Check if employee.document model exists
        if 'employee.document' not in self.env:
            return []

        # Get all documents expiring within 2 months
        expiring_documents = self.env['employee.document'].sudo().search([
            ('expiry_date', '!=', False),
            ('expiry_date', '<=', two_months_later),
            ('expiry_date', '>=', today),
            ('state', '=', 'approved'),
            ('is_current', '=', True),
        ])

        doc_type_labels = {
            'national_id_front': 'الهوية الوطنية',
            'national_id_back': 'الهوية الوطنية',
            'passport': 'جواز السفر',
            'iqama': 'الإقامة',
        }

        # Get admin users (HR managers)
        admin_employees = self.env['hr.employee'].sudo().search([
            ('user_id.groups_id.category_id.name', '=', 'Human Resources')
        ])

        notification_results = []

        for doc in expiring_documents:
            days_until_expiry = (doc.expiry_date - today).days
            doc_type = doc_type_labels.get(doc.document_type, doc.document_type)
            employee = doc.employee_id

            # Notify employee
            if employee:
                title = "⚠️ تنبيه: مستند قارب على الانتهاء"
                body = f"مستند {doc_type} سينتهي خلال {days_until_expiry} يوم (تاريخ الانتهاء: {doc.expiry_date})"

                result = self.send_notification_to_user(
                    employee,
                    title,
                    body,
                    data={
                        'type': 'document_expiry',
                        'document_id': str(doc.id),
                        'document_type': doc.document_type,
                        'expiry_date': str(doc.expiry_date),
                        'days_remaining': str(days_until_expiry)
                    }
                )
                notification_results.append(result)

            # Notify admins
            for admin_emp in admin_employees:
                if admin_emp.id != employee.id:  # Don't notify admin twice if they're the owner
                    title = "⚠️ تنبيه إداري: مستند موظف قارب على الانتهاء"
                    body = f"مستند {doc_type} للموظف {employee.name if employee else 'غير معروف'} سينتهي خلال {days_until_expiry} يوم (تاريخ الانتهاء: {doc.expiry_date})"

                    result = self.send_notification_to_user(
                        admin_emp,
                        title,
                        body,
                        data={
                            'type': 'document_expiry_admin',
                            'document_id': str(doc.id),
                            'employee_id': str(employee.id) if employee else '',
                            'employee_name': employee.name if employee else '',
                            'document_type': doc.document_type,
                            'expiry_date': str(doc.expiry_date),
                            'days_remaining': str(days_until_expiry)
                        }
                    )
                    notification_results.append(result)

        return notification_results

    def send_id_expiry_notifications(self):
        """
        Cron job to check for employee visa/passport expiring within 2 months.
        Checks visa_expire and passport expiry dates on hr.employee.
        """
        today = date_module.today()
        two_months_later = today + timedelta(days=60)

        notification_results = []

        # Get admin users (HR managers)
        admin_employees = self.env['hr.employee'].sudo().search([
            ('user_id.groups_id.category_id.name', '=', 'Human Resources')
        ])

        # Check employees with visa expiry
        employees_with_expiring_visa = self.env['hr.employee'].sudo().search([
            ('visa_expire', '!=', False),
            ('visa_expire', '<=', two_months_later),
            ('visa_expire', '>=', today),
        ])

        for employee in employees_with_expiring_visa:
            days_until_expiry = (employee.visa_expire - today).days

            # Notify employee
            title = "⚠️ تنبيه: التأشيرة/الإقامة قاربت على الانتهاء"
            body = f"التأشيرة/الإقامة ستنتهي خلال {days_until_expiry} يوم (تاريخ الانتهاء: {employee.visa_expire})"

            result = self.send_notification_to_user(
                employee,
                title,
                body,
                data={
                    'type': 'visa_expiry',
                    'expiry_date': str(employee.visa_expire),
                    'days_remaining': str(days_until_expiry)
                }
            )
            notification_results.append(result)

            # Notify admins
            for admin_emp in admin_employees:
                if admin_emp.id != employee.id:
                    title = "⚠️ تنبيه إداري: تأشيرة/إقامة موظف قاربت على الانتهاء"
                    body = f"تأشيرة/إقامة الموظف {employee.name} ستنتهي خلال {days_until_expiry} يوم"

                    result = self.send_notification_to_user(
                        admin_emp,
                        title,
                        body,
                        data={
                            'type': 'visa_expiry_admin',
                            'employee_id': str(employee.id),
                            'employee_name': employee.name,
                            'expiry_date': str(employee.visa_expire),
                            'days_remaining': str(days_until_expiry)
                        }
                    )
                    notification_results.append(result)

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



class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    x_api_updated = fields.Boolean(string="Updated via API", default=False, copy=False, index=True)

