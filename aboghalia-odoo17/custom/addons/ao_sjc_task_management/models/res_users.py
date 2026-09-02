# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    sjc_team = fields.Selection(
        [
            ('makka', 'Makka'),
            ('madina', 'Madina'),
        ],
        string='SJC Team',
        help='Project Managers only see PO tasks for this team on the SJC dashboard.',
    )

    def _ao_sjc_home_action(self):
        return self.env.ref(
            'ao_sjc_task_management.action_sjc_dashboard',
            raise_if_not_found=False,
        )

    def _ao_sjc_employee_group(self):
        return self.env.ref(
            'ao_sjc_task_management.group_sjc_employee',
            raise_if_not_found=False,
        )

    def _ao_sjc_home_write_ctx(self):
        return self.with_context(
            skip_ao_sjc_home_action=True,
            skip_ao_po_home_action=True,
            skip_ao_makka_po_home_action=True,
        )

    def _ao_sjc_set_home_action_if_needed(self, force=False):
        """Set SJC+ Dashboard as Home Action for SJC users."""
        if self.env.context.get('skip_ao_sjc_home_action'):
            return
        action = self._ao_sjc_home_action()
        group = self._ao_sjc_employee_group()
        if not action or not group:
            return
        for user in self:
            in_group = group in user.groups_id
            if not in_group:
                if user.action_id and user.action_id.id == action.id:
                    user._ao_sjc_home_write_ctx().sudo().write({'action_id': False})
                continue
            if force or not user.action_id or user.action_id.id != action.id:
                user._ao_sjc_home_write_ctx().sudo().write({'action_id': action.id})

    @api.model
    def _ao_sjc_apply_home_action_all(self):
        """Called on module install/upgrade: all SJC users open Dashboard after login."""
        group = self._ao_sjc_employee_group()
        if not group:
            return True
        users = self.sudo().search([
            ('share', '=', False),
            ('groups_id', 'in', group.id),
        ])
        users._ao_sjc_set_home_action_if_needed(force=True)
        return True

    def _ao_fallback_home_action(self):
        """Prefer SJC dashboard when the user is an SJC employee."""
        group = self._ao_sjc_employee_group()
        action = self._ao_sjc_home_action()
        if group and action and group in self.groups_id:
            return action
        parent = super()
        if hasattr(parent, '_ao_fallback_home_action'):
            return parent._ao_fallback_home_action()
        return self.env.ref('mail.action_discuss', raise_if_not_found=False)

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._ao_sjc_set_home_action_if_needed(force=True)
        return users

    def write(self, vals):
        res = super().write(vals)
        if 'groups_id' in vals:
            self._ao_sjc_set_home_action_if_needed(force=True)
        return res
