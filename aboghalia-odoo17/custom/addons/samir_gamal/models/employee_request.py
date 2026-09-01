from dataclasses import field
from datetime import date
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import qrcode
import base64
from io import BytesIO
import logging

class EmployeeRequest(models.Model):
    _name = 'employee.request'
    _description = 'Employee Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'serial_number'

    # The Common Fields
    # request_id = fields.Integer(
    #     string='ID',
    #     readonly=True,
    #     required=True,
    #     copy=False,
    #     default=0
    # )



    
    # # PREFIXES = {
    # #     "شركة م سمير صالح ابو غليه": "Sce",
    # #     "شركة م جمال حريري": "Jbh",
    # #     "المجلس التنسيقي": "Sjc",
    # #     "المختبرات الطايف": "Taif",
    # #     "المختبرات جده": "Jeed",
    # # }

    # def _get_prefix_by_company(self, company_name):
    #     return self.PREFIXES.get(company_name, 'GEN')
   
    def _get_employee_request_prefix(self):
        return self.company_id.employee_request_prefix or ''

    #Changed the model field qr_code to store the QR code as a Char instead of Binary
    #Changes were made by Mohamed Adel
    serial_number = fields.Char(string="رقم المعاملة", readonly=True, copy=False)


    @api.model
    def create(self, vals):
        res = super().create(vals)

        if not res.serial_number and res.company_id:
            prefix = res._get_employee_request_prefix()
            domain = [
                ('serial_number', 'ilike', prefix + '%'),
                ('company_id', '=', res.company_id.id),
                ('id', '!=', res.id),
            ]
            # Include archived records in search
            last_request = self.with_context(active_test=False).search(
                domain, order='serial_number desc', limit=1
            )

            next_num = 1
            if last_request and last_request.serial_number:
                last_serial = last_request.serial_number.replace(prefix, '').strip()
                if last_serial.isdigit():
                    next_num = int(last_serial) + 1

            res.serial_number = f"{prefix}{str(next_num).zfill(4)}"

        if res.employee_ids:
            employee_obj = self.env['hr.employee']
            employee_obj.send_employee_request_notification(
                employee_ids=res.employee_ids,
                serial_number=res.serial_number,
                end_date=res.end_date.strftime('%Y-%m-%d') if res.end_date else None
            )

        return res






    company_id = fields.Many2one('res.company', string="الشركة", default=lambda self: self.env.company, required=True)
    partner_id=fields.Many2one('res.partner',  required=True,string='اسم العميل/الجهة ')
    partner_phone = fields.Char(
        string="رقم الهاتف",
        related='partner_id.phone',
        store=True,
        readonly=False
    )
    request_topic = fields.Text(string="موضوع المعاملة / الجهة")
    description = fields.Html(required=True,string= "الوصف")
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id, required=True)
    transaction_type = fields.Many2one(
    'employee.request.type',
    string="نوع المعاملة",
    tracking=True, required=True)
    status = fields.Selection([
    ('new', 'جديد'),
    ('in_progress', 'قيد الإجراء'),
    ('overdue', 'متأخر'),
    ('done', 'منتهى'),
    ], string="Status", compute='_compute_status', store=True, tracking=True, default='new')

    employee_ids = fields.Many2many('hr.employee', string="الموظف المسؤول", tracking=True, required=True)
    start_date = fields.Date(string="تاريخ البداية" , tracking=True, required=True)
    end_date = fields.Date(string="تاريخ النهاية" , tracking=True, required=True)
    active = fields.Boolean(string='Active', default=True)



    
    @api.depends('end_date')
    def _compute_status(self):
        today = date.today()
        for rec in self:
            if rec.status == 'done':
                continue  # Keep 'done' as final
            if rec.end_date and rec.end_date < today:
                rec.status = 'overdue'
            elif rec.status not in ['overdue', 'done']:
                if rec.status != 'in_progress':
                    rec.status = 'new'

    # customer_id = fields.Many2one('res.partner', string="Customer Name")
    department= fields.Many2one('hr.department',string="القسم" ,  tracking=True, required=True)
    incoming_number = fields.Char(string="رقم الوارد")
    created_by = fields.Many2one('res.users', string="Created By", default=lambda self: self.env.user, readonly=True)
    tag_ids = fields.Many2many('employee.request.tag', string="Tags", required=True)  # new m2m field for tags
    qr_code = fields.Char("QR Code", compute='_compute_qr_code', store=True)

    def write(self, vals):
        # Handle serial number generation after write
        if 'company_id' in vals:
            for record in self:
                if self.env['res.company'].browse(vals['company_id']).employee_request_prefix:
                    prefix = self.env['res.company'].browse(vals['company_id']).employee_request_prefix
                    
                    domain = [
                        ('serial_number', 'ilike', prefix + '%'),
                        ('company_id', '=', vals['company_id']),
                        ('id', '!=', record.id),
                    ]
                    last_request = self.search(domain, order='id desc', limit=1)
                    
                    next_num = 1
                    if last_request and last_request.serial_number:
                        last_serial = last_request.serial_number.replace(prefix, '').strip()
                        if last_serial.isdigit():
                            next_num = int(last_serial) + 1
                    
                    new_serial = f"{prefix}{str(next_num).zfill(4)}"
                    
                    # Update using SQL to avoid recursion
                    vals['serial_number'] = new_serial
                    # # Invalidate cache
                    # record.invalidate_cache(['serial_number'])
        
        # Call parent write method first
        res = super().write(vals)
        
       
        
        return res
    
    def action_start(self):
        for rec in self:
            rec.status = 'in_progress'

    
    def action_in_progress(self):
        for rec in self:
            rec.status = 'in_progress'

    
    def action_overdue(self):
        for rec in self:
            rec.status = 'overdue'

    
    def action_done(self):
        for rec in self:
            rec.status = 'done'
            rec.active = False

    @api.depends('serial_number')
    def _compute_qr_code(self):
        for record in self:
            if record.serial_number:
                try:
                    base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    request_url = f"{base_url}/web#id={record.id}&model=employee.request&view_type=form"

                    qr = qrcode.QRCode(box_size=10, border=4)
                    qr.add_data(request_url)
                    qr.make(fit=True)
                    img = qr.make_image(fill='black', back_color='white')

                    buffer = BytesIO()
                    img.save(buffer, format='PNG')
                    record.qr_code = base64.b64encode(buffer.getvalue())

                except Exception as e:
                    _logger.warning(f"QR Generation Error: {e}")
                    record.qr_code = False
            else:
                record.qr_code = False





    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError("تاريخ البداية يجب أن يكون قبل تاريخ النهاية.")

    def action_open_whatsapp(self):
        self.ensure_one()
        phone = self.partner_phone
        if phone:
            clean_phone = phone.replace(" ", "").replace("+", "").replace("-", "").replace("(", "").replace(")", "")
            url = f"https://wa.me/{clean_phone}"
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }
        else:
            return {'type': 'ir.actions.act_window_close'}


    def message_post(self, **kwargs):
        """
        Override message_post to send push notifications to employees
        when a new message is posted on the request.
        
        Developer: Odoo Developer Mohamed Adel
        """
        # Call the original message_post method
        message = super(EmployeeRequest, self).message_post(**kwargs)
        
        # Get the message body
        body = kwargs.get('body', '')
        message_type = kwargs.get('message_type', 'notification')
        
        # Only send notifications for actual messages (not notifications)
        if body and self.employee_ids:
            # Send push notification to all employees in the request
            self.env['hr.employee'].send_employee_chatter_notification(
                employee_ids=self.employee_ids,
                message=body,
                serial_number=self.serial_number
            )
        
        return message
    # @api.depends('serial_number', 'start_date', 'end_date', 'status')
    # def _compute_qr_code(self):
    #     for record in self:
    #         if record.id:
    #             try:
    #                 qr_text = (
    #                     f"رقم المعاملة: {record.request_id or ''}\n"
    #                     f"العميل: {record.customer_id.name or ''}\n"
    #                     f"تاريخ البداية: {record.start_date or ''}\n"
    #                     f"تاريخ الانتهاء: {record.end_date or ''}\n"
    #                     f"الحالة: {dict(self.fields_get(allfields=['state'])['state']['selection']).get(record.state, '')}"
    #                 )

    #                 qr = qrcode.QRCode(box_size=10, border=4)
    #                 qr.add_data(qr_text)
    #                 qr.make(fit=True)
    #                 img = qr.make_image(fill='black', back_color='white')
    #                 buffer = BytesIO()
    #                 img.save(buffer, format='PNG')
    #                 record.qr_code = base64.b64encode(buffer.getvalue())
    #             except Exception:
    #                 record.qr_code = False
    #         else:
    #             record.qr_code = False



   



    # api.depends('request_id')  
    # def _compute_qr_code(self):
    #     for record in self:
    #         if record.id:
    #             try:
    #                 base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #                 request_url = f"{base_url}/web#id={record.id}&model=employee.request&view_type=form"
    #                 qr = qrcode.QRCode(box_size=10, border=4)
    #                 qr.add_data(request_url)
    #                 qr.make(fit=True)
    #                 img = qr.make_image(fill='black', back_color='white')
    #                 buffer = BytesIO()
    #                 img.save(buffer, format='PNG')
    #                 record.qr_code = base64.b64encode(buffer.getvalue())
    #             except Exception:
    #                 record.qr_code = False
    #         else:
    #             record.qr_code = False

   

    # # Cover Letter
    # cover_letter_purpose = fields.Char(string="Purpose of Cover Letter")
    # cover_letter_destination = fields.Char(string="Destination Company")
    # cover_letter_language = fields.Selection([('ar', 'Arabic'), ('en', 'English')], string="Letter Language")

    # #Vacation 
    # vacation_type = fields.Selection([
    #     ('annual', 'Annual'),
    #     ('sick', 'Sick'),
    #     ('unpaid', 'Unpaid'),
    #     ('other', 'Other'),
    # ], string="Vacation Type")
    # vacation_start_date = fields.Date(string="Vacation Start Date")
    # vacation_end_date = fields.Date(string="Vacation End Date")
    # vacation_days = fields.Integer(string="Number of Vacation Days", compute='_compute_vacation_days')

    # #Equipment 
    # equipment_type = fields.Selection([
    #     ('laptop', 'Laptop'),
    #     ('monitor', 'Monitor'),
    #     ('mobile', 'Mobile'),
    #     ('other', 'Other'),
    # ], string="Equipment Type")
    # equipment_justification = fields.Text(string="Justification")
    # equipment_urgency = fields.Selection([
    #     ('low', 'Low'),
    #     ('medium', 'Medium'),
    #     ('high', 'High'),
    # ], string="Urgency Level")

    # # Training
    # training_course = fields.Char(string="Training Course Name")
    # training_provider = fields.Char(string="Training Provider")
    # training_start_date = fields.Date(string="Training Start Date")
    # training_end_date = fields.Date(string="Training End Date")

    # #Loan 
    # loan_amount = fields.Monetary(string="Loan Amount", currency_field='currency_id')
    # loan_installments = fields.Integer(string="Number of Installments")
    # loan_reason = fields.Text(string="Loan Reason")
    # loan_start_date = fields.Date(string="Loan Start Date")

    # #Money (Cash Request)
    # money_amount = fields.Monetary(string="Amount", currency_field='currency_id')
    # money_payment_method = fields.Selection([
    #     ('cash', 'Cash'),
    #     ('bank_transfer', 'Bank Transfer'),
    #     ('other', 'Other'),
    # ], string="Payment Method")
    # money_payment_purpose = fields.Char(string="Payment Purpose")

    
    # @api.depends('vacation_start_date', 'vacation_end_date')
    # def _compute_vacation_days(self):
    #     for rec in self:
    #         if rec.vacation_start_date and rec.vacation_end_date:
    #             delta = rec.vacation_end_date - rec.vacation_start_date
    #             rec.vacation_days = delta.days + 1 if delta.days >= 0 else 0
    #         else:
    #             rec.vacation_days = 0

    # # approver depends on the type of request
    # @api.depends('request_type', 'employee_id')
    # def _compute_approver(self):
    #     for rec in self:
    #         rec.approver_id = False  # go default

    #         if not rec.employee_id:
    #             continue

    #         if rec.request_type == 'money':
    #             group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
    #         elif rec.request_type == 'cover_letter':
    #             group = self.env.ref('hr.group_hr_manager', raise_if_not_found=False)
    #         elif rec.request_type == 'vacation':
    #             rec.approver_id = rec.employee_id.parent_id.user_id.id if rec.employee_id.parent_id else False
    #             continue
    #         elif rec.request_type == 'equipment':
    #             group = self.env.ref('base.group_system', raise_if_not_found=False)
    #         elif rec.request_type == 'training':
    #             group = self.env.ref('hr.group_hr_user', raise_if_not_found=False)  # عدّل حسب جروب التدريب عندك
    #         elif rec.request_type == 'loan':
    #             group = self.env.ref('account.group_account_user', raise_if_not_found=False)
    #         else:
    #             group = None

    #         if group:
    #             rec.approver_id = self.env['res.users'].search([('groups_id', 'in', group.id)], limit=1).id

    #         #  if there is no specific head , it will be send to the manager direct
    #         if not rec.approver_id and rec.department_id and rec.department_id.manager_id:
    #             rec.approver_id = rec.department_id.manager_id.user_id.id

    # #  Actions
    # def action_submit(self):
    #     for rec in self:
    #         rec.message_post(body="Request submitted and sent to approver: %s" % (rec.approver_id.name if rec.approver_id else "None"))
    #         rec.state = 'submit'

    # def action_to_approve(self):
    #     for rec in self:
    #         rec.state = 'to_approve'
    #         rec.message_post(body="Request moved to 'To Approve' state and sent to approver: %s" % (rec.approver_id.name if rec.approver_id else "None"))

    # def action_approve(self):
    #     for rec in self:
    #         rec.state = 'approved'
    #         rec.message_post(body="Request has been approved by %s." % self.env.user.name)

    # def action_done(self):
    #     for rec in self:
    #         rec.state = 'done'
    #         rec.message_post(body="Request marked as Done.")

    # def action_refuse(self):
    #     for rec in self:
    #         rec.state = 'refused'
    #         rec.message_post(body="Request has been refused.")

    # def action_reset_draft(self):
    #     for rec in self:
    #         rec.state = 'draft'
    #         rec.message_post(body="Request has been reset to Draft.")

   