# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


LEVEL_NEXT = {
    'manager': 'project_manager',
    'project_manager': 'general_manager',
    'general_manager': 'hr_manager',
    'hr_manager': 'done',
}

LEVEL_GROUP_XMLID = {
    'project_manager': 'ao_leave_approval.group_leave_project_manager',
    'general_manager': 'ao_leave_approval.group_leave_general_manager',
    'hr_manager': 'ao_leave_approval.group_leave_hr_manager',
}

LEVEL_APPROVER_FIELD = {
    'manager': 'manager_approver_id',
    'project_manager': 'project_manager_approver_id',
    'general_manager': 'general_manager_approver_id',
    'hr_manager': 'hr_manager_approver_id',
}


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    remaining_leave_days = fields.Float(
        string='Remaining Leave Days',
        compute='_compute_remaining_leave_days',
        help='Allocated days for this time off type minus validated and pending requests (virtual remaining).',
    )
    requires_allocation = fields.Selection(
        related='holiday_status_id.requires_allocation',
    )
    current_level = fields.Selection(
        [
            ('none', 'None'),
            ('manager', 'Direct Manager'),
            ('project_manager', 'Project Manager'),
            ('general_manager', 'General Manager'),
            ('hr_manager', 'HR Managers'),
            ('done', 'Approved'),
        ],
        string='Current Level',
        default='none',
        tracking=True,
        copy=False,
        readonly=True,
    )
    can_decide = fields.Boolean(
        string='Can Decide',
        compute='_compute_can_decide',
    )
    manager_approver_id = fields.Many2one(
        'res.users', string='Manager Approver', readonly=True, copy=False, tracking=True,
    )
    project_manager_approver_id = fields.Many2one(
        'res.users', string='Project Manager Approver', readonly=True, copy=False, tracking=True,
    )
    general_manager_approver_id = fields.Many2one(
        'res.users', string='General Manager Approver', readonly=True, copy=False, tracking=True,
    )
    hr_manager_approver_id = fields.Many2one(
        'res.users', string='HR Manager Approver', readonly=True, copy=False, tracking=True,
    )

    def _get_current_level_label(self, level=None):
        self.ensure_one()
        level = level or self.current_level
        selection = self._fields['current_level'].selection
        if callable(selection):
            selection = selection(self)
        return dict(selection).get(level, '')

    @api.depends('employee_id', 'holiday_status_id', 'date_from')
    def _compute_remaining_leave_days(self):
        for rec in self:
            if rec.employee_id and rec.holiday_status_id:
                leave_type = rec.holiday_status_id.with_context(
                    employee_id=rec.employee_id.id,
                    default_employee_id=rec.employee_id.id,
                    default_date_from=rec.date_from or fields.Date.today(),
                )
                rec.remaining_leave_days = leave_type.virtual_remaining_leaves
            else:
                rec.remaining_leave_days = 0.0

    @api.depends_context('uid')
    @api.depends(
        'state', 'current_level', 'employee_id',
        'employee_id.user_id', 'employee_id.parent_id',
        'employee_id.parent_id.user_id',
        'employee_id.leave_project_manager_id',
        'employee_id.leave_project_manager_id.user_id',
    )
    def _compute_can_decide(self):
        user = self.env.user
        is_pm = user.has_group('ao_leave_approval.group_leave_project_manager')
        is_gm = user.has_group('ao_leave_approval.group_leave_general_manager')
        is_hr = user.has_group('ao_leave_approval.group_leave_hr_manager')
        group_access = {
            'project_manager': is_pm,
            'general_manager': is_gm,
            'hr_manager': is_hr,
        }
        for holiday in self:
            holiday.can_decide = holiday._user_can_decide(user, group_access=group_access)

    def _user_can_decide(self, user=None, group_access=None):
        self.ensure_one()
        user = user or self.env.user
        if self.state != 'confirm' or self.holiday_type != 'employee':
            return False
        if self.employee_id.user_id and self.employee_id.user_id == user:
            return False
        if self.current_level == 'manager':
            manager_user = self.employee_id.parent_id.user_id
            return bool(manager_user) and manager_user == user
        if self.current_level == 'project_manager':
            pm_user = self.employee_id.leave_project_manager_id.user_id
            if pm_user and pm_user == user:
                return True
        if group_access is not None:
            return bool(group_access.get(self.current_level))
        xmlid = LEVEL_GROUP_XMLID.get(self.current_level)
        if xmlid:
            return user.has_group(xmlid)
        return False

    def _ensure_leave_group_user(self, user, level):
        xmlid = LEVEL_GROUP_XMLID.get(level)
        if not user or not xmlid:
            return
        group = self.env.ref(xmlid, raise_if_not_found=False)
        if group and group not in user.sudo().groups_id:
            user.sudo().write({'groups_id': [(4, group.id)]})

    def _get_users_for_level(self, level):
        self.ensure_one()
        if level == 'manager':
            return self.employee_id.parent_id.user_id
        users = self.env['res.users']
        xmlid = LEVEL_GROUP_XMLID.get(level)
        if xmlid:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                users = group.sudo().users.filtered(lambda u: u.active and not u.share)
        if level == 'project_manager':
            pm_employee = self.employee_id.leave_project_manager_id
            if pm_employee:
                if not pm_employee.user_id:
                    raise UserError(_(
                        'Project Manager %(name)s has no related user. '
                        'Link a user on that employee first.',
                        name=pm_employee.name,
                    ))
                self._ensure_leave_group_user(pm_employee.user_id, 'project_manager')
                users |= pm_employee.user_id
        return users

    def _check_direct_manager(self):
        self.ensure_one()
        if not self.employee_id.parent_id.user_id:
            raise UserError(_(
                'Employee %(employee)s has no manager with a linked user. '
                'Set the Manager on the employee before requesting time off.',
                employee=self.employee_id.name,
            ))

    def _check_level_has_approvers(self, level):
        self.ensure_one()
        users = self._get_users_for_level(level)
        if not users:
            raise UserError(_(
                'No users found for approval level: %(level)s. '
                'Assign users to this group (or set the employee manager) before continuing.',
                level=self._get_current_level_label(level),
            ))

    def _will_enter_approval_cycle(self, values, mapped_validation_type):
        leave_type_id = values.get('holiday_status_id')
        validation = mapped_validation_type.get(leave_type_id)
        if not validation or validation == 'no_validation':
            return False
        state = values.get('state')
        return not state or state == 'confirm'

    @api.model_create_multi
    def create(self, vals_list):
        leave_type_ids = [
            values.get('holiday_status_id')
            for values in vals_list
            if values.get('holiday_status_id')
        ]
        leave_types = self.env['hr.leave.type'].browse(leave_type_ids)
        mapped_validation_type = {
            leave_type.id: leave_type.leave_validation_type
            for leave_type in leave_types
        }
        for values in vals_list:
            if not self._will_enter_approval_cycle(values, mapped_validation_type):
                continue
            employee = self.env['hr.employee'].browse(values.get('employee_id'))
            if not employee:
                employee = self.env.user.employee_id
            if employee and not employee.parent_id.user_id:
                raise UserError(_(
                    'Employee %(employee)s has no manager with a linked user. '
                    'Set the Manager on the employee before requesting time off.',
                    employee=employee.name,
                ))
            values.setdefault('current_level', 'manager')
        holidays = super().create(vals_list)
        missing_level = holidays.filtered(
            lambda h: h.state == 'confirm'
            and h.holiday_type == 'employee'
            and h.current_level in (False, 'none')
        )
        if missing_level:
            missing_level.sudo().write({'current_level': 'manager'})
            missing_level.activity_update()
        return holidays

    def action_confirm(self):
        to_cycle = self.filtered(
            lambda h: h.holiday_type == 'employee' and h.validation_type != 'no_validation'
        )
        for holiday in to_cycle:
            holiday._check_direct_manager()
            holiday._check_level_has_approvers('manager')
        to_cycle.write({'current_level': 'manager'})
        return super().action_confirm()

    def action_approve(self, check_state=True):
        if check_state and any(holiday.state != 'confirm' for holiday in self):
            raise UserError(_(
                'Time off request must be confirmed ("To Approve") in order to approve it.'
            ))

        other_leaves = self.filtered(lambda h: h.holiday_type != 'employee')
        if other_leaves:
            other_leaves.sudo().action_validate()

        wizard_action = False
        for holiday in self.filtered(lambda h: h.holiday_type == 'employee'):
            if not holiday._user_can_decide():
                raise UserError(_(
                    'You are not allowed to approve this time off request at the current level.'
                ))
            current = holiday.current_level
            next_level = LEVEL_NEXT.get(current)
            if not next_level:
                raise UserError(_('This time off request is not waiting for approval.'))

            vals = {}
            approver_field = LEVEL_APPROVER_FIELD.get(current)
            if approver_field:
                vals[approver_field] = self.env.user.id

            if next_level == 'done':
                if holiday.pending_task_ids:
                    holiday.sudo().write(vals)
                    wizard_action = holiday._action_pending_task_wizard()
                    continue
                holiday.sudo().write(vals)
                holiday.sudo().action_validate()
                holiday.message_post(body=_(
                    'Approved by %(user)s (%(level)s). Time off is fully approved.',
                    user=self.env.user.name,
                    level=holiday._get_current_level_label(current),
                ))
            else:
                holiday._check_level_has_approvers(next_level)
                vals['current_level'] = next_level
                holiday.sudo().write(vals)
                holiday.message_post(body=_(
                    'Approved by %(user)s (%(level)s). Forwarded to %(next_level)s.',
                    user=self.env.user.name,
                    level=holiday._get_current_level_label(current),
                    next_level=holiday._get_current_level_label(next_level),
                ))
                holiday.activity_update()

        return wizard_action or True

    def _action_pending_task_wizard(self):
        self.ensure_one()
        ctx = dict(self.env.context or {})
        ctx.update({'default_leave_req_id': self.id})
        return {
            'name': _('Re-Assign Task'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'task.reassign',
            'target': 'new',
            'context': ctx,
        }

    def action_refuse(self):
        current_employee = self.env.user.employee_id
        for holiday in self:
            if holiday.state != 'confirm':
                raise UserError(_(
                    'Time off request must be waiting for approval in order to refuse it.'
                ))
            if holiday.holiday_type == 'employee' and not holiday._user_can_decide():
                raise UserError(_(
                    'You are not allowed to refuse this time off request at the current level.'
                ))

        self.sudo().write({
            'state': 'refuse',
            'second_approver_id': current_employee.id,
        })
        self.mapped('meeting_id').write({'active': False})
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.sudo().write({'state': 'refuse'})
        self._remove_resource_leave()
        for holiday in self:
            if holiday.employee_id.user_id:
                holiday.message_post(
                    body=_(
                        'Your %(leave_type)s planned on %(date)s has been refused by %(user)s (%(level)s).',
                        leave_type=holiday.holiday_status_id.display_name,
                        date=holiday.date_from,
                        user=self.env.user.name,
                        level=holiday._get_current_level_label(),
                    ),
                    partner_ids=holiday.employee_id.user_id.partner_id.ids,
                )
        self.activity_update()
        return True

    def action_draft(self):
        res = super().action_draft()
        self.write({
            'current_level': 'none',
            'manager_approver_id': False,
            'project_manager_approver_id': False,
            'general_manager_approver_id': False,
            'hr_manager_approver_id': False,
        })
        return res

    def action_validate(self):
        records = self
        if not self.env.is_superuser() and any(h.current_level == 'hr_manager' for h in self):
            records = self.sudo()
        res = super(HrLeave, records).action_validate()
        validated = records.filtered(lambda h: h.state == 'validate' and h.current_level != 'done')
        if validated:
            validated.write({'current_level': 'done'})
        return res

    def _check_approval_update(self, state):
        if self.env.is_superuser():
            return
        to_check = self.env['hr.leave']
        for holiday in self:
            if state in ('validate', 'refuse') and holiday._user_can_decide():
                continue
            to_check |= holiday
        if to_check:
            super(HrLeave, to_check)._check_approval_update(state)

    def _get_responsible_for_approval(self):
        self.ensure_one()
        if self.holiday_type != 'employee':
            return super()._get_responsible_for_approval()
        users = self.sudo()._get_users_for_level(self.current_level)
        return users or super()._get_responsible_for_approval()

    def activity_update(self):
        confirm_leaves = self.filtered(lambda h: h.state == 'confirm')
        others = self - confirm_leaves
        if others:
            super(HrLeave, others).activity_update()
        if not confirm_leaves:
            return True
        confirm_leaves.activity_unlink([
            'hr_holidays.mail_act_leave_approval',
            'hr_holidays.mail_act_leave_second_approval',
        ])
        for holiday in confirm_leaves:
            users = holiday.sudo()._get_users_for_level(holiday.current_level)
            note = _(
                'New %(leave_type)s Request created by %(user)s',
                leave_type=holiday.holiday_status_id.name,
                user=holiday.create_uid.name,
            )
            for user in users:
                holiday.sudo().activity_schedule(
                    'hr_holidays.mail_act_leave_approval',
                    user_id=user.id,
                    note=note,
                )
            try:
                holiday._message_notify_current_level()
            except Exception:
                _logger.exception(
                    'OdooBot leave notification failed for leave %s', holiday.id,
                )
        return True

    def _message_notify_current_level(self):
        self.ensure_one()
        users = self.sudo()._get_users_for_level(self.current_level)
        if not users:
            return
        body = _(
            'Time off request for %(employee)s is waiting for %(level)s approval.',
            employee=self.employee_id.name,
            level=self._get_current_level_label(),
        )
        partners = users.mapped('partner_id')
        if partners:
            self.env['mail.thread'].sudo().message_notify(
                partner_ids=partners.ids,
                model_description='Time Off',
                subject=_('Time Off Approval Required'),
                body=body,
                email_layout_xmlid='mail.mail_notification_light',
            )
        for user in users:
            self._send_odoobot_approval_message(user)

    def _get_leave_record_url(self):
        self.ensure_one()
        base_url = self.get_base_url()
        return f'{base_url}/web#id={self.id}&model=hr.leave&view_type=form'

    def _send_odoobot_approval_message(self, user):
        """Post a Discuss DM from OdooBot so the approver gets a chat popup/message."""
        self.ensure_one()
        if not user or not user.partner_id or user.share:
            return
        odoobot = self.env.ref('base.partner_root')
        record_url = self._get_leave_record_url()
        body = Markup(
            '<p>%(intro)s</p>'
            '<ul>'
            '<li><b>%(employee_label)s</b>: %(employee)s</li>'
            '<li><b>%(type_label)s</b>: %(leave_type)s</li>'
            '<li><b>%(level_label)s</b>: %(level)s</li>'
            '<li><b>%(dates_label)s</b>: %(date_from)s → %(date_to)s</li>'
            '</ul>'
            '<p><a href="%(url)s" target="_blank">%(open_label)s</a></p>'
        ) % {
            'intro': _(
                'A time off request needs your approval.',
            ),
            'employee_label': _('Employee'),
            'employee': self.employee_id.name or '',
            'type_label': _('Time Off Type'),
            'leave_type': self.holiday_status_id.display_name or '',
            'level_label': _('Current Level'),
            'level': self._get_current_level_label(),
            'dates_label': _('Dates'),
            'date_from': self.request_date_from or self.date_from or '',
            'date_to': self.request_date_to or self.date_to or '',
            'url': record_url,
            'open_label': _('Open Time Off Request'),
        }
        channel = self.env['discuss.channel'].with_user(user).channel_get(
            [odoobot.id, user.partner_id.id],
            pin=False,
        )
        channel.sudo().with_context(mail_create_nosubscribe=True).message_post(
            body=body,
            author_id=odoobot.id,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
