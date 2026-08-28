# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class UnifiedContractRegion(models.Model):
    _name = 'unified.contract.region'
    _description = 'المنطقة'
    _order = 'name asc'

    name = fields.Char(string='اسم المنطقة', required=True)
    code = fields.Char(string='كود المنطقة')
    district_ids = fields.One2many('unified.contract.district', 'region_id', string='الأحياء والمواقع التابعة')

class UnifiedContractDistrict(models.Model):
    _name = 'unified.contract.district'
    _description = 'الحي / الموقع'
    _order = 'name asc'

    name = fields.Char(string='اسم الحي / الموقع', required=True)
    code = fields.Char(string='كود الحي / الموقع')
    region_id = fields.Many2one('unified.contract.region', string='المنطقة التابعة لها', required=True, ondelete='cascade')
    station_ids = fields.One2many('unified.contract.station', 'district_id', string='المحطات التابعة')

class UnifiedContractStation(models.Model):
    _name = 'unified.contract.station'
    _description = 'رقم / اسم المحطة'
    _order = 'name asc'

    name = fields.Char(string='اسم / رقم المحطة', required=True)
    code = fields.Char(string='كود المحطة (بالإنجليزي/أرقام)', help='رمز المحطة الفني باللغة الإنجليزية أو الأرقام')
    region_id = fields.Many2one('unified.contract.region', string='المنطقة', related='district_id.region_id', store=True, readonly=True)
    district_id = fields.Many2one('unified.contract.district', string='الحي / الموقع', required=True, ondelete='cascade')

class UnifiedContractDepartment(models.Model):
    _name = 'unified.contract.department'
    _description = 'القسم / الإدارة'
    _order = 'name asc'

    name = fields.Char(string='اسم القسم / الإدارة', required=True)
    code = fields.Char(string='كود القسم')

class UnifiedContractWorkOrderType(models.Model):
    _name = 'unified.contract.work.order.type'
    _description = 'نوع أمر العمل'
    _order = 'name asc'

    name = fields.Char(string='نوع أمر العمل', required=True)
    code = fields.Char(string='كود النوع')

class UnifiedContractWorkOrderCategory(models.Model):
    _name = 'unified.contract.work.order.category'
    _description = 'تصنيف أمر العمل'
    _order = 'name asc'

    name = fields.Char(string='تصنيف أمر العمل', required=True)
    code = fields.Char(string='كود التصنيف')

class UnifiedContractPermitStatus(models.Model):
    _name = 'unified.contract.permit.status'
    _description = 'حالة التصريح'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='حالة التصريح', required=True)
    sequence = fields.Integer(string='التسلسل', default=10)
    code = fields.Char(string='كود حالة التصريح')
    description = fields.Text(string='الوصف والتوجيهات')

class UnifiedContractAlertSetting(models.Model):
    _name = 'unified.contract.alert.setting'
    _description = 'إدارة التنبيهات وإعدادات النظام'

    name = fields.Char(string='اسم التكوين', default='إعدادات التنبيهات والنظام', required=True)
    
    # 1. Work Order Number Settings
    wo_number_length = fields.Integer(
        string='طول رقم أمر العمل (عدد الخانات)',
        default=12,
        help='حدد طول رقم أمر العمل المطلوب (مثلاً 12 رقم)'
    )
    wo_number_unique = fields.Boolean(
        string='اشتراط عدم تكرار رقم أمر العمل',
        default=True,
        help='منع تكرار رقم أمر العمل في النظام'
    )
    wo_number_numeric_only = fields.Boolean(
        string='اشتراط أن يكون رقم أمر العمل أرقاماً فقط',
        default=True,
        help='عدم قبول حروف أو رموز في رقم أمر العمل'
    )

    # 2. Permit Alert Settings
    permit_alert_days_before = fields.Integer(
        string='التنبيه قبل انتهاء التصريح بـ (أيام)',
        default=1,
        help='عدد الأيام قبل تاريخ انتهاء التصريح لإصدار تنبيه مسبق'
    )
    permit_alert_max_count = fields.Integer(
        string='الحد الأقصى لعدد مرات التنبيه',
        default=3,
        help='الحد الأقصى لإرسال الإشعارات والتنبيهات المسبقة'
    )

    # 3. Permit Number Settings (إعدادات ضوابط رقم التصريح)
    permit_number_length = fields.Integer(
        string='طول رقم التصريح (عدد الخانات)',
        default=0,
        help='حدد طول رقم التصريح المطلوب (0 لعدم تقييد الخانات)'
    )
    permit_number_unique = fields.Boolean(
        string='اشتراط عدم تكرار رقم التصريح',
        default=False,
        help='منع تكرار رقم التصريح في النظام'
    )
    permit_number_numeric_only = fields.Boolean(
        string='اشتراط أن يكون رقم التصريح أرقاماً فقط',
        default=False,
        help='عدم قبول حروف أو رموز في رقم التصريح'
    )

    # 4. Programming Date Alert Settings (إعدادات تنبيه تاريخ البرنامج لمرحلة التنفيذ)
    programming_alert_days_before = fields.Integer(
        string='التنبيه قبل تاريخ البرنامج بـ (أيام)',
        default=3,
        help='عدد الأيام قبل تاريخ البرنامج لإصدار تنبيه مسبق في مرحلة التنفيذ'
    )

    @api.model
    def get_config(self):
        config = self.search([], limit=1)
        if not config:
            config = self.create({
                'name': 'إعدادات التنبيهات والنظام',
                'wo_number_length': 12,
                'wo_number_unique': True,
                'wo_number_numeric_only': True,
                'permit_alert_days_before': 1,
                'permit_alert_max_count': 3,
                'permit_number_length': 0,
                'permit_number_unique': False,
                'permit_number_numeric_only': False,
                'programming_alert_days_before': 3,
            })
        return config

    def action_open_alert_settings(self):
        config = self.get_config()
        return {
            'name': _('إدارة التنبيهات وإعدادات النظام'),
            'type': 'ir.actions.act_window',
            'res_model': 'unified.contract.alert.setting',
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'current',
        }

class UnifiedContractNotification(models.Model):
    _name = 'unified.contract.notification'
    _description = 'إشعارات النظام وأوامر العمل'
    _order = 'id desc'

    name = fields.Char(string='عنوان الإشعار', required=True)
    work_order_id = fields.Many2one('unified.contract.work.order', string='أمر العمل التابع له', ondelete='cascade')
    user_id = fields.Many2one('res.users', string='الموظف الموجه له الإشعار', required=True)
    date = fields.Datetime(string='تاريخ الإشعار', default=fields.Datetime.now)
    is_read = fields.Boolean(string='تمت القراءة', default=False)
    notification_type = fields.Selection([
        ('permit_expiry', 'تنبيه انتهاء تصريح ⚠️'),
        ('programming_alert', 'تنبيه تاريخ البرنامج ⚙️'),
        ('wo_late', 'تنبيه تأخر أمر عمل 🔴'),
        ('general', 'إشعار عام ℹ️'),
    ], string='نوع الإشعار', default='general')
    message = fields.Text(string='محتوى الإشعار')
