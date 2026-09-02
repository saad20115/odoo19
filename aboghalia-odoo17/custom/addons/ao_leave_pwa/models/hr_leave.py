# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    pwa_balance_warning = fields.Text(
        string='PWA Balance Warning',
        copy=False,
        help='Arabic note for approvers when paid leave exceeds available balance.',
    )

    def _pwa_notify(self, users, title, body, data=None):
        self.ensure_one()
        if not users:
            return
        try:
            self.env['leave.pwa.subscription'].sudo().notify_users(
                users, title, body, data=data or {},
            )
        except Exception:
            _logger.exception('PWA notify failed for leave %s', self.id)

    def _pwa_leave_url(self):
        return '/leave#summary'

    def _pwa_approval_url(self):
        return '/leave#approvals'

    def _pwa_approval_notify_users(self, holiday):
        """Users to Web-Push when a leave waits at holiday.current_level."""
        users = holiday.sudo()._get_users_for_level(holiday.current_level)
        # Force approvers must be notified on every new request (manager stage).
        if holiday.current_level == 'manager':
            force_group = self.env.ref(
                'ao_leave_approval.group_leave_force_approver',
                raise_if_not_found=False,
            )
            if force_group:
                users |= force_group.sudo().users.filtered(
                    lambda u: u.active and not u.share,
                )
        return users

    def activity_update(self):
        res = super().activity_update()
        for holiday in self.filtered(lambda h: h.state == 'confirm' and h.holiday_type == 'employee'):
            try:
                users = holiday._pwa_approval_notify_users(holiday)
                if not users:
                    continue
                holiday._pwa_notify(
                    users,
                    _('Time Off Approval'),
                    _(
                        '%(employee)s requested %(leave_type)s — waiting for %(level)s.',
                        employee=holiday.employee_id.name or '',
                        leave_type=holiday.holiday_status_id.display_name or '',
                        level=holiday._get_current_level_label() if hasattr(holiday, '_get_current_level_label') else '',
                    ),
                    data={
                        'type': 'leave_approval',
                        'leave_id': holiday.id,
                        'url': holiday._pwa_approval_url(),
                    },
                )
            except Exception:
                _logger.exception('PWA approver notify failed for leave %s', holiday.id)
        return res

    def action_approve(self, check_state=True):
        before = {h.id: (h.state, getattr(h, 'current_level', False)) for h in self}
        res = super().action_approve(check_state=check_state)
        for holiday in self:
            holiday.invalidate_recordset()
            prev_state, _prev_level = before.get(holiday.id, (False, False))
            emp_user = holiday.employee_id.user_id
            if not emp_user:
                continue
            if holiday.state == 'validate':
                holiday._pwa_notify(
                    emp_user,
                    _('Time Off Approved'),
                    _(
                        'Your %(leave_type)s request was fully approved.',
                        leave_type=holiday.holiday_status_id.display_name or '',
                    ),
                    data={
                        'type': 'leave_validated',
                        'leave_id': holiday.id,
                        'url': holiday._pwa_leave_url(),
                    },
                )
            elif holiday.state == 'confirm' and prev_state == 'confirm':
                level = (
                    holiday._get_current_level_label()
                    if hasattr(holiday, '_get_current_level_label') else ''
                )
                holiday._pwa_notify(
                    emp_user,
                    _('Time Off Update'),
                    _(
                        'Your leave request was approved at the previous level and forwarded to %(level)s.',
                        level=level,
                    ),
                    data={
                        'type': 'leave_forwarded',
                        'leave_id': holiday.id,
                        'url': holiday._pwa_leave_url(),
                    },
                )
        return res

    def action_refuse(self):
        res = super().action_refuse()
        for holiday in self:
            emp_user = holiday.employee_id.user_id
            if not emp_user:
                continue
            holiday._pwa_notify(
                emp_user,
                _('Time Off Refused'),
                _(
                    'Your %(leave_type)s request was refused.',
                    leave_type=holiday.holiday_status_id.display_name or '',
                ),
                data={
                    'type': 'leave_refused',
                    'leave_id': holiday.id,
                    'url': holiday._pwa_leave_url(),
                },
            )
        return res
