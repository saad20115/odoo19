# -*- coding: utf-8 -*-
from odoo import api, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _ao_makka_po_followup_home_action(self):
        return self.env.ref('ao_makka_po_followup.action_po_followup', raise_if_not_found=False)

    def _ao_makka_po_set_home_action_if_needed(self, force=False):
        """Set PO Follow-up Makka as home action for contract users."""
        if self.env.context.get('skip_ao_makka_po_home_action'):
            return
        action = self._ao_makka_po_followup_home_action()
        group = self.env.ref('ao_makka_po_followup.group_makka_po_followup_user', raise_if_not_found=False)
        if not action or not group:
            return
        for user in self:
            in_group = group in user.groups_id
            if not in_group:
                # Avoid Access Error after login when group was removed.
                if user.action_id and user.action_id.id == action.id:
                    user.with_context(skip_ao_makka_po_home_action=True).sudo().write({
                        'action_id': False,
                    })
                continue
            if force or not user.action_id:
                user.with_context(skip_ao_makka_po_home_action=True).sudo().write({
                    'action_id': action.id,
                })

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._ao_makka_po_set_home_action_if_needed()
        return users

    def write(self, vals):
        res = super().write(vals)
        if 'groups_id' in vals:
            self._ao_makka_po_set_home_action_if_needed()
        return res
