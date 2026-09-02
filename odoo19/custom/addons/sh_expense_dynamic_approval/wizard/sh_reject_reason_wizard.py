# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.
from odoo import models, _
from datetime import datetime


class RejectionReasonWizard(models.TransientModel):
    _inherit = 'sh.reject.reason.wizard'
    _description = "Reject reason wizard"

    # name = fields.Char(string="Reason", required=True)

    def action_reject_order(self):

        active_obj = self.env[self.env.context.get('active_model')].browse(
            self.env.context.get('active_id'))

        if self.env.context.get('active_model') == 'hr.expense.sheet':

            active_obj.write({
                'reject_reason': self.name,
                'reject_by': active_obj.env.user,
                'rejection_date': datetime.now(),
                'state': 'cancel',
            })

            template_id = active_obj.env.ref(
                "sh_expense_dynamic_approval.email_template_for_reject_expense_report")

            if template_id:
                template_id.sudo().send_mail(active_obj.id, force_send=True, email_values={
                    'email_from': active_obj.env.user.email, 'email_to': active_obj.employee_id.work_email})

            if active_obj.employee_id.user_id:

                self.env['bus.bus']._sendone(active_obj.employee_id.user_id.partner_id, 'simple_notification', {
                    'type': 'info',
                    'sticky':True,
                    'title': _("Approvel Notitification"),
                    'message': _('Your Expense Report %s is rejected', active_obj.name),
                })

        return super().action_reject_order()
