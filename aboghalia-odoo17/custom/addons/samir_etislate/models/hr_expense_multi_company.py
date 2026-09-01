# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployeeBase(models.AbstractModel):
    _inherit = 'hr.employee.base'

    def _search_filter_for_expense(self, operator, value):
        """Expense employee dropdown rules.

        - Users in ``group_expense_select_any_employee``: all employees
        - Everyone else: only their own employee record
        """
        assert operator == '=' and value, "Operation not supported"

        user = self.env.user
        if user.has_group('samir_etislate.group_expense_select_any_employee'):
            return [(1, '=', 1)]

        employee = user.employee_id
        if employee:
            return [('id', '=', employee.id)]
        return [('id', '=', 0)]


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _register_hook(self):
        """Fix global employee rule from hr_employee_transfer on registry load."""
        super()._register_hook()
        cr = self.env.cr
        cr.execute(
            """
            UPDATE ir_rule AS r
               SET domain_force = %s
              FROM ir_model AS m
             WHERE r.model_id = m.id
               AND m.model = 'hr.employee'
               AND r.name = 'Employee Multi Company Rule'
               AND r.domain_force LIKE %s
            """,
            (
                "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]",
                '%user.company_id%',
            ),
        )
        if cr.rowcount:
            self.env.registry.clear_cache()

    def _expense_can_skip_employee_rules(self):
        return (
            self.env.context.get('hr_expense_multi_company_employees')
            and self.env.user.has_group('samir_etislate.group_expense_select_any_employee')
        )

    @api.model
    def _expense_employee_sudo_env(self):
        """Bypass HR / multi-company record rules on the expense employee field."""
        if not self._expense_can_skip_employee_rules():
            return self
        company_ids = self.env['res.company'].sudo().search([]).ids
        return self.sudo().with_context(allowed_company_ids=company_ids)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        self = self._expense_employee_sudo_env()
        return super()._search(
            domain, offset=offset, limit=limit, order=order, access_rights_uid=access_rights_uid
        )

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        self = self._expense_employee_sudo_env()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs):
        self = self._expense_employee_sudo_env()
        return super().search_read(
            domain=domain, fields=fields, offset=offset, limit=limit, order=order, **read_kwargs
        )

    def read(self, fields=None, load='_classic_read'):
        self = self._expense_employee_sudo_env()
        return super(HrEmployee, self).read(fields=fields, load=load)

    def name_get(self):
        self = self._expense_employee_sudo_env()
        return super(HrEmployee, self).name_get()

    def check_access_rule(self, operation):
        # Allow reading any employee when picking on expense form (group only).
        if operation == 'read' and self._expense_can_skip_employee_rules():
            return
        return super().check_access_rule(operation)


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    def _expense_can_skip_employee_rules(self):
        return (
            self.env.context.get('hr_expense_multi_company_employees')
            and self.env.user.has_group('samir_etislate.group_expense_select_any_employee')
        )

    @api.model
    def _expense_employee_sudo_env(self):
        if not self._expense_can_skip_employee_rules():
            return self
        company_ids = self.env['res.company'].sudo().search([]).ids
        return self.sudo().with_context(allowed_company_ids=company_ids)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        self = self._expense_employee_sudo_env()
        return super()._search(
            domain, offset=offset, limit=limit, order=order, access_rights_uid=access_rights_uid
        )

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        self = self._expense_employee_sudo_env()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs):
        self = self._expense_employee_sudo_env()
        return super().search_read(
            domain=domain, fields=fields, offset=offset, limit=limit, order=order, **read_kwargs
        )

    def read(self, fields=None, load='_classic_read'):
        self = self._expense_employee_sudo_env()
        return super(HrEmployeePublic, self).read(fields=fields, load=load)

    def name_get(self):
        self = self._expense_employee_sudo_env()
        return super(HrEmployeePublic, self).name_get()

    def check_access_rule(self, operation):
        if operation == 'read' and self._expense_can_skip_employee_rules():
            return
        return super().check_access_rule(operation)


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    # Kept for upgrade safety if an old view arch still references it.
    can_select_any_employee = fields.Boolean(
        compute='_compute_can_select_any_employee',
    )
    employee_id = fields.Many2one(
        domain="[('filter_for_expense', '=', True)]",
        context={'hr_expense_multi_company_employees': True},
        check_company=False,
    )

    @api.depends_context('uid')
    def _compute_can_select_any_employee(self):
        can = self.env.user.has_group('samir_etislate.group_expense_select_any_employee')
        for expense in self:
            expense.can_select_any_employee = can

    @api.model
    def _default_employee_id(self):
        """Own employee if any; otherwise empty (no error)."""
        return (
            self.env.user.with_company(self.env.company).employee_id
            or self.env.user.employee_id
        )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'employee_id' in fields_list:
            employee = self._default_employee_id()
            res['employee_id'] = employee.id if employee else False
        return res

    @api.depends('company_id')
    def _compute_employee_id(self):
        """Set own employee when empty; leave empty if user has no employee."""
        if self.env.context.get('default_employee_id'):
            return
        for expense in self:
            if not expense.employee_id:
                expense.employee_id = (
                    self.env.user.with_company(expense.company_id).employee_id
                    or self.env.user.employee_id
                )

    @api.onchange('employee_id')
    def _onchange_employee_id_set_company(self):
        """Switch company only when that company has accounting (journals).

        شركات without a chart (e.g. جمال) keep the session company so Create Report
        keeps working with the current company's purchase journal.
        """
        company = self.employee_id.company_id
        if not company:
            return
        if self.env['hr.expense.sheet']._get_expense_journal_for_company(company):
            self.company_id = company

    def _get_default_expense_sheet_values(self):
        """Prefer a journal of the expense company; else keep session default."""
        values = super()._get_default_expense_sheet_values()
        Sheet = self.env['hr.expense.sheet']
        for vals in values:
            company = self.env['res.company'].browse(vals.get('company_id'))
            journal = Sheet._get_expense_journal_for_company(company)
            if journal:
                vals['employee_journal_id'] = journal.id
            else:
                # Company has no CoA/journals: use session company journal.
                session_journal = Sheet._get_expense_journal_for_company(self.env.company)
                if session_journal:
                    vals['employee_journal_id'] = session_journal.id
        return values


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    employee_id = fields.Many2one(
        domain="[('filter_for_expense', '=', True)]",
        context={'hr_expense_multi_company_employees': True},
        check_company=False,
    )
    # Allow session-company journals on sheets whose company has no CoA yet
    # (e.g. شركة م جمال) so users are not blocked by _check_company.
    employee_journal_id = fields.Many2one(check_company=False)
    journal_id = fields.Many2one(check_company=False)
    payment_method_line_id = fields.Many2one(check_company=False)

    @api.model
    def _get_expense_journal_for_company(self, company):
        """Prefer company expense journal, else first purchase journal of that company."""
        if not company:
            return self.env['account.journal']
        company = company.sudo() if len(company) == 1 else company.sudo()[:1]
        journal = company.expense_journal_id.sudo()
        if journal and journal.company_id == company:
            return journal
        return self.env['account.journal'].sudo().search([
            ('company_id', '=', company.id),
            ('type', '=', 'purchase'),
        ], limit=1)

    @api.model
    def _default_journal_id(self):
        default_company_id = self.env.context.get('default_company_id') or self.env.company.id
        company = self.env['res.company'].browse(default_company_id)
        journal = self._get_expense_journal_for_company(company)
        if not journal:
            journal = self._get_expense_journal_for_company(self.env.company)
        return journal.id if journal else False

    def _force_employee_journal_from_company(self, vals, company=None):
        """Use company journal when it exists; otherwise keep session journal."""
        company = company or self.env['res.company'].browse(vals.get('company_id'))
        if not company:
            return vals
        company = company[:1]
        vals = dict(vals)
        journal = self._get_expense_journal_for_company(company)
        if not journal:
            journal = self._get_expense_journal_for_company(self.env.company)
        if journal:
            vals['employee_journal_id'] = journal.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._force_employee_journal_from_company(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('skip_expense_journal_company_sync'):
            return super().write(vals)
        vals = dict(vals)
        if vals.get('company_id'):
            vals = self._force_employee_journal_from_company(vals)
        return super().write(vals)

    @api.onchange('company_id')
    def _onchange_company_id_reset_journals(self):
        if not self.company_id:
            return
        journal = self._get_expense_journal_for_company(self.company_id)
        if not journal:
            journal = self._get_expense_journal_for_company(self.env.company)
        self.employee_journal_id = journal
