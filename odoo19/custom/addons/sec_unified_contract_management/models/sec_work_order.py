# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class SecWorkOrder(models.Model):
    _name = 'sec.work.order'
    _description = 'أمر عمل العقد الموحد (شركة الكهرباء)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='رقم أمر العمل الداخلي', copy=False, readonly=True, default=lambda self: self.env['ir.sequence'].next_by_code('sec.work.order') or '/')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='الشركة', default=lambda self: self.env.company, required=True)
    project_id = fields.Many2one('sec.unified.project', string='المشروع / العقد الموحد الرئيسي', required=True, tracking=True)

    # 1. ترويسة الإسناد والبيانات الأساسية
    order_title = fields.Char(string='مسمى / عنوان أمر العمل', required=True, tracking=True)
    region = fields.Selection([
        ('makkah', 'منطقة مكة المكرمة'),
        ('madinah', 'منطقة المدينة المنورة'),
        ('jeddah', 'محافظة جدة'),
        ('taif', 'محافظة الطائف'),
        ('riyadh', 'منطقة الرياض'),
        ('eastern', 'المنطقة الشرقية'),
        ('southern', 'المنطقة الجنوبية'),
        ('northern', 'المنطقة الشمالية'),
        ('other', 'أخرى'),
    ], string='المنطقة / الفرع', default='makkah', required=True, tracking=True)

    sec_work_order_no = fields.Char(string='رقم أمر عمل الكهرباء (SEC WO No)', required=True, tracking=True, index=True)
    sec_notification_no = fields.Char(string='رقم الإشعار', tracking=True, index=True)
    contractor_id = fields.Many2one('res.partner', string='المقاول / مقاول الباطن', tracking=True)
    site_location = fields.Char(string='الموقع الجغرافي / العنوان', tracking=True)
    gps_coordinates = fields.Char(string='إحداثيات GPS الموقع')
    substation_no = fields.Char(string='رقم المحطة / المغذي', tracking=True)

    work_type = fields.Selection([
        ('lv_network', 'شبكات جهد منخفض (LV)'),
        ('mv_network', 'شبكات جهد متوسط (MV)'),
        ('new_connection', 'توصيلات مشتركون جديدة'),
        ('replacement', 'إحلال وتجديد شبكات'),
        ('substation_install', 'إنشاء وتركيب محطات تحويل'),
        ('emergency', 'أعمال طوارئ وصيانة عاجلة'),
        ('other', 'أخرى'),
    ], string='نوع أمر العمل', default='lv_network', required=True, tracking=True)

    work_order_category = fields.Selection([
        ('direct_sec', 'عقد مباشر - كهرباء'),
        ('unified_contract', 'عقد موحد شامل'),
        ('turnkey', 'تسليم مفتاح'),
        ('maintenance', 'تشغيل وصيانة'),
        ('custom', 'مخصص'),
    ], string='تصنيف أمر العمل', default='unified_contract', tracking=True)

    assigned_date = fields.Date(string='تاريخ الإسناد', default=fields.Date.context_today, tracking=True)
    target_completion_date = fields.Date(string='تاريخ نهاية المشروع المتوقع (SLA)', tracking=True)
    elapsed_days = fields.Integer(string='المدة المنقضية (أيام)', compute='_compute_elapsed_days')
    estimated_value = fields.Float(string='القيمة التقديرية (ر.س)', tracking=True)

    # شريط السلسلة المتتابعة (The Cascading Workflow State Machine)
    state = fields.Selection([
        ('draft', '1. الإسناد'),
        ('survey', '2. الكشفية والتصاريح'),
        ('execution', '3. التنفيذ الميداني'),
        ('closing', '4. الإغلاق والتسليم'),
        ('invoicing', '5. الفوترة والمستخلصات'),
        ('collection', '6. التحصيل المالي'),
        ('done', '7. مكتمل ومؤرشف نهائياً'),
        ('cancelled', 'ملغي'),
    ], string='المرحلة الحالية', default='draft', tracking=True, required=True)

    # مسؤول كل مرحلة (لتوجيه التنبيه الآلي فور تسليم المرحلة)
    user_stage_survey = fields.Many2one('res.users', string='مسؤول الكشفية والتصاريح', default=lambda self: self.env.user)
    user_stage_execution = fields.Many2one('res.users', string='مهندس / مسؤول التنفيذ الميداني')
    user_stage_closing = fields.Many2one('res.users', string='مهندس الجودة / مسؤول الإغلاق')
    user_stage_invoicing = fields.Many2one('res.users', string='المحاسب / مسؤول الفوترة')
    user_stage_collection = fields.Many2one('res.users', string='مسؤول التحصيل المالي')
    user_stage_manager = fields.Many2one('res.users', string='مدير المشروع المشرف')

    # 2. الكشفية والتصاريح
    survey_date = fields.Date(string='تاريخ الكشف الميداني', tracking=True)
    surveyor_name = fields.Char(string='اسم المساح / القائم بالكشف')
    route_length_meter = fields.Float(string='طول المسار المقترح (متر طولي)', tracking=True)
    soil_type = fields.Selection([
        ('asphalt', 'إسفلتية'),
        ('rocky', 'صخرية'),
        ('sandy', 'رملية'),
        ('mixed', 'مختلطة'),
    ], string='نوع التربة والمسار', default='asphalt')
    has_obstacles = fields.Boolean(string='هل يوجد عوائق؟', tracking=True)
    obstacles_description = fields.Text(string='شرح وتفاصيل العوائق المرصودة')
    
    permit_municipality_no = fields.Char(string='رقم تصريح البلدية / الأمانة', tracking=True)
    permit_municipality_expiry = fields.Date(string='تاريخ انتهاء تصريح البلدية', tracking=True)
    permit_traffic_no = fields.Char(string='رقم تصريح إدارة المرور', tracking=True)
    permit_traffic_expiry = fields.Date(string='تاريخ انتهاء تصريح المرور')
    permit_services_cleared = fields.Boolean(string='تم التنسيق مع جهات الخدمات الأخرى (مياه، اتصالات)', tracking=True)
    permit_file = fields.Binary(string='مرفق التصريح المعتمد', attachment=True)
    permit_filename = fields.Char(string='اسم ملف التصريح')

    # 3. التنفيذ الميداني والإنجاز
    execution_start_date = fields.Date(string='تاريخ بدء التنفيذ الفعلي', tracking=True)
    execution_end_date = fields.Date(string='تاريخ انتهاء التنفيذ الفعلي', tracking=True)
    execution_team_leader = fields.Char(string='رئيس فرقة التنفيذ / المقاول')
    progress_percentage = fields.Float(string='نسبة الإنجاز الكلية %', default=0.0, tracking=True)
    
    # فكرة الإنجاز (مرحلتين)
    milestone_15_received = fields.Boolean(string='1. استلام 15%', tracking=True)
    milestone_15_date = fields.Date(string='تاريخ استلام 15%')
    milestone_full_achieved = fields.Boolean(string='2. إنجاز الأعمال بالكامل', tracking=True)
    milestone_full_date = fields.Date(string='تاريخ إنجاز الأعمال الكامل')

    # 4. الإغلاق والتسليم والمرفقات
    inspection_date = fields.Date(string='تاريخ الفحص والتسليم المشترك', tracking=True)
    inspector_sec_name = fields.Char(string='مهندس استشاري / ممثل شركة الكهرباء', tracking=True)
    inspector_contractor_name = fields.Char(string='مهندس الجودة / ممثل المقاول')
    as_built_approved = fields.Boolean(string='تم اعتماد مخططات As-Built المنفذة', tracking=True)
    megger_test_approved = fields.Boolean(string='تم اعتماد اختبارات العزل والجهد الكهربائي', tracking=True)
    
    boq_file = fields.Binary(string='تحميل المقايسة المعتمدة (BOQ)', attachment=True)
    boq_filename = fields.Char(string='اسم ملف المقايسة')
    inspection_report_file = fields.Binary(string='محضر وتقرير الفحص الميداني', attachment=True)
    inspection_report_filename = fields.Char(string='اسم ملف الفحص')
    as_built_file = fields.Binary(string='مخطط As-Built المعتمد', attachment=True)
    as_built_filename = fields.Char(string='اسم ملف As-Built')

    # 5. الفوترة والمستخلصات
    claim_date = fields.Date(string='تاريخ رفع المستخلص للكهرباء', tracking=True)
    invoice_number = fields.Char(string='رقم الفاتورة / المستخلص', tracking=True)
    original_value = fields.Float(string='القيمة الأصلية للمستخلص (قبل الضريبة)', tracking=True)
    tax_amount = fields.Float(string='ضريبة القيمة المضافة 15%', compute='_compute_invoicing_totals', store=True)
    total_invoiced_value = fields.Float(string='إجمالي قيمة المستخلص بالضريبة (ر.س)', compute='_compute_invoicing_totals', store=True)
    invoice_status = fields.Selection([
        ('draft', 'قيد الإعداد المكتبي'),
        ('submitted', 'تم الرفع للاستشاري / شركة الكهرباء'),
        ('approved', 'معتمد نهائياً من شركة الكهرباء'),
        ('rejected', 'مرفوض / ملاحظات للتعديل'),
    ], string='حالة اعتماد المستخلص', default='draft', tracking=True)

    # 6. التحصيل المالي
    payment_reference = fields.Char(string='رقم إشعار الدفع / الحوالة البنكية', tracking=True)
    payment_date = fields.Date(string='تاريخ التحصيل الفعلي', tracking=True)
    collected_amount = fields.Float(string='المبلغ المحصل فعلياً (ر.س)', tracking=True)
    deductions_amount = fields.Float(string='الاستقطاعات والخصومات (إن وجدت)', tracking=True)
    remaining_amount = fields.Float(string='المبلغ المتبقي غير المحصل', compute='_compute_collection_status', store=True)
    collection_status = fields.Selection([
        ('pending', 'قيد انتظار التحصيل'),
        ('partial', 'تحصيل جزئي'),
        ('fully_collected', 'تم التحصيل بالكامل'),
    ], string='حالة التحصيل', default='pending', tracking=True)

    # الجانب الخدمي والأصول والمبنى
    building_reference = fields.Char(string='المبنى / المحطة التابعة')
    asset_equipment_ids = fields.Text(string='الأصول والمعدات المرتبطة')
    software_system_link = fields.Char(string='كود / رابط النظام البرمجي')

    # الإلغاء
    cancellation_reason = fields.Text(string='سبب إلغاء أمر العمل', tracking=True)
    cancellation_date = fields.Date(string='تاريخ الإلغاء')
    cancelled_by_id = fields.Many2one('res.users', string='تم الإلغاء بواسطة')

    @api.depends('assigned_date')
    def _compute_elapsed_days(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.assigned_date:
                rec.elapsed_days = (today - rec.assigned_date).days
            else:
                rec.elapsed_days = 0

    @api.depends('original_value')
    def _compute_invoicing_totals(self):
        for rec in self:
            rec.tax_amount = rec.original_value * 0.15
            rec.total_invoiced_value = rec.original_value + rec.tax_amount

    @api.depends('total_invoiced_value', 'collected_amount', 'deductions_amount')
    def _compute_collection_status(self):
        for rec in self:
            total = rec.total_invoiced_value
            paid = rec.collected_amount + rec.deductions_amount
            rec.remaining_amount = max(0.0, total - paid)
            if total > 0:
                if paid >= total:
                    rec.collection_status = 'fully_collected'
                elif paid > 0:
                    rec.collection_status = 'partial'
                else:
                    rec.collection_status = 'pending'
            else:
                rec.collection_status = 'pending'

    # دالة التنبيه الآلي المتتابع للمسؤول التالي
    def _send_stage_notification(self, next_user, stage_title, msg_text):
        self.ensure_one()
        if next_user:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'مرحلة جديدة: {stage_title}',
                note=f'{msg_text}\nأمر العمل: {self.name} - {self.sec_work_order_no}',
                user_id=next_user.id
            )
        self.message_post(
            body=f'🔔 **تم الانتقال لمرحلة: {stage_title}**\n{msg_text}',
            subtype_xmlid='mail.mt_comment'
        )

    # 1️⃣ إنهاء الإسناد ──(تنبيه آلي)──► 👷 فريق الكشفية والتصاريح
    def action_to_survey(self):
        self.ensure_one()
        self.state = 'survey'
        target_user = self.user_stage_survey or self.env.user
        self._send_stage_notification(target_user, '2. الكشفية والتصاريح', 'تم إسناد أمر العمل، يرجى استخراج التصاريح والكشف الميداني.')

    # 2️⃣ اعتماد التصريح ──(تنبيه آلي)──► 🚜 المهندس وفريق التنفيذ
    def action_to_execution(self):
        self.ensure_one()
        if not self.permit_municipality_no:
            raise ValidationError(_('تنبيه: لا يمكن بدء التنفيذ الميداني بدون إدخال رقم تصريح البلدية/الأمانة!'))
        self.state = 'execution'
        target_user = self.user_stage_execution or self.env.user
        self._send_stage_notification(target_user, '3. التنفيذ الميداني', 'صدر التصريح، يرجى بدء الحفر والتمديد والأعمال الميدانية.')

    # 3️⃣ اكتمال التنفيذ ──(تنبيه آلي)──► 🔍 مهندس الجودة والاستشاري
    def action_to_closing(self):
        self.ensure_one()
        if not self.milestone_full_achieved and not self.milestone_15_received:
            raise ValidationError(_('تنبيه: يجب تأكيد مرحلة الإنجاز الميداني قبل الإغلاق والتسليم!'))
        self.state = 'closing'
        target_user = self.user_stage_closing or self.env.user
        self._send_stage_notification(target_user, '4. الإغلاق والتسليم', 'اكتمل التنفيذ، يرجى الفحص المشترك ورفع اختبارات العزل ومخططات As-Built.')

    # 4️⃣ اعتماد الإغلاق ──(تنبيه آلي)──► 📑 المحاسب ومنسق العقود
    def action_to_invoicing(self):
        self.ensure_one()
        if not self.as_built_approved or not self.megger_test_approved:
            raise ValidationError(_('يجب تأكيد اعتماد مخططات As-Built واختبارات العزل الكهربائي قبل التحويل للفوترة!'))
        self.state = 'invoicing'
        target_user = self.user_stage_invoicing or self.env.user
        self._send_stage_notification(target_user, '5. الفوترة والمستخلصات', 'اكتملت الورقيات والاعتمادات، يرجى إعداد ورفع المستخلص لشركة الكهرباء.')

    # 5️⃣ اعتماد المستخلص ──(تنبيه آلي)──► 💳 الإدارة المالية والتحصيل
    def action_to_collection(self):
        self.ensure_one()
        if self.invoice_status != 'approved':
            raise ValidationError(_('يجب أن تكون حالة المستخلص (معتمد نهائياً من شركة الكهرباء) للانتقال للتحصيل!'))
        self.state = 'collection'
        target_user = self.user_stage_collection or self.env.user
        self._send_stage_notification(target_user, '6. التحصيل المالي', 'اعتمدت شركة الكهرباء المستخلص، يرجى متابعة واستلام الدفعات البنكية.')

    # 6️⃣ اكتمال التحصيل ──(تنبيه آلي)──► 👔 مدير المشروع
    def action_mark_done(self):
        self.ensure_one()
        if self.collection_status != 'fully_collected':
            raise ValidationError(_('لا يمكن إغلاق وأرشفة أمر العمل نهائياً حتى يتم التحصيل بالكامل!'))
        self.state = 'done'
        target_user = self.user_stage_manager or self.env.user
        self._send_stage_notification(target_user, '7. المكتمل والمؤرشف', 'تم التحصيل بالكامل، تم إغلاق وأرشفة أمر العمل بنجاح تام.')

    def action_cancel_dialog(self):
        self.ensure_one()
        return {
            'name': 'إلغاء أمر العمل',
            'type': 'ir.actions.act_window',
            'res_model': 'sec.work.order',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'views': [(self.env.ref('sec_unified_contract_management.view_sec_work_order_cancel_wizard').id, 'form')],
        }

    def action_confirm_cancel(self):
        self.ensure_one()
        if not self.cancellation_reason:
            raise ValidationError(_('يرجى كتابة سبب الإلغاء بشكل إلزامي قبل تأكيد الإلغاء.'))
        self.write({
            'state': 'cancelled',
            'cancellation_date': fields.Date.context_today(self),
            'cancelled_by_id': self.env.user.id,
        })
        self.message_post(body=f'❌ **تم إلغاء أمر العمل.**\n**السبب:** {self.cancellation_reason}')

    def action_reset_to_draft(self):
        self.ensure_one()
        self.state = 'draft'

    # حماية السجلات ومنع الحذف النهائي
    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancelled'):
                raise UserError(_('لحماية سلامة السجلات والفواتير: لا يمكن حذف أمر العمل نهائياً بعد إسناده أو البدء فيه!\nيمكنك استخدام خيار (إلغاء أمر العمل) لتغيير حالته إلى ملغي مع حفظ السجلات.'))
        return super(SecWorkOrder, self).unlink()
