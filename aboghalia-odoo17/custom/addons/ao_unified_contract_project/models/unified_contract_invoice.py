# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class UnifiedContractInvoice(models.Model):
    _name = 'unified.contract.invoice'
    _description = 'فواتير العقود الموحدة'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='رقم طلب الفاتورة',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('جديد'),
        tracking=True
    )
    work_order_id = fields.Many2one(
        'unified.contract.work.order',
        string='أمر العمل المرتبط',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    project_id = fields.Many2one(
        'unified.contract.project',
        string='المشروع',
        related='work_order_id.project_id',
        store=True,
        readonly=True
    )
    contractor_id = fields.Many2one(
        'res.partner',
        string='المقاول المنفذ',
        related='work_order_id.contractor_id',
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        related='work_order_id.company_id',
        store=True,
        readonly=True
    )

    # 1. رقم المستخلص - رقم الخدمة (يقبل نصوص وأرقام ولا يقبل التكرار)
    extract_service_number = fields.Char(
        string='رقم المستخلص - رقم الخدمة',
        required=True,
        index=True,
        tracking=True,
        help='رقم المستخلص أو رقم الخدمة (يقبل أرقام ونصوص وفريد لا يتكرر)'
    )

    # 2. المبالغ والضرائب
    amount_before_tax = fields.Float(
        string='القيمة قبل الضريبة',
        digits=(16, 2),
        required=True,
        tracking=True,
        help='إدخال يدوي للقيمة قبل الضريبة (يقبل الكسور)'
    )
    tax_amount = fields.Float(
        string='مبلغ الضريبة (15%)',
        compute='_compute_amounts',
        store=True,
        digits=(16, 2),
        help='مبلغ ضريبة القيمة المضافة 15% محسبوب تلقائياً'
    )
    amount_total = fields.Float(
        string='القيمة شامل الضريبة',
        compute='_compute_amounts',
        store=True,
        digits=(16, 2),
        help='القيمة الإجمالية شاملة الضريبة محسبة تلقائياً'
    )

    # 3. إدخالات فريق المالية (عند إصدار الفاتورة وتأكيدها)
    invoice_number = fields.Char(
        string='رقم الفاتورة الصادرة',
        tracking=True,
        help='رقم الفاتورة الصادرة من الإدارة المالية'
    )
    invoice_date = fields.Date(
        string='تاريخ الفاتورة',
        tracking=True
    )
    upload_date = fields.Date(
        string='تاريخ الرفع على النظام',
        tracking=True,
        help='تاريخ تأكيد ورفع الفاتورة على النظام المالي'
    )
    invoice_attachment_ids = fields.Many2many(
        'ir.attachment',
        'unified_contract_invoice_attachment_rel',
        'invoice_id', 'attachment_id',
        string='مرفقات الفاتورة',
        help='ملفات ومرفقات الفاتورة الصادرة المرفوعة من فريق المالية'
    )
    notes = fields.Text(
        string='ملاحظات وتوجيهات المالية'
    )

    # 4. حالة الفاتورة (إصدار فاتورة - الرفع على النظام - متأخر - محصل - طلب تصحيح)
    state = fields.Selection([
        ('draft', 'بانتظار إصدار الفاتورة ⏳'),
        ('uploaded', 'تم الرفع على النظام 🚀'),
        ('late', 'متأخر ⚠️'),
        ('paid', 'محصل ✅'),
        ('correction_requested', 'طلب تصحيح / تعديل 📝'),
        ('cancel', 'ملغي ❌')
    ], string='حالة الفاتورة', default='draft', required=True, tracking=True)

    _sql_constraints = [
        ('extract_service_number_unique', 'unique(extract_service_number)', 'عذراً! رقم المستخلص - رقم الخدمة مُدخل مسبقاً ولا يمكن تكراره نهائياً!')
    ]

    @api.constrains('extract_service_number')
    def _check_extract_service_number_unique(self):
        extract_nums = [r.extract_service_number for r in self if r.extract_service_number]
        if not extract_nums:
            return
        duplicates = self.search([
            ('extract_service_number', 'in', extract_nums),
            ('id', 'not in', self.ids)
        ])
        if duplicates:
            dup_map = {d.extract_service_number: d.name for d in duplicates}
            for rec in self:
                if rec.extract_service_number in dup_map:
                    raise ValidationError(_('عذراً! رقم المستخلص - رقم الخدمة (%s) مُدخل مسبقاً في طلب الفاتورة رقم (%s) ولا يمكن تكراره!') % (rec.extract_service_number, dup_map[rec.extract_service_number]))

    @api.depends('amount_before_tax')
    def _compute_amounts(self):
        for rec in self:
            amt = rec.amount_before_tax or 0.0
            rec.tax_amount = round(amt * 0.15, 2)
            rec.amount_total = round(amt * 1.15, 2)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            wo_id = vals.get('work_order_id')
            if wo_id:
                wo = self.env['unified.contract.work.order'].browse(wo_id)
                if wo and wo.work_order_number:
                    vals['name'] = wo.work_order_number
            if not vals.get('name') or vals.get('name') == _('جديد'):
                vals['name'] = self.env['ir.sequence'].next_by_code('unified.contract.invoice') or _('جديد')
        records = super().create(vals_list)
        for rec in records:
            rec._sync_to_work_order()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.work_order_id and rec.work_order_id.work_order_number:
                if rec.name != rec.work_order_id.work_order_number:
                    super(UnifiedContractInvoice, rec).write({'name': rec.work_order_id.work_order_number})
        self._sync_to_work_order()
        return res

    def unlink(self):
        for rec in self:
            if rec.work_order_id:
                rec.work_order_id.with_context(
                    skip_invoice_sync=True, 
                    skip_stage_permission_check=True, 
                    skip_closure_check=True
                ).write({
                    'invoice_id': False,
                    'invoice_number': False,
                    'payment_status': 'unpaid',
                    'stage_5_status': 'in_progress'
                })
                rec.work_order_id._compute_stage_statuses()
                rec.work_order_id._compute_overall_progress()
        return super().unlink()

    def _sync_to_work_order(self):
        """Strictly sync invoice data, payment status & stage_5_status back to linked Work Order, and auto-close when paid."""
        stage_6 = self.env['unified.contract.work.order.stage'].search([('sequence', '=', 6)], limit=1)
        if not stage_6:
            stage_6 = self.env['unified.contract.work.order.stage'].search([('name', 'ilike', 'إغلاق')], limit=1)
        stage_5 = self.env['unified.contract.work.order.stage'].search([('sequence', '=', 5)], limit=1)

        for rec in self:
            if rec.work_order_id:
                wo = rec.work_order_id
                
                wo_payment_status = 'unpaid'
                if rec.state == 'paid':
                    wo_payment_status = 'paid'
                
                stage_5_st = 'referred'
                if rec.state == 'draft':
                    if rec.invoice_number:
                        stage_5_st = 'issued'
                    else:
                        stage_5_st = 'referred'
                elif rec.state == 'uploaded':
                    stage_5_st = 'uploaded'
                elif rec.state == 'late':
                    stage_5_st = 'late'
                elif rec.state == 'correction_requested':
                    stage_5_st = 'correction_requested'
                elif rec.state == 'paid':
                    stage_5_st = 'paid'
                elif rec.state == 'cancel':
                    stage_5_st = 'in_progress'

                wo_vals = {
                    'extract_service_number': rec.extract_service_number,
                    'amount_before_tax': rec.amount_before_tax,
                    'tax_amount': rec.tax_amount,
                    'amount_total': rec.amount_total,
                    'invoice_number': rec.invoice_number,
                    'invoice_amount': rec.amount_total,
                    'payment_status': wo_payment_status,
                    'stage_5_status': stage_5_st,
                    'invoice_id': rec.id,
                }

                if rec.state == 'paid':
                    if stage_6:
                        wo_vals['stage_id'] = stage_6.id
                    wo_vals['state'] = 'done'
                    wo_vals['progress'] = 100.0
                    wo_vals['stage_1_status'] = 'completed'
                    wo_vals['stage_2_status'] = 'completed'
                    wo_vals['stage_3_status'] = 'completed' if wo.stage_3_status != 'skipped' else 'skipped'
                    wo_vals['stage_4_status'] = 'completed'
                    wo_vals['stage_5_status'] = 'paid'
                else:
                    if wo.state == 'done':
                        wo_vals['state'] = 'in_progress'
                    if stage_5 and wo.stage_id.sequence == 6:
                        wo_vals['stage_id'] = stage_5.id

                wo.with_context(
                    skip_invoice_sync=True, 
                    skip_stage_permission_check=True, 
                    skip_closure_check=True,
                    skip_certificate_reset=True
                ).write(wo_vals)
                wo._compute_stage_statuses()
                wo._compute_overall_progress()

    def action_confirm_and_upload(self):
        """Finance Team action to confirm invoice issuance and upload to system"""
        for rec in self:
            if not rec.invoice_number:
                raise ValidationError(_('عذراً! يرجى إدخال رقم الفاتورة الصادرة قبل الإرسال والتأكيد.'))
            today = fields.Date.context_today(self)
            if not rec.invoice_date:
                rec.invoice_date = today
            rec.upload_date = today
            rec.state = 'uploaded'
            rec.message_post(body=_('🚀 تم إصدار وتأكيد الفاتورة رقم <b>%s</b> والرفع على النظام بواسطة <b>%s</b>.') % (rec.invoice_number, self.env.user.name))

    def action_request_correction(self):
        """Finance Team action to request data correction from Work Order team"""
        for rec in self:
            rec.state = 'correction_requested'
            rec.message_post(body=_('📝 تم طلب تصحيح / تعديل بيانات المستخلص بواسطة <b>%s</b>.') % self.env.user.name)
            if rec.work_order_id:
                rec.work_order_id.message_post(body=_('📝 قامت الإدارة المالية بطلب تصحيح / تعديل الفاتورة رقم (<b>%s</b>). يمكنك الآن تعديل بيانات المستخلص وإعادة الإحالة.') % rec.name)

    def action_set_late(self):
        for rec in self:
            rec.state = 'late'
            rec.message_post(body=_('⚠️ تم تحويل حالة الفاتورة إلى <b>متأخر</b> بواسطة <b>%s</b>.') % self.env.user.name)

    def action_set_paid(self):
        for rec in self:
            rec.state = 'paid'
            rec.message_post(body=_('✅ تم تحصيل الفاتورة بالكامل وإغلاق أمر العمل تلقائياً بواسطة <b>%s</b>.') % self.env.user.name)

    def action_set_draft(self):
        for rec in self:
            rec.state = 'draft'

    @api.model
    def _cron_check_overdue_invoices(self):
        """Cron job to check overdue invoices after configured days (default 60 days)"""
        overdue_days_str = self.env['ir.config_parameter'].sudo().get_param('ao_unified_contract.invoice_overdue_days', default=60)
        try:
            overdue_days = int(overdue_days_str)
        except (ValueError, TypeError):
            overdue_days = 60

        today = fields.Date.context_today(self)
        uploaded_invoices = self.search([('state', '=', 'uploaded')])
        for inv in uploaded_invoices:
            ref_date = inv.upload_date or inv.invoice_date or fields.Date.to_date(inv.create_date)
            if ref_date:
                days_diff = (today - ref_date).days
                if days_diff >= overdue_days:
                    inv.state = 'late'
                    inv.message_post(body=_('⚠️ تم تحويل حالة الفاتورة تلقائياً إلى <b>متأخر</b> لتجاوزها الفترة المسموحة (%s يوم من الرفع على النظام المالي).') % days_diff)
