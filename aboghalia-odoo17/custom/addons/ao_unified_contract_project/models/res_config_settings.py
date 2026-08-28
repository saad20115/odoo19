# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    wo_number_length = fields.Integer(
        string='طول رقم أمر العمل (عدد الخانات)',
        config_parameter='ao_unified_contract.wo_number_length',
        default=12,
        help='حدد طول خانات رقم أمر العمل المطلوب (مثلاً: 12 رقم). اترك 0 إذا كنت لا تريد تقييد الطول.'
    )
    wo_number_unique = fields.Boolean(
        string='اشتراط عدم تكرار رقم أمر العمل (فريد)',
        config_parameter='ao_unified_contract.wo_number_unique',
        default=True,
        help='عند تفعيل هذا الخيار، سيمنع النظام حفظ أي رقم أمر عمل مكرر.'
    )
    wo_number_numeric_only = fields.Boolean(
        string='اشتراط أن يكون رقم أمر العمل أرقام فقط',
        config_parameter='ao_unified_contract.wo_number_numeric_only',
        default=True,
        help='عند تفعيل هذا الخيار، سيشترط النظام أن يحتوي رقم أمر العمل على أرقام فقط.'
    )
    permit_alert_days_before = fields.Integer(
        string='التنبيه قبل انتهاء التصريح بـ (أيام)',
        config_parameter='ao_unified_contract.permit_alert_days_before',
        default=1,
        help='حدد عدد الأيام المتبقية قبل تاريخ انتهاء التصريح لإرسال وتفعيل إشعار التنبيه.'
    )
    permit_alert_max_count = fields.Integer(
        string='عدد مرات إرسال التنبيه',
        config_parameter='ao_unified_contract.permit_alert_max_count',
        default=3,
        help='حدد الحد الأقصى لعدد مرات التنبيه المسموح بإرسالها للمسؤولين قبل وبعد الانتهاء.'
    )
