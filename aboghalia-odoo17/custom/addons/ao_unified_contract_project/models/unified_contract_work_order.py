# -*- coding: utf-8 -*-

import re
from urllib.parse import unquote
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class UnifiedContractWorkOrder(models.Model):
    _name = 'unified.contract.work.order'
    _description = 'أمر عمل / مهمة عقد موحد'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'work_order_number'
    _order = 'id desc'

    @api.model
    def _get_default_permit_status_id(self):
        status = self.env['unified.contract.permit.status'].search([
            '|', ('name', 'ilike', 'لم يصدر'), ('code', '=', 'not_issued')
        ], limit=1)
        if not status:
            status = self.env['unified.contract.permit.status'].create({
                'name': 'لم يصدر',
                'code': 'not_issued',
                'sequence': 1,
            })
        return status.id

    name = fields.Char(
        string='بيان أمر العمل / الفعالية',
        required=False,
        tracking=True
    )
    work_order_number = fields.Char(
        string='رقم أمر العمل',
        required=True,
        copy=False,
        tracking=True,
        help='رقم أمر العمل (خاضع لقواعد الطول والتكرار المحددة في إدارة التنبيهات)'
    )
    project_id = fields.Many2one(
        'unified.contract.project',
        string='مشروع العقد الموحد',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    contractor_id = fields.Many2one(
        'res.partner',
        string='المقاول المُنَفِذ',
        domain="[('id', 'in', project_contractor_ids)]",
        tracking=True,
        help='المقاول المسند إليه تنفيذ أمر العمل (مفلتر حسب مقاولي المشروع المعتمدين)'
    )
    project_contractor_ids = fields.Many2many(
        'res.partner',
        related='project_id.contractor_ids',
        string='مقاولو المشروع المعتمدون'
    )
    team_id = fields.Many2one(
        'unified.contract.team',
        string='فريق العمل المسؤول عن المرحلة',
        compute='_compute_team_id',
        store=True,
        readonly=False,
        domain="[('project_id', '=', project_id)]",
        tracking=True,
        help='فريق العمل المعين لتنفيذ هذه المرحلة ضمن المشروع'
    )
    user_id = fields.Many2one(
        'res.users',
        string='المسؤول عن التنفيذ العام',
        default=lambda self: self.env.user,
        tracking=True
    )
    color = fields.Integer(
        string='رمز اللون البصري',
        default=0,
        help='رمز اللون لتصنيف أمر العمل في عروض الكانبان'
    )

    # Automatic Multi-User Stage Performer Tracking (تسجيل متعدّد للموظفين المشاركين بكل مرحلة تلقائياً)
    stage_1_user_ids = fields.Many2many(
        'res.users',
        'wo_stage_1_user_rel',
        'work_order_id',
        'user_id',
        string='المسؤولون عن الإسناد',
        readonly=True,
        tracking=True,
        help='الموظفون الذين شاركوا في تحديد وإدخال بيانات مرحلة الإسناد'
    )
    stage_2_user_ids = fields.Many2many(
        'res.users',
        'wo_stage_2_user_rel',
        'work_order_id',
        'user_id',
        string='المسؤولون عن الكشفية والتصاريح',
        readonly=True,
        tracking=True,
        help='الموظفون الذين شاركوا في إدخال وتحديث بيانات المعاينة الفنية والتصاريح'
    )
    stage_3_user_ids = fields.Many2many(
        'res.users',
        'wo_stage_3_user_rel',
        'work_order_id',
        'user_id',
        string='المسؤولون عن التنفيذ والتشغيل',
        readonly=True,
        tracking=True,
        help='الموظفون الذين شاركوا في إدخال وتحديث بيانات التنفيذ والأصول والبرمجة'
    )
    stage_4_user_ids = fields.Many2many(
        'res.users',
        'wo_stage_4_user_rel',
        'work_order_id',
        'user_id',
        string='المسؤولون عن الإغلاق والتوثيق',
        readonly=True,
        tracking=True,
        help='الموظفون الذين شاركوا في إدخال وتحديث بيانات نموذج 155 وشهادة الإنجاز'
    )
    stage_5_user_ids = fields.Many2many(
        'res.users',
        'wo_stage_5_user_rel',
        'work_order_id',
        'user_id',
        string='المسؤولون عن الفوترة والتحصيل',
        readonly=True,
        tracking=True,
        help='الموظفون الذين شاركوا في إدخال وتحديث بيانات الفاتورة والتحصيل'
    )

    # Stage Status Badges (علامات حالة وحث إنجاز المراحل المتعاقبة)
    stage_1_status = fields.Selection([
        ('completed', '✔️ مكتملة'),
        ('in_progress', '⚙️ قيد المعالجة الحالية'),
        ('not_started', '✖️ لم تبدأ بعد'),
    ], string='حالة مرحلة الإسناد', compute='_compute_stage_statuses', store=True)

    stage_2_status = fields.Selection([
        ('completed', '✔️ مكتملة'),
        ('in_progress', '⚙️ قيد المعالجة الحالية'),
        ('not_started', '✖️ لم تبدأ بعد'),
    ], string='حالة مرحلة الكشفية', compute='_compute_stage_statuses', store=True)

    stage_3_status = fields.Selection([
        ('completed', '✔️ مكتملة'),
        ('skipped', '🔴 تم التخطي'),
        ('in_progress', '⚙️ قيد المعالجة الحالية'),
        ('not_started', '✖️ لم تبدأ بعد'),
    ], string='حالة مرحلة التنفيذ', compute='_compute_stage_statuses', store=True)

    stage_4_status = fields.Selection([
        ('completed', '✔️ مكتملة'),
        ('in_progress', '⚙️ قيد المعالجة الحالية'),
        ('not_started', '✖️ لم تبدأ بعد'),
    ], string='حالة مرحلة الإغلاق', compute='_compute_stage_statuses', store=True)

    stage_5_status = fields.Selection([
        ('completed', '✔️ مكتملة'),
        ('in_progress', '⚙️ قيد المعالجة الحالية'),
        ('not_started', '✖️ لم تبدأ بعد'),
    ], string='حالة مرحلة الفوترة', compute='_compute_stage_statuses', store=True)

    # Fold & Details Toggle Booleans for all 5 Stages
    show_stage_1_details = fields.Boolean(
        string='عرض تفاصيل مرحلة الإسناد',
        compute='_compute_stage_fold_defaults',
        store=True,
        readonly=False
    )
    show_stage_2_details = fields.Boolean(
        string='عرض تفاصيل مرحلة الكشفية والتصاريح',
        compute='_compute_stage_fold_defaults',
        store=True,
        readonly=False
    )
    show_stage_3_details = fields.Boolean(
        string='عرض تفاصيل مرحلة التنفيذ والتشغيل',
        compute='_compute_stage_fold_defaults',
        store=True,
        readonly=False
    )
    show_stage_4_details = fields.Boolean(
        string='عرض تفاصيل مرحلة الإغلاق والتوثيق',
        compute='_compute_stage_fold_defaults',
        store=True,
        readonly=False
    )
    show_stage_5_details = fields.Boolean(
        string='عرض تفاصيل مرحلة الفوترة والتحصيل',
        compute='_compute_stage_fold_defaults',
        store=True,
        readonly=False
    )

    # Legacy alias for backward compatibility
    show_assignment_details = fields.Boolean(
        related='show_stage_1_details',
        readonly=False
    )
    can_edit_assignment = fields.Boolean(
        string='إمكانية تعديل بيانات الإسناد',
        compute='_compute_can_edit_assignment'
    )

    @api.depends('stage_1_status', 'stage_2_status', 'stage_3_status', 'stage_4_status', 'stage_5_status')
    def _compute_stage_fold_defaults(self):
        for rec in self:
            rec.show_stage_1_details = (rec.stage_1_status != 'completed')
            rec.show_stage_2_details = (rec.stage_2_status != 'completed')
            rec.show_stage_3_details = (rec.stage_3_status != 'completed')
            rec.show_stage_4_details = (rec.stage_4_status != 'completed')
            rec.show_stage_5_details = (rec.stage_5_status != 'completed')

    def action_toggle_stage_1_details(self):
        for rec in self:
            rec.show_stage_1_details = not rec.show_stage_1_details

    def action_toggle_stage_2_details(self):
        for rec in self:
            rec.show_stage_2_details = not rec.show_stage_2_details

    def action_toggle_stage_3_details(self):
        for rec in self:
            rec.show_stage_3_details = not rec.show_stage_3_details

    def action_toggle_stage_4_details(self):
        for rec in self:
            rec.show_stage_4_details = not rec.show_stage_4_details

    def action_toggle_stage_5_details(self):
        for rec in self:
            rec.show_stage_5_details = not rec.show_stage_5_details

    def action_toggle_assignment_details(self):
        return self.action_toggle_stage_1_details()

    def action_open_extend_permit_wizard(self):
        self.ensure_one()
        return {
            'name': _('تمديد تاريخ انتهاء التصريح 🔄'),
            'type': 'ir.actions.act_window',
            'res_model': 'unified.contract.permit.extend.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_work_order_id': self.id,
                'default_new_permit_end_date': fields.Date.context_today(self),
            }
        }

    # 1. Assignment Phase Fields (مرحلة الإسناد)
    region_id = fields.Many2one(
        'unified.contract.region',
        string='المنطقة',
        tracking=True
    )
    district_id = fields.Many2one(
        'unified.contract.district',
        string='الموقع / الحي',
        domain="[('region_id', '=', region_id)]",
        tracking=True
    )
    station_id = fields.Many2one(
        'unified.contract.station',
        string='رقم / اسم المحطة',
        domain="[('district_id', '=', district_id)]",
        tracking=True
    )
    department_id = fields.Many2one(
        'unified.contract.department',
        string='القسم / الإدارة',
        tracking=True
    )
    work_order_type_id = fields.Many2one(
        'unified.contract.work.order.type',
        string='نوع أمر العمل',
        tracking=True
    )
    work_order_category_id = fields.Many2one(
        'unified.contract.work.order.category',
        string='تصنيف أمر العمل',
        tracking=True
    )
    assignment_date = fields.Date(
        string='تاريخ الإسناد',
        default=fields.Date.context_today,
        tracking=True
    )
    elapsed_days = fields.Integer(
        string='المدة المنقضية (أيام)',
        compute='_compute_elapsed_days',
        store=False,
        help='عدد الأيام المنقضية تلقائياً بين تاريخ الإسناد والتاريخ الحالي'
    )
    estimated_amount = fields.Float(
        string='القيمة التقديرية (ر.س)',
        tracking=True
    )
    coordinate_x = fields.Char(
        string='إحداثي X (خط الطول Longitude)',
        tracking=True,
        help='إحداثي X لموقع أمر العمل'
    )
    coordinate_y = fields.Char(
        string='إحداثي Y (خط العرض Latitude)',
        tracking=True,
        help='إحداثي Y لموقع أمر العمل'
    )
    google_maps_url = fields.Char(
        string='رابط موقع أمر العمل (خرائط جوجل)',
        tracking=True,
        help='رابط خرائط جوجل التلقائي المستخرج من الإحداثيات أو المدخل يدوياً'
    )

    @api.model
    def _parse_google_maps_url_coordinates(self, url_text):
        if not url_text:
            return False, False
        url_str = str(url_text).strip()
        url = unquote(url_str)

        # Support shortened Google Maps URLs via HTTP HEAD redirect resolution
        if any(shortener in url_str for shortener in ['goo.gl', 'maps.app.goo.gl', 'page.link']):
            try:
                import urllib.request
                req = urllib.request.Request(url_str, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    resolved_url = resp.geturl()
                    if resolved_url:
                        url = unquote(resolved_url)
            except Exception:
                pass

        patterns = [
            r'@([-+]?\d+(?:\.\d+)?),\s*([-+]?\d+(?:\.\d+)?)',
            r'[?&](?:query|q|ll|destination|near|center)=([-+]?\d+(?:\.\d+)?),\s*([-+]?\d+(?:\.\d+)?)',
            r'/place/(?:[^/]+/)?@?([-+]?\d+(?:\.\d+)?),\s*([-+]?\d+(?:\.\d+)?)',
            r'([-+]?\d{1,2}\.\d+),\s*([-+]?\d{1,3}\.\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), match.group(2)
        return False, False
        url = unquote(str(url_text).strip())
        
        patterns = [
            r'@([-+]?\d+(?:\.\d+)?),\s*([-+]?\d+(?:\.\d+)?)',
            r'[?&](?:query|q|ll|destination|near|center)=([-+]?\d+(?:\.\d+)?),\s*([-+]?\d+(?:\.\d+)?)',
            r'/place/(?:[^/]+/)?@?([-+]?\d+(?:\.\d+)?),\s*([-+]?\d+(?:\.\d+)?)',
            r'([-+]?\d{1,2}\.\d+),\s*([-+]?\d{1,3}\.\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), match.group(2)
        return False, False

    @api.onchange('coordinate_x', 'coordinate_y')
    def _onchange_coordinates_generate_url(self):
        if self.coordinate_x and self.coordinate_y:
            cx = str(self.coordinate_x).strip()
            cy = str(self.coordinate_y).strip()
            if cx and cy:
                self.google_maps_url = f"https://www.google.com/maps/search/?api=1&query={cy},{cx}"

    @api.onchange('google_maps_url')
    def _onchange_google_maps_url_extract_coordinates(self):
        if self.google_maps_url:
            lat, lng = self._parse_google_maps_url_coordinates(self.google_maps_url)
            if lat and lng:
                self.coordinate_y = lat
                self.coordinate_x = lng

    def action_open_google_maps(self):
        self.ensure_one()
        if not self.google_maps_url:
            if self.coordinate_x and self.coordinate_y:
                cx = str(self.coordinate_x).strip()
                cy = str(self.coordinate_y).strip()
                self.google_maps_url = f"https://www.google.com/maps/search/?api=1&query={cy},{cx}"
            else:
                raise UserError(_('عذراً! يرجى إدخال الإحداثيات (X, Y) أو رابط الخريطة أولاً للتمكن من فتح الموقع على خرائط جوجل.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.google_maps_url,
            'target': 'new',
        }

    # 2. Scouting & Permits Phase Fields (الكشفية والتصاريح)
    is_scouting_completed = fields.Selection([
        ('no', 'لا'),
        ('yes', 'نعم'),
    ], string='تمت الكشفية والمعاينة الفنية؟', default='no', required=True, tracking=True)
    has_scouting_obstacles = fields.Selection([
        ('no', 'لا'),
        ('yes', 'نعم'),
    ], string='هل يوجد عوائق كشفية / فنية؟', default='no', required=True, tracking=True)
    scouting_obstacles_notes = fields.Text(
        string='تفاصيل وبيان العوائق'
    )
    permit_number = fields.Char(
        string='رقم التصريح',
        tracking=True,
        help='رقم تصريح العمل الرسمي'
    )
    permit_status_id = fields.Many2one(
        'unified.contract.permit.status',
        string='حالة التصريح',
        default=_get_default_permit_status_id,
        tracking=True
    )
    permit_start_date = fields.Date(
        string='تاريخ بداية التصريح',
        tracking=True
    )
    permit_end_date = fields.Date(
        string='تاريخ انتهاء التصريح',
        tracking=True
    )
    permit_alert_status = fields.Selection([
        ('not_issued', 'لم يصدر ⚪'),
        ('normal', 'ساري / طبيعي 🟢'),
        ('warning', 'تنبيه - متبقي أيام قليلة ⚠️'),
        ('expired', 'منتهي / متأخر 🔴'),
    ], string='حالة تنبيه التصريح', compute='_compute_permit_alert_status', store=True)

    @api.constrains('permit_start_date', 'permit_end_date')
    def _check_permit_dates_order(self):
        for rec in self:
            if rec.permit_start_date and rec.permit_end_date:
                if rec.permit_end_date < rec.permit_start_date:
                    raise ValidationError(_('عذراً! لا يمكن أن يكون تاريخ انتهاء التصريح قبل تاريخ الإصدار/البداية.'))

    def _get_or_create_permit_status(self, code, name):
        status = self.env['unified.contract.permit.status'].search([
            '|', ('code', '=', code), ('name', 'ilike', name)
        ], limit=1)
        if not status:
            status = self.env['unified.contract.permit.status'].create({
                'name': name,
                'code': code,
            })
        return status

    def _sync_permit_status_from_dates(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.permit_end_date and rec.permit_end_date < today:
                expired_status = rec._get_or_create_permit_status('expired', 'منتهي')
                if rec.permit_status_id != expired_status:
                    rec.permit_status_id = expired_status.id
            elif rec.permit_number or rec.permit_end_date:
                valid_status = rec._get_or_create_permit_status('valid', 'ساري')
                if rec.permit_status_id != valid_status:
                    rec.permit_status_id = valid_status.id
            else:
                not_issued_status = rec._get_or_create_permit_status('not_issued', 'لم يصدر')
                if rec.permit_status_id != not_issued_status:
                    rec.permit_status_id = not_issued_status.id

    @api.onchange('permit_number', 'permit_start_date', 'permit_end_date')
    def _onchange_permit_number_update_status(self):
        if self.permit_start_date and self.permit_end_date and self.permit_end_date < self.permit_start_date:
            return {
                'warning': {
                    'title': _('تنبيه - تواريخ غير منطقية'),
                    'message': _('عذراً! لا يمكن أن يكون تاريخ انتهاء التصريح قبل تاريخ الإصدار/البداية.')
                }
            }
        self._sync_permit_status_from_dates()

    work_order_date = fields.Date(
        string='تاريخ إصدار أمر العمل',
        default=fields.Date.context_today,
        tracking=True
    )
    date_start = fields.Date(
        string='تاريخ بداية التنفيذ',
        default=fields.Date.context_today
    )
    date_deadline = fields.Date(
        string='تاريخ التسليم المتوقع',
        tracking=True
    )
    stage_id = fields.Many2one(
        'unified.contract.work.order.stage',
        string='مرحلة أمر العمل',
        default=lambda self: self._default_stage_id(),
        group_expand='_read_group_stage_ids',
        tracking=True
    )
    is_first_stage = fields.Boolean(
        string='المرحلة الأولى',
        compute='_compute_stage_position'
    )
    is_last_stage = fields.Boolean(
        string='المرحلة الأخيرة',
        compute='_compute_stage_position'
    )
    next_stage_name = fields.Char(
        string='اسم المرحلة التالية',
        compute='_compute_stage_names'
    )
    prev_stage_name = fields.Char(
        string='اسم المرحلة السابقة',
        compute='_compute_stage_names'
    )
    state = fields.Selection([
        ('draft', 'جديد / تحت الإعداد'),
        ('in_progress', 'قيد التنفيذ'),
        ('on_hold', 'معلق مؤقتاً'),
        ('late', 'متأخر عن الجدول الزمنـي'),
        ('done', 'منتهي / مكتمل'),
        ('cancel', 'ملغـى'),
    ], string='حالة أمر العمل', default='draft', compute='_compute_state_automatically', store=True, readonly=False, tracking=True)

    progress = fields.Float(
        string='نسبة الإنجاز (%)',
        compute='_compute_overall_progress',
        store=True,
        tracking=True,
        help='نسبة الإنجاز التراكمية لأمر العمل تكتمل بنهاية كل مرحلة عدا مرحلة التنفيذ تتأثر بنسبتها الداخلية'
    )
    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        related='project_id.company_id',
        store=True,
        readonly=True
    )
    description = fields.Html(
        string='تفاصيل وتوجيهات أمر العمل'
    )

    # 3. Execution Phase Fields (مرحلة التنفيذ والتشغيل)
    execution_start_date = fields.Date(
        string='تاريخ بداية التنفيذ',
        default=fields.Date.context_today,
        tracking=True
    )
    execution_end_date = fields.Date(
        string='تاريخ الانتهاء',
        tracking=True
    )
    excavation_quantity = fields.Float(
        string='كميات حفر (م/م³)',
        default=0.0,
        tracking=True
    )
    extension_quantity = fields.Float(
        string='كميات تمديد (م)',
        default=0.0,
        tracking=True
    )
    equipment_count = fields.Integer(
        string='معدات (عدد)',
        default=0,
        tracking=True
    )
    execution_progress = fields.Float(
        string='نسبة إنجاز التنفيذ (%)',
        default=0.0,
        tracking=True
    )
    execution_status = fields.Selection([
        ('not_started', 'لم يبدأ التنفيذ ⚪'),
        ('in_progress', 'جاري التنفيذ ⚙️'),
        ('completed', 'تم التنفيذ بالكامل ✔️'),
        ('skipped', 'تم التخطي 🔴'),
    ], string='حالة التنفيذ', compute='_compute_execution_status', store=True)

    is_execution_skipped = fields.Boolean(
        string='تم تخطي التنفيذ',
        default=False,
        tracking=True
    )

    restoration_status = fields.Selection([
        ('no', 'لا'),
        ('yes', 'نعم'),
    ], string='إعادة الوضع؟', default='no', required=True, tracking=True)

    asset_receipt_207 = fields.Selection([
        ('no', 'لا'),
        ('yes', 'نعم'),
    ], string='استلام الأصول (إجراء 207)', default='no', required=True, tracking=True)

    asset_receipt_207_date = fields.Date(
        string='تاريخ إجراء 207',
        tracking=True,
        help='تاريخ تنفيذ إجراء استلام الأصول 207'
    )

    asset_receipt_201 = fields.Selection([
        ('no', 'لا'),
        ('yes', 'نعم'),
    ], string='استلام الأصول (إجراء 201)', default='no', required=True, tracking=True)

    asset_receipt_201_date = fields.Date(
        string='تاريخ إجراء 201',
        tracking=True,
        help='تاريخ تنفيذ إجراء استلام الأصول 201'
    )

    programming_date = fields.Date(
        string='تاريخ البرنامج',
        tracking=True
    )
    programming_alert_status = fields.Selection([
        ('not_scheduled', 'غير مجدول ⚪'),
        ('scheduled', 'مجدول 🟢'),
        ('warning', 'مجدول - تنبيه متبقي أيام ⚠️'),
        ('expired', 'مجدول - متأخر / منتهي 🔴'),
        ('executed', 'تم التنفيذ 🟢'),
    ], string='تنبيه تاريخ البرنامج', compute='_compute_programming_alert_status', store=True)

    completion_certificate_status = fields.Selection([
        ('no', 'لا'),
        ('yes', 'نعم'),
    ], string='شهادة الإتمام؟', default='no', required=True, tracking=True)

    @api.onchange('asset_receipt_207')
    def _onchange_asset_receipt_207_set_date(self):
        if self.asset_receipt_207 == 'yes' and not self.asset_receipt_207_date:
            self.asset_receipt_207_date = fields.Date.context_today(self)

    @api.onchange('asset_receipt_201')
    def _onchange_asset_receipt_201_set_date(self):
        if self.asset_receipt_201 == 'yes' and not self.asset_receipt_201_date:
            self.asset_receipt_201_date = fields.Date.context_today(self)

    @api.onchange('completion_certificate_status')
    def _onchange_completion_certificate_status_update_alert(self):
        if self.completion_certificate_status == 'yes':
            if not self.completion_certificate_date:
                self.completion_certificate_date = fields.Date.context_today(self)
            self.programming_alert_status = 'executed'
            if self.id:
                notifications = self.env['unified.contract.notification'].search([
                    ('work_order_id', '=', self.id),
                    ('notification_type', '=', 'programming_alert'),
                    ('is_read', '=', False)
                ])
                notifications.write({'is_read': True})

    asset_details = fields.Text(
        string='الأصول والمعدات المستخدمة',
        help='سجل تفاصيل الأصول والمعدات الفنية المسندة لأمر العمل'
    )
    programming_notes = fields.Text(
        string='ملاحظات البرنامج',
        help='ملاحظات وإعدادات البرمجة الفنية'
    )
    operation_status = fields.Selection([
        ('not_started', 'لم يبدأ التشغيل'),
        ('testing', 'قيد الاختبار والتشغيل التجريبي'),
        ('operational', 'يعمل بكفاءة وتشغيل كلي'),
    ], string='حالة التشغيل والاختبار', default='not_started', tracking=True)

    # 4. Closing Phase Fields (مرفقات - استلام 155 - شهادة الإنجاز)
    receipt_155_number = fields.Char(
        string='رقم نموذج استلام 155',
        tracking=True,
        help='الرقم المرجعي لنموذج استلام 155 الرسمي'
    )
    receipt_155_date = fields.Date(
        string='تاريخ نموذج استلام 155',
        tracking=True
    )
    completion_certificate_no = fields.Char(
        string='رقم شهادة الإنجاز الرسمية',
        tracking=True,
        help='رقم شهادة الإنجاز المعتمدة من الجهة المالكة'
    )
    completion_certificate_date = fields.Date(
        string='تاريخ شهادة الإنجاز',
        tracking=True
    )
    closing_attachment_ids = fields.Many2many(
        'ir.attachment',
        string='مرفقات ومستندات الإغلاق',
        help='مستندات استلام 155 وشهادات الإنجاز والمرفقات الفنية'
    )

    # 5. Invoicing & Collection Phase Fields (الفوترة والتحصيل)
    invoice_number = fields.Char(
        string='رقم الفاتورة الصادرة',
        tracking=True
    )
    invoice_amount = fields.Float(
        string='المبلغ المفوتر',
        tracking=True
    )
    payment_status = fields.Selection([
        ('unpaid', 'غير محصل'),
        ('partially_paid', 'تحصيل جزئي'),
        ('paid', 'تم التحصيل بالكامل'),
    ], string='حالة التحصيل', default='unpaid', tracking=True)

    @api.depends('stage_id', 'date_deadline')
    def _compute_state_automatically(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state in ('done', 'cancel', 'on_hold'):
                continue
            if rec.date_deadline and rec.date_deadline < today:
                rec.state = 'late'
            else:
                if rec.is_first_stage:
                    rec.state = 'draft'
                else:
                    rec.state = 'in_progress'

    @api.depends('stage_id', 'state', 'execution_progress', 'is_execution_skipped')
    def _compute_stage_statuses(self):
        for rec in self:
            current_seq = rec.stage_id.sequence if rec.stage_id else 1
            is_done = rec.state == 'done'

            # Stage 1: Assignment
            if is_done or current_seq > 1:
                rec.stage_1_status = 'completed'
            elif current_seq == 1:
                rec.stage_1_status = 'in_progress'
            else:
                rec.stage_1_status = 'not_started'

            # Stage 2: Scouting & Permits
            if is_done or current_seq > 2:
                rec.stage_2_status = 'completed'
            elif current_seq == 2:
                rec.stage_2_status = 'in_progress'
            else:
                rec.stage_2_status = 'not_started'

            # Stage 3: Execution
            if rec.is_execution_skipped and rec.execution_progress < 100.0:
                rec.stage_3_status = 'skipped'
            elif is_done or current_seq > 3:
                rec.stage_3_status = 'completed'
            elif current_seq == 3:
                rec.stage_3_status = 'in_progress'
            else:
                rec.stage_3_status = 'not_started'

            # Stage 4: Closing
            if is_done or current_seq > 4:
                rec.stage_4_status = 'completed'
            elif current_seq == 4:
                rec.stage_4_status = 'in_progress'
            else:
                rec.stage_4_status = 'not_started'

            # Stage 5: Invoicing
            if is_done:
                rec.stage_5_status = 'completed'
            elif current_seq == 5:
                rec.stage_5_status = 'in_progress'
            else:
                rec.stage_5_status = 'not_started'

    @api.depends('stage_id', 'project_id')
    def _compute_can_edit_assignment(self):
        user = self.env.user
        is_admin = self.env.is_admin()
        non_admin_recs = [r for r in self if not (is_admin or r.is_first_stage)]
        teams_map = {}
        if non_admin_recs:
            proj_ids = list(set(r.project_id.id for r in non_admin_recs if r.project_id))
            if proj_ids:
                assignment_teams = self.env['unified.contract.team'].search([
                    ('project_id', 'in', proj_ids),
                    ('work_order_stage_id.sequence', '=', 1)
                ])
                for t in assignment_teams:
                    teams_map[t.project_id.id] = t

        for rec in self:
            if is_admin or rec.is_first_stage:
                rec.can_edit_assignment = True
            else:
                assignment_team = teams_map.get(rec.project_id.id)
                if assignment_team and (user.id == assignment_team.leader_id.id or user.id in assignment_team.member_ids.ids):
                    rec.can_edit_assignment = True
                else:
                    rec.can_edit_assignment = False

    @api.depends('permit_end_date', 'permit_number', 'permit_status_id', 'state')
    def _compute_permit_alert_status(self):
        today = fields.Date.context_today(self)
        alert_config = self.env['unified.contract.alert.setting'].sudo().get_config()
        alert_days = alert_config.permit_alert_days_before or 1

        for rec in self:
            is_not_issued_status = not rec.permit_status_id or 'لم يصدر' in (rec.permit_status_id.name or '') or getattr(rec.permit_status_id, 'code', '') == 'not_issued'

            # If permit_number and permit_end_date are provided, permit status is active/issued!
            if rec.permit_number and rec.permit_end_date and is_not_issued_status:
                is_not_issued_status = False

            if not rec.permit_number or not rec.permit_end_date or is_not_issued_status:
                rec.permit_alert_status = 'not_issued'
                if rec.color in (1, 3):
                    rec.color = 0
                continue

            if rec.state in ('done', 'cancel'):
                rec.permit_alert_status = 'normal'
                continue

            delta = (rec.permit_end_date - today).days
            if delta < 0:
                rec.permit_alert_status = 'expired'
                rec.color = 1
            elif delta <= alert_days:
                rec.permit_alert_status = 'warning'
                rec.color = 3
            else:
                rec.permit_alert_status = 'normal'
                if rec.color in (1, 3):
                    rec.color = 0

    @api.depends('execution_progress', 'is_execution_skipped', 'stage_id')
    def _compute_execution_status(self):
        for rec in self:
            if rec.stage_id and rec.stage_id.sequence <= 3:
                rec.is_execution_skipped = False

            if rec.is_execution_skipped and rec.execution_progress < 100.0:
                rec.execution_status = 'skipped'
            elif rec.execution_progress <= 0.0:
                rec.execution_status = 'not_started'
            elif rec.execution_progress >= 100.0:
                rec.execution_status = 'completed'
                rec.restoration_status = 'yes'
                rec.is_execution_skipped = False
            else:
                rec.execution_status = 'in_progress'

    @api.constrains('execution_progress')
    def _check_execution_progress_max(self):
        for rec in self:
            if rec.execution_progress < 0.0 or rec.execution_progress > 100.0:
                raise ValidationError(_('عذراً! الحد الأقصى المسموح به لنسبة إنجاز التنفيذ هو 100%. يرجى إدخال قيمة بين 0% و 100%.'))

    @api.constrains('execution_start_date', 'execution_end_date')
    def _check_execution_dates_order(self):
        for rec in self:
            if rec.execution_start_date and rec.execution_end_date:
                if rec.execution_end_date < rec.execution_start_date:
                    raise ValidationError(_('عذراً! يجب أن يكون تاريخ الانتهاء أكبر من أو يساوي تاريخ بداية التنفيذ.'))

    @api.onchange('execution_start_date', 'execution_end_date')
    def _onchange_execution_dates_check(self):
        if self.execution_start_date and self.execution_end_date:
            if self.execution_end_date < self.execution_start_date:
                return {
                    'warning': {
                        'title': _('تنبيه - تاريخ غير صالح'),
                        'message': _('عذراً! يجب أن يكون تاريخ الانتهاء أكبر من أو يساوي تاريخ بداية التنفيذ.')
                    }
                }

    @api.depends('stage_id', 'stage_id.sequence', 'stage_id.stage_progress', 'execution_progress', 'state')
    def _compute_overall_progress(self):
        all_stages = self.env['unified.contract.work.order.stage'].search([], order='sequence asc, id asc')
        for rec in self:
            if rec.state == 'done':
                rec.progress = 100.0
                continue
            if not rec.stage_id or not all_stages:
                rec.progress = 0.0
                continue
                
            current_seq = rec.stage_id.sequence
            prev_stages = [s for s in all_stages if s.sequence < current_seq]
            base_progress = prev_stages[-1].stage_progress if prev_stages else 0.0
            
            is_execution_stage = bool(
                (rec.stage_id.name and 'تنفيذ' in rec.stage_id.name) or 
                (rec.stage_id.sequence == 3)
            )
            
            if is_execution_stage:
                current_target = rec.stage_id.stage_progress
                stage_weight = max(current_target - base_progress, 0.0)
                exec_pct = max(min(rec.execution_progress or 0.0, 100.0), 0.0)
                rec.progress = round(base_progress + (exec_pct / 100.0) * stage_weight, 2)
            else:
                rec.progress = round(base_progress, 2)

    @api.onchange('execution_progress', 'stage_id')
    def _onchange_execution_progress_update_overall_progress(self):
        if self.execution_progress and self.execution_progress >= 100.0:
            self.restoration_status = 'yes'
        self._compute_overall_progress()

    @api.depends('programming_date', 'completion_certificate_status', 'state')
    def _compute_programming_alert_status(self):
        today = fields.Date.context_today(self)
        alert_config = self.env['unified.contract.alert.setting'].sudo().get_config()
        alert_days = alert_config.programming_alert_days_before or 3

        for rec in self:
            if rec.completion_certificate_status == 'yes':
                rec.programming_alert_status = 'executed'
                continue
            if not rec.programming_date:
                rec.programming_alert_status = 'not_scheduled'
                continue
            if rec.state in ('done', 'cancel'):
                rec.programming_alert_status = 'executed'
                continue

            delta = (rec.programming_date - today).days
            if delta < 0:
                rec.programming_alert_status = 'expired'
            elif delta <= alert_days:
                rec.programming_alert_status = 'warning'
            else:
                rec.programming_alert_status = 'scheduled'

    @api.depends('project_id', 'stage_id')
    def _compute_team_id(self):
        projects = self.mapped('project_id')
        teams_by_project = {}
        if projects:
            all_teams = self.env['unified.contract.team'].search([
                ('project_id', 'in', projects.ids)
            ])
            for team in all_teams:
                pid = team.project_id.id
                if pid not in teams_by_project:
                    teams_by_project[pid] = []
                teams_by_project[pid].append(team)

        for rec in self:
            if rec.project_id and rec.stage_id:
                proj_teams = teams_by_project.get(rec.project_id.id, [])
                team = next((t for t in proj_teams if t.work_order_stage_id and t.work_order_stage_id.id == rec.stage_id.id), None)
                if not team and rec.stage_id.name:
                    team = next((t for t in proj_teams if (t.stage_id and t.stage_id.name == rec.stage_id.name) or (t.name and rec.stage_id.name in t.name)), None)
                
                if team:
                    rec.team_id = team.id
                    if team.leader_id:
                        rec.user_id = team.leader_id.id

    @api.onchange('team_id')
    def _onchange_team_id(self):
        if self.team_id and self.team_id.leader_id:
            self.user_id = self.team_id.leader_id

    @api.constrains('work_order_number')
    def _check_work_order_number_config(self):
        alert_config = self.env['unified.contract.alert.setting'].sudo().get_config()
        numeric_only = alert_config.wo_number_numeric_only
        enforce_unique = alert_config.wo_number_unique
        required_length = alert_config.wo_number_length or 12

        for rec in self:
            if not rec.work_order_number:
                continue
            val = str(rec.work_order_number).strip()
            
            if numeric_only and not val.isdigit():
                raise ValidationError(_('عذراً! حسب إعدادات إدارة التنبيهات، يجب أن يتكون رقم أمر العمل من أرقام فقط.'))
                
            if required_length > 0 and len(val) != required_length:
                raise ValidationError(_('عذراً! حسب إعدادات إدارة التنبيهات، يجب أن يتكون رقم أمر العمل من (%s) رقم/خانة بالضبط. (الطول المدخل: %s خانة).') % (required_length, len(val)))
                
            if enforce_unique:
                existing = self.search([
                    ('work_order_number', '=', val),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    target_display = existing.work_order_number or existing.name or ''
                    raise ValidationError(_('عذراً! رقم أمر العمل (%s) مستخدم مسبقاً في أمر العمل رقم (%s). إعدادات إدارة التنبيهات تشترط عدم التكرار.') % (val, target_display))

    @api.constrains('permit_number')
    def _check_permit_number_config(self):
        alert_config = self.env['unified.contract.alert.setting'].sudo().get_config()
        numeric_only = alert_config.permit_number_numeric_only
        enforce_unique = alert_config.permit_number_unique
        required_length = alert_config.permit_number_length or 0

        for rec in self:
            if not rec.permit_number:
                continue
            val = str(rec.permit_number).strip()
            
            if numeric_only and not val.isdigit():
                raise ValidationError(_('عذراً! حسب إعدادات إدارة التنبيهات، يجب أن يتكون رقم التصريح من أرقام فقط.'))
                
            if required_length > 0 and len(val) != required_length:
                raise ValidationError(_('عذراً! حسب إعدادات إدارة التنبيهات، يجب أن يتكون رقم التصريح من (%s) رقم/خانة بالضبط. (الطول المدخل: %s خانة).') % (required_length, len(val)))
                
            if enforce_unique:
                existing = self.search([
                    ('permit_number', '=', val),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    target_display = existing.work_order_number or existing.name or ''
                    raise ValidationError(_('عذراً! رقم التصريح (%s) مستخدم مسبقاً في أمر العمل رقم (%s). إعدادات إدارة التنبيهات تشترط عدم تكرار رقم التصريح.') % (val, target_display))

    @api.depends('assignment_date')
    def _compute_elapsed_days(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.assignment_date:
                delta = (today - rec.assignment_date).days
                rec.elapsed_days = max(delta, 0)
            else:
                rec.elapsed_days = 0

    @api.onchange('region_id')
    def _onchange_region_id(self):
        if self.district_id and self.district_id.region_id != self.region_id:
            self.district_id = False
            self.station_id = False

    @api.onchange('district_id')
    def _onchange_district_id(self):
        if self.station_id and self.station_id.district_id != self.district_id:
            self.station_id = False

    @api.depends('stage_id')
    def _compute_stage_position(self):
        all_stages = self.env['unified.contract.work.order.stage'].search([], order='sequence asc, id asc')
        first_id = all_stages[0].id if all_stages else False
        last_id = all_stages[-1].id if all_stages else False
        for record in self:
            record.is_first_stage = bool(record.stage_id and record.stage_id.id == first_id)
            record.is_last_stage = bool(record.stage_id and record.stage_id.id == last_id)

    @api.depends('stage_id')
    def _compute_stage_names(self):
        all_stages = self.env['unified.contract.work.order.stage'].search([], order='sequence asc, id asc')
        for rec in self:
            current_seq = rec.stage_id.sequence if rec.stage_id else -1
            next_stages = [s for s in all_stages if s.sequence > current_seq]
            prev_stages = [s for s in all_stages if s.sequence < current_seq]
            
            if next_stages:
                rec.next_stage_name = f"الانتقال إلى: {next_stages[0].name} ➡️"
            else:
                rec.next_stage_name = "المرحلة التالية ➡️"
                
            if prev_stages:
                rec.prev_stage_name = f"إرجاع لمرحلة سابقة ⬅️"
            else:
                rec.prev_stage_name = "إرجاع لمرحلة سابقة ⬅️"

    @api.onchange('stage_id')
    def _onchange_stage_id_update_state_and_progress(self):
        if self.stage_id:
            self._compute_overall_progress()
            all_stages = self.env['unified.contract.work.order.stage'].search([], order='sequence asc, id asc')
            first_id = all_stages[0].id if all_stages else False
            if self.stage_id.id == first_id:
                self.state = 'draft'
            elif self.state == 'draft':
                self.state = 'in_progress'
            if not self.permit_status_id:
                self.permit_status_id = self._get_default_permit_status_id()

    @api.model
    def _default_stage_id(self):
        return self.env['unified.contract.work.order.stage'].search([], limit=1)

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        return self.env['unified.contract.work.order.stage'].search([])

    def _check_revert_stage_permission(self):
        if self.env.is_admin():
            return True
        user_profiles = self.env['unified.contract.permission.profile'].search([
            ('user_ids', 'in', [self.env.user.id]),
            ('can_revert_stage', '=', True)
        ])
        if not user_profiles:
            raise UserError(_('عذراً! ليس لديك صلاحية لإرجاع مرحلة أمر العمل إلى مرحلة سابقة. يتطلب ذلك تفعيل خيار (السماح بإرجاع المراحل للسابقة) في بروفايل الصلاحيات الخاص بك.'))
        return True

    def _is_execution_stage(self, stage):
        return bool(stage and (('تنفيذ' in (stage.name or '')) or stage.sequence == 3))

    def _is_closure_or_later_stage(self, stage):
        return bool(stage and (('إغلاق' in (stage.name or '')) or stage.sequence >= 4))

    def _get_skip_execution_wizard_action(self, target_stage=None):
        self.ensure_one()
        if not target_stage or target_stage.sequence <= self.stage_id.sequence:
            target_stage = self.env['unified.contract.work.order.stage'].search([
                ('sequence', '>', self.stage_id.sequence)
            ], order='sequence asc', limit=1)
        view = self.env.ref('ao_unified_contract_project.view_unified_contract_skip_execution_wizard_form_v5')
        return {
            'name': _('تنبيه - التنفيذ غير مكتمل'),
            'type': 'ir.actions.act_window',
            'res_model': 'unified.contract.skip.execution.wizard',
            'view_mode': 'form',
            'view_id': view.id,
            'views': [(view.id, 'form')],
            'target': 'new',
            'context': {
                'default_work_order_id': self.id,
            }
        }

    def action_next_stage(self):
        for rec in self:
            current_seq = rec.stage_id.sequence if rec.stage_id else -1
            next_stage = self.env['unified.contract.work.order.stage'].search([
                ('sequence', '>', current_seq)
            ], order='sequence asc', limit=1)
            if next_stage:
                if rec._is_execution_stage(rec.stage_id) and rec._is_closure_or_later_stage(next_stage):
                    if rec.execution_progress < 100.0 and not self.env.context.get('skip_execution_check'):
                        return rec._get_skip_execution_wizard_action(next_stage)

                rec.stage_id = next_stage.id
                if rec.state == 'draft':
                    rec.state = 'in_progress'
                if not rec.permit_status_id:
                    rec.permit_status_id = rec._get_default_permit_status_id()
                rec._compute_team_id()
                rec._compute_overall_progress()

    def action_open_revert_wizard(self):
        self.ensure_one()
        self._check_revert_stage_permission()
        
        all_stages = self.env['unified.contract.work.order.stage'].search([
            ('sequence', '<', self.stage_id.sequence if self.stage_id else 999999)
        ], order='sequence desc')
        
        if not all_stages:
            raise UserError(_('أمر العمل في المرحلة الأولى بالفعل، لا توجد مراحل سابقة للإرجاع إليها.'))
            
        return {
            'name': _('إرجاع أمر العمل لمرحلة سابقة'),
            'type': 'ir.actions.act_window',
            'res_model': 'unified.contract.stage.revert.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'unified.contract.work.order',
                'default_res_id': self.id,
                'default_stage_id': all_stages[0].id,
                'previous_stage_ids': all_stages.ids,
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        first_stage = self.env['unified.contract.work.order.stage'].search([], order='sequence asc, id asc', limit=1)
        default_permit_status = self._get_default_permit_status_id()
        issued_permit_status = self.env['unified.contract.permit.status'].search([
            '|', ('name', 'ilike', 'ساري'), ('name', 'ilike', 'معتمد')
        ], limit=1)
        current_user_id = self.env.user.id

        for vals in vals_list:
            self._sync_coordinates_and_maps_url(vals)
            if not vals.get('name') and vals.get('work_order_number'):
                vals['name'] = vals['work_order_number']
            if not vals.get('stage_id') and first_stage:
                vals['stage_id'] = first_stage.id
            if vals.get('stage_id') and first_stage and vals['stage_id'] == first_stage.id:
                vals['state'] = 'draft'

            # Automatic permit status update upon permit data entry
            if vals.get('permit_number') and vals.get('permit_end_date') and issued_permit_status:
                vals['permit_status_id'] = issued_permit_status.id
            elif not vals.get('permit_status_id'):
                vals['permit_status_id'] = default_permit_status

            # Strictly force default 'no' for scouting fields unless explicitly set to 'yes'
            if vals.get('is_scouting_completed') != 'yes':
                vals['is_scouting_completed'] = 'no'
            if vals.get('has_scouting_obstacles') != 'yes':
                vals['has_scouting_obstacles'] = 'no'

            # Auto-assign current user into Stage 1 performer list
            if 'stage_1_user_ids' not in vals:
                vals['stage_1_user_ids'] = [(4, current_user_id)]

        records = super(UnifiedContractWorkOrder, self).create(vals_list)
        for rec in records:
            rec._compute_team_id()
            rec._compute_overall_progress()
        return records

    def _sync_coordinates_and_maps_url(self, vals):
        url = vals.get('google_maps_url')
        if url and isinstance(url, str):
            lat, lng = self._parse_google_maps_url_coordinates(url)
            if lat and lng:
                if 'coordinate_y' not in vals:
                    vals['coordinate_y'] = lat
                if 'coordinate_x' not in vals:
                    vals['coordinate_x'] = lng
        elif (vals.get('coordinate_x') or vals.get('coordinate_y')) and not vals.get('google_maps_url'):
            cx = str(vals.get('coordinate_x', '')).strip()
            cy = str(vals.get('coordinate_y', '')).strip()
            if cx and cy:
                vals['google_maps_url'] = f"https://www.google.com/maps/search/?api=1&query={cy},{cx}"

    def write(self, vals):
        self._sync_coordinates_and_maps_url(vals)
        if 'work_order_number' in vals and not vals.get('name'):
            vals['name'] = vals['work_order_number']
        if 'stage_id' in vals and not self.env.context.get('skip_stage_permission_check'):
            new_stage = self.env['unified.contract.work.order.stage'].browse(vals['stage_id'])
            for rec in self:
                if rec.stage_id and new_stage and new_stage.sequence < rec.stage_id.sequence:
                    rec._check_revert_stage_permission()
                if not self.env.context.get('skip_execution_check') and rec._is_execution_stage(rec.stage_id) and rec._is_closure_or_later_stage(new_stage):
                    if rec.execution_progress < 100.0:
                        raise ValidationError(_('عذراً! لا يمكن نقل أمر العمل لمرحلة الإغلاق لأن نسبة إنجاز التنفيذ أقل من 100%. يرجى استخدام زر (الانتقال للمرحلة التالية) أو إكمال نسبة التنفيذ 100% أولاً.'))

        # Automatic Permit Status Update upon entry of permit number and permit end date
        issued_permit_status = self.env['unified.contract.permit.status'].search([
            '|', ('name', 'ilike', 'ساري'), ('name', 'ilike', 'معتمد')
        ], limit=1)

        # Multi-User Automatic Stage Performer Tracking logic
        current_user_id = self.env.user.id
        stage_1_fields = {'project_id', 'contractor_id', 'region_id', 'district_id', 'station_id', 'department_id', 'work_order_type_id', 'work_order_category_id', 'assignment_date', 'estimated_amount', 'team_id', 'coordinate_x', 'coordinate_y'}
        stage_2_fields = {'is_scouting_completed', 'has_scouting_obstacles', 'scouting_obstacles_notes', 'permit_status_id', 'permit_number', 'permit_start_date', 'permit_end_date'}
        stage_3_fields = {'execution_start_date', 'execution_end_date', 'excavation_quantity', 'extension_quantity', 'equipment_count', 'execution_progress', 'restoration_status', 'asset_receipt_207', 'asset_receipt_207_date', 'asset_receipt_201', 'asset_receipt_201_date', 'programming_date', 'completion_certificate_status', 'asset_details', 'programming_notes', 'operation_status'}
        stage_4_fields = {'receipt_155_number', 'receipt_155_date', 'completion_certificate_no', 'completion_certificate_date', 'closing_attachment_ids'}
        stage_5_fields = {'invoice_number', 'invoice_amount', 'payment_status'}

        res = super(UnifiedContractWorkOrder, self).write(vals)

        for rec in self:
            if any(f in vals for f in ('permit_number', 'permit_start_date', 'permit_end_date')):
                rec._sync_permit_status_from_dates()

            if vals.get('completion_certificate_status') == 'yes':
                notifications = self.env['unified.contract.notification'].search([
                    ('work_order_id', '=', rec.id),
                    ('notification_type', '=', 'programming_alert'),
                    ('is_read', '=', False)
                ])
                if notifications:
                    notifications.write({'is_read': True})

            if any(f in vals for f in stage_1_fields) and current_user_id not in rec.stage_1_user_ids.ids:
                rec.write({'stage_1_user_ids': [(4, current_user_id)]})
            if any(f in vals for f in stage_2_fields) and current_user_id not in rec.stage_2_user_ids.ids:
                rec.write({'stage_2_user_ids': [(4, current_user_id)]})
            if any(f in vals for f in stage_3_fields) and current_user_id not in rec.stage_3_user_ids.ids:
                rec.write({'stage_3_user_ids': [(4, current_user_id)]})
            if any(f in vals for f in stage_4_fields) and current_user_id not in rec.stage_4_user_ids.ids:
                rec.write({'stage_4_user_ids': [(4, current_user_id)]})
            if any(f in vals for f in stage_5_fields) and current_user_id not in rec.stage_5_user_ids.ids:
                rec.write({'stage_5_user_ids': [(4, current_user_id)]})

        if 'stage_id' in vals:
            for rec in self:
                if rec.stage_id:
                    rec.progress = rec.stage_id.stage_progress
                if rec.is_first_stage and rec.state not in ('cancel', 'on_hold', 'done'):
                    rec.state = 'draft'
                elif not rec.is_first_stage and rec.state == 'draft':
                    rec.state = 'in_progress'
                if not rec.permit_status_id:
                    rec.permit_status_id = rec._get_default_permit_status_id()
                rec._compute_team_id()
        return res

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_set_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_set_on_hold(self):
        self.write({'state': 'on_hold'})

    def action_set_late(self):
        self.write({'state': 'late'})

    def action_set_done(self):
        self.write({'state': 'done', 'progress': 100.0})

    def action_set_cancel(self):
        self.write({'state': 'cancel'})

    def action_reactivate(self):
        """ Reactivate a cancelled work order back to in_progress """
        self.write({'state': 'in_progress'})
