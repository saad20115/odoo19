# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class UnifiedContractPermitExtendWizard(models.TransientModel):
    _name = 'unified.contract.permit.extend.wizard'
    _description = 'معالج تمديد تاريخ انتهاء التصريح'

    work_order_id = fields.Many2one(
        'unified.contract.work.order',
        string='أمر العمل',
        required=True
    )
    current_permit_end_date = fields.Date(
        string='تاريخ الانتهاء السابق/الحالي',
        related='work_order_id.permit_end_date',
        readonly=True
    )
    new_permit_end_date = fields.Date(
        string='تاريخ الانتهاء الجديد للتمديد',
        required=True
    )
    extension_reason = fields.Text(
        string='سبب وملاحظات التمديد'
    )

    @api.constrains('new_permit_end_date', 'current_permit_end_date')
    def _check_new_permit_end_date(self):
        for rec in self:
            if rec.current_permit_end_date and rec.new_permit_end_date:
                if rec.new_permit_end_date <= rec.current_permit_end_date:
                    raise ValidationError(_('عذراً! يجب أن يكون تاريخ التمديد الجديد أكبر من تاريخ الانتهاء السابق.'))

    @api.onchange('new_permit_end_date')
    def _onchange_new_permit_end_date(self):
        if self.current_permit_end_date and self.new_permit_end_date:
            if self.new_permit_end_date <= self.current_permit_end_date:
                return {
                    'warning': {
                        'title': _('تاريخ تمديد غير صالح'),
                        'message': _('عذراً! يجب أن يكون تاريخ التمديد الجديد أكبر من تاريخ الانتهاء السابق.')
                    }
                }

    def action_confirm_extend(self):
        self.ensure_one()
        order = self.work_order_id
        old_date = self.current_permit_end_date
        new_date = self.new_permit_end_date

        if old_date and new_date <= old_date:
            raise ValidationError(_('عذراً! يجب أن يكون تاريخ التمديد الجديد أكبر من تاريخ الانتهاء السابق.'))

        order.write({
            'permit_end_date': new_date
        })

        order.message_post(
            body=f"🔄 <b>تم تمديد تاريخ انتهاء التصريح</b> من ({old_date or 'غير محدد'}) إلى <b>({new_date})</b> بواسطة الموظف <b>{self.env.user.name}</b>.<br/>السبب/الملاحظات: {self.extension_reason or 'بدون ملاحظات مدونة'}"
        )
        return {'type': 'ir.actions.act_window_close'}
