# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import AccessError

# Models that must never be used as Home Action for non-admin users.
_AO_UNSAFE_HOME_MODELS = {
    'ir.actions.server',
    'ir.cron',
    'ir.ui.view',
    'ir.model',
    'ir.model.access',
    'ir.rule',
    'ir.module.module',
    'ir.config_parameter',
    'base.automation',
    'base.automation.line',
}


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _ao_find_related_employees(self):
        """Find employees without using company-filtered employee_ids.

        Match by user_id OR work_email == login (live often misses user_id link).
        """
        self.ensure_one()
        Employee = self.env['hr.employee'].sudo()
        domain = [
            ('active', '=', True),
            ('company_id', '!=', False),
            '|',
            ('user_id', '=', self.id),
            ('work_email', '=ilike', (self.login or '').strip()),
        ]
        return Employee.search(domain)

    def _ao_get_employee_company(self):
        """Company from Employee form (hr.employee.company_id)."""
        self.ensure_one()
        employees = self._ao_find_related_employees()
        if not employees:
            return self.env['res.company']
        allowed = employees.filtered(lambda e: e.company_id in self.company_ids)
        pick = allowed or employees
        companies = pick.mapped('company_id')
        if len(companies) == 1:
            return companies
        others = companies.filtered(lambda c: c != self.company_id)
        if len(others) == 1:
            return others
        return pick[0].company_id

    def _ao_get_login_company(self):
        """Login company: Employee form first, else user Default Company."""
        self.ensure_one()
        return self._ao_get_employee_company() or self.company_id

    def _ao_apply_login_company(self):
        """Sync user.company_id from Employee company; return company for cookie."""
        self.ensure_one()
        company = self._ao_get_login_company()
        if not company:
            return company
        # Ensure employee is linked to this user when matched by email only.
        employees = self._ao_find_related_employees().filtered(
            lambda e: e.company_id == company and not e.user_id
        )
        for emp in employees:
            try:
                emp.write({'user_id': self.id})
            except Exception:
                break
        vals = {}
        if company not in self.company_ids:
            vals['company_ids'] = [(4, company.id)]
        if self.company_id != company:
            vals['company_id'] = company.id
        if vals:
            self.sudo().with_context(skip_ao_po_home_action=True).write(vals)
        return company

    def _ao_fallback_home_action(self):
        return self.env.ref('mail.action_discuss', raise_if_not_found=False)

    def _ao_is_unsafe_home_model(self, res_model):
        if not res_model:
            return False
        if self.has_group('base.group_system'):
            return False
        if res_model in _AO_UNSAFE_HOME_MODELS:
            return True
        if res_model.startswith('ir.'):
            return True
        return False

    def _ao_user_can_open_action(self, action):
        self.ensure_one()
        if not action:
            return False
        try:
            concrete = self.env[action.type].sudo().browse(action.id).exists()
            if not concrete:
                return False
            if concrete.groups_id and not (concrete.groups_id & self.groups_id):
                return False
            if action.type in ('ir.actions.server', 'ir.actions.report') and not self.has_group('base.group_system'):
                return False
            res_model = getattr(concrete, 'res_model', None) or False
            if self._ao_is_unsafe_home_model(res_model):
                return False
            if not res_model:
                return True
            user_env = self.env(user=self.id)
            if res_model not in user_env:
                return False
            Model = user_env[res_model]
            Model.check_access_rights('read')
            Model.search([], limit=1)
            return True
        except AccessError:
            return False
        except Exception:
            return False

    def _ao_safe_home_action_id(self):
        """Prefer current Home Action only if safe; else Discuss."""
        self.ensure_one()
        fallback = self._ao_fallback_home_action()
        action = self.action_id
        if action and self._ao_user_can_open_action(action):
            return action.id
        if not fallback:
            return False
        if not action or action.id != fallback.id:
            try:
                self.sudo().with_context(skip_ao_po_home_action=True).write({
                    'action_id': fallback.id,
                })
            except Exception:
                pass
        return fallback.id

    @api.model
    def _ao_fix_inaccessible_home_actions(self, force_discuss=True):
        users = self.search([('share', '=', False)])
        fallback = self.env.ref('mail.action_discuss', raise_if_not_found=False) if force_discuss else False
        fixed = 0
        for user in users:
            if user.has_group('base.group_system'):
                continue
            if not fallback:
                continue
            if user.action_id.id == fallback.id:
                continue
            if user.action_id and user._ao_user_can_open_action(user.action_id):
                concrete = user.env[user.action_id.type].sudo().browse(user.action_id.id)
                res_model = getattr(concrete, 'res_model', None)
                if res_model and not user._ao_is_unsafe_home_model(res_model):
                    continue
            user.sudo().with_context(skip_ao_po_home_action=True).write({
                'action_id': fallback.id,
            })
            fixed += 1
        return fixed
