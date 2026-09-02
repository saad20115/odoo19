# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SecWorkOrderExecutionStep(models.Model):
    _name = 'sec.work.order.execution.step'
    _description = 'مرحلة تنفيذ تفصيلية لأمر العمل'
    _order = 'sequence, id'

    sequence = fields.Integer(string='الترتيب', default=10)
    work_order_id = fields.Many2one('sec.work.order', string='أمر العمل', ondelete='cascade', required=True)
    name = fields.Char(string='بند / مرحلة التنفيذ', required=True)
    
    step_type = fields.Selection([
        ('civil', 'أعمال مدنية وحفر'),
        ('electrical', 'أعمال كهربائية وتمديد'),
        ('equipment', 'تركيب محولات ومعدات'),
        ('testing', 'فحص واختبارات وتشغيل'),
        ('asphalt', 'سفلتة وإعادة الوضع'),
        ('other', 'أخرى'),
    ], string='نوع الأعمال', default='civil', required=True)

    responsible_id = fields.Many2one('res.users', string='المسؤول الميداني', default=lambda self: self.env.user)
    date_start = fields.Date(string='تاريخ البدء')
    date_end = fields.Date(string='تاريخ الانتهاء')
    
    progress = fields.Float(string='نسبة الإنجاز %', default=0.0)
    status = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('in_progress', 'جاري التنفيذ'),
        ('done', 'مكتملة'),
    ], string='الحالة', default='pending')
    
    notes = fields.Char(string='ملاحظات التنفيذ')


class SecWorkOrderAttachmentCheck(models.Model):
    _name = 'sec.work.order.attachment.check'
    _description = 'المرفقات والورقيات الإلزامية للتسليم والإغلاق'
    _order = 'sequence, id'

    sequence = fields.Integer(string='الترتيب', default=10)
    work_order_id = fields.Many2one('sec.work.order', string='أمر العمل', ondelete='cascade', required=True)
    name = fields.Char(string='اسم المستند / الورقية المطلوبة', required=True)
    
    doc_category = fields.Selection([
        ('permit', 'تصاريح وتراخيص'),
        ('survey', 'كشفية ومخططات أولية'),
        ('test', 'تقارير فحص واختبارات'),
        ('as_built', 'مخططات As-Built المنفذة'),
        ('handover', 'محاضر تسليم وشهادات إنجاز'),
        ('sec_approval', 'اعتمادات شركة الكهرباء والاستشاري'),
        ('other', 'أخرى'),
    ], string='تصنيف المستند', default='handover', required=True)

    is_mandatory = fields.Boolean(string='إلزامي للإغلاق؟', default=True)
    is_uploaded = fields.Boolean(string='تم الرفع؟', compute='_compute_is_uploaded', store=True)
    
    attachment_file = fields.Binary(string='الملف المرفق', attachment=True)
    attachment_filename = fields.Char(string='اسم الملف')
    
    verified_by_id = fields.Many2one('res.users', string='تم التدقيق والاعتماد بواسطة')
    verification_date = fields.Date(string='تاريخ الاعتماد')

    @api.depends('attachment_file')
    def _compute_is_uploaded(self):
        for rec in self:
            rec.is_uploaded = bool(rec.attachment_file)
