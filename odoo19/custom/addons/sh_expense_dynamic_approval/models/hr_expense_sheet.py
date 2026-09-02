# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import api, fields, models, _
from datetime import datetime


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    approval_level_id = fields.Many2one(
        'sh.expense.approval.config', string="Approval Level", compute="compute_approval_level")

    level = fields.Integer(string="Next Approval Level", readonly=True)
    user_ids = fields.Many2many('res.users', string="Users", readonly=True)
    group_ids = fields.Many2many('res.groups', string="Groups", readonly=True)
    is_boolean = fields.Boolean(
        string="Boolean", compute="compute_is_boolean", search='_search_is_boolean')
    approval_info_line = fields.One2many(
        'sh.approval.info', 'hr_expense_sheet_id', readonly=True)
    rejection_date = fields.Datetime(string="Reject Date", readonly=True)
    reject_by = fields.Many2one('res.users', string="Reject By", readonly=True)
    reject_reason = fields.Char(string="Reject Reason", readonly=True)

    def compute_is_boolean(self):

        if self.env.user.id in self.user_ids.ids or any(item in self.env.user.groups_id.ids for item in self.group_ids.ids):
            self.is_boolean = True
        else:
            self.is_boolean = False

    def _search_is_boolean(self, operator, value):

        results = []

        if value:
            expense_sheet_ids = self.env['hr.expense.sheet'].search([])
            if expense_sheet_ids:
                for expense_sheet_id in expense_sheet_ids:
                    if self.env.user.id in expense_sheet_id.user_ids.ids or any(item in self.env.user.groups_id.ids for item in expense_sheet_id.group_ids.ids):
                        results.append(expense_sheet_id.id)
        return [('id', 'in', results)]

    def action_submit_sheet(self):

        template_id = self.env.ref("sh_expense_dynamic_approval.email_template_for_approve_expense_report")

        self.approval_info_line = False
        self.level = False
        self.group_ids = False
        self.user_ids = False

        if self.approval_level_id.expense_approval_line:

            lines = self.approval_level_id.expense_approval_line

            for line in lines:
                dictt = []
                if line.approve_by == 'group':
                    dictt.append((0, 0, {
                        'level': line.level,
                        'user_ids': False,
                        'group_ids': [(6, 0, line.group_ids.ids)],
                    }))

                if line.approve_by == 'user':
                    dictt.append((0, 0, {
                        'level': line.level,
                        'user_ids': [(6, 0, line.user_ids.ids)],
                        'group_ids': False,
                    }))

                self.update({
                    'approval_info_line': dictt
                })

            if lines[0].approve_by == 'group':
                self.write({
                    'level': lines[0].level,
                    'group_ids': [(6, 0, lines[0].group_ids.ids)],
                    'user_ids': False
                })

                users = self.env['res.users'].search(
                    [('groups_id', 'in', lines[0].group_ids.ids)])

                if template_id and users:
                    for user in users:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                if users:
                    for user in users:

                        self.env['bus.bus']._sendone(user.partner_id, 'simple_notification', {
                            'type': 'info',
                            'sticky':True,                            
                            'title': _("Approvel Notitification"),
                            'message': _('You have approval notification for Expense Report %s', self.name),
                        })

            if lines[0].approve_by == 'user':
                self.write({
                    'level': lines[0].level,
                    'user_ids': [(6, 0, lines[0].user_ids.ids)],
                    'group_ids': False
                })

                if template_id and lines[0].user_ids:
                    for user in lines[0].user_ids:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                if lines[0].user_ids:
                    for user in lines[0].user_ids:
                       
                        self.env['bus.bus']._sendone(user.partner_id, 'simple_notification', {
                            'type': 'info',
                            'sticky':True,
                            'title': _("Approvel Notitification"),
                            'message': _('You have approval notification for Expense Report %s', self.name),
                        })

            super().action_submit_sheet()
        else:
            super().action_submit_sheet()

    @api.depends('total_amount')
    def compute_approval_level(self):

        if self.total_amount:

            expense_approvals = self.env['sh.expense.approval.config'].search(
                [('min_amount', '<', self.total_amount), ('company_ids.id', 'in', [self.env.company.id])])

            listt = []
            for expense_approval in expense_approvals:
                listt.append(expense_approval.min_amount)

            if listt:
                expense_approval = expense_approvals.filtered(
                    lambda x: x.min_amount == max(listt))

                self.update({
                    'approval_level_id': expense_approval[0].id
                })
            else:
                self.approval_level_id = False
        else:
            self.approval_level_id = False

    def action_approve_expense_report(self):

        template_id = self.env.ref(
            "sh_expense_dynamic_approval.email_template_for_approve_expense_report")

        info = self.approval_info_line.filtered(
            lambda x: x.level == self.level)

        if info:
            info.status = True
            info.approval_date = datetime.now()
            info.approved_by = self.env.user

        line_id = self.env['sh.expense.approval.line'].search(
            [('expense_approval_config_id', '=', self.approval_level_id.id), ('level', '=', self.level)])

        next_line = self.env['sh.expense.approval.line'].search(
            [('expense_approval_config_id', '=', self.approval_level_id.id), ('id', '>', line_id.id)], limit=1)

        if next_line:
            if next_line.approve_by == 'group':
                self.write({
                    'level': next_line.level,
                    'group_ids': [(6, 0, next_line.group_ids.ids)],
                    'user_ids': False
                })
                users = self.env['res.users'].search(
                    [('groups_id', 'in', next_line.group_ids.ids)])

                if template_id and users and self.approval_level_id.is_boolean:
                    for user in users:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email, 'email_cc': self.employee_id.work_email})

                if template_id and users and not self.approval_level_id.is_boolean:
                    for user in users:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                if users:
                    for user in users:

                        self.env['bus.bus']._sendone(user.partner_id, 'simple_notification', {
                            'type': 'info',
                            'sticky':True,
                            'title': _("Approvel Notitification"),
                            'message': _('You have approval notification for Expense Report %s', self.name),
                        })

            if next_line.approve_by == 'user':
                self.write({
                    'level': next_line.level,
                    'user_ids': [(6, 0, next_line.user_ids.ids)],
                    'group_ids': False
                })

                if template_id and next_line.user_ids and self.approval_level_id.is_boolean:
                    for user in next_line.user_ids:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email, 'email_cc': self.employee_id.work_email})

                if template_id and next_line.user_ids and not self.approval_level_id.is_boolean:
                    for user in next_line.user_ids:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                if next_line.user_ids:
                    for user in next_line.user_ids:

                        self.env['bus.bus']._sendone(user.partner_id, 'simple_notification', {
                            'type': 'info',
                            'sticky':True,
                            'title': _("Approvel Notitification"),
                            'message': _('You have approval notification for Expense Report %s', self.name),
                        })

        else:
            template_id = self.env.ref(
                "sh_expense_dynamic_approval.email_template_for_confirm_expense_report")
            if template_id:
                template_id.sudo().send_mail(self.id, force_send=True, email_values={
                    'email_from': self.env.user.email, 'email_to': self.employee_id.work_email})

            if self.employee_id.user_id:

                self.env['bus.bus']._sendone(self.employee_id.user_id.partner_id, 'simple_notification', {
                    'type': 'info',
                    'sticky':True,
                    'title': _("Approvel Notitification"),
                    'message': _('Your Expense Report %s is approved', self.name),
                })

            self.write({
                'level': False,
                'group_ids': False,
                'user_ids': False,
                'state': 'approve'
            })

            super().action_approve_expense_sheets()

    def action_approve(self):

        super().action_approve_expense_sheets()
