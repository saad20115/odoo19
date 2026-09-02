# -*- coding: utf-8 -*-
"""HR-imported leave balances for the Leaves PWA."""
import base64
import csv
import io
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

NAME_HEADERS = frozenset({
    'name', 'employee', 'employee_name', 'employee name', 'emp_name',
    'اسم الموظف', 'الموظف', 'اسم', 'name_ar',
})
ID_HEADERS = frozenset({'employee_id', 'id', 'emp_id', 'معرف', 'رقم الموظف'})
REMAINING_HEADERS = frozenset({
    'remaining', 'remaining_days', 'days', 'balance', 'remaining days',
    'الرصيد', 'المتبقي', 'الأيام المتبقية', 'ايام متبقية', 'رصيد',
})


class LeavePwaEmployeeBalance(models.Model):
    _name = 'leave.pwa.employee.balance'
    _description = 'PWA Employee Leave Balance (HR Import)'
    _order = 'year desc, employee_id'
    _rec_name = 'display_name'

    employee_id = fields.Many2one(
        'hr.employee', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(
        'res.company', related='employee_id.company_id', store=True, readonly=True,
    )
    year = fields.Integer(required=True, index=True)
    remaining_days = fields.Float(
        string='Remaining Days',
        digits=(16, 2),
        required=True,
        help='Remaining paid leave days as recorded by HR at import time.',
    )
    effective_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        help='Balance is valid from this date forward for the rest of the year.',
    )
    import_id = fields.Many2one(
        'leave.pwa.balance.import', string='Import Batch', ondelete='set null',
    )
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    _sql_constraints = [
        (
            'employee_year_uniq',
            'unique(employee_id, year)',
            'Only one balance record per employee per calendar year is allowed.',
        ),
    ]

    @api.depends('employee_id', 'year', 'remaining_days')
    def _compute_display_name(self):
        for rec in self:
            emp = rec.employee_id.name or '?'
            rec.display_name = f'{emp} — {rec.year} ({rec.remaining_days:.2f} days)'

    @api.model
    def get_active_for_employee(self, employee, year):
        """Return the active HR balance override for an employee/year, if any."""
        if not employee:
            return self.browse()
        return self.sudo().search([
            ('employee_id', '=', employee.id),
            ('year', '=', year),
            ('active', '=', True),
        ], limit=1)


class LeavePwaBalanceImportLine(models.Model):
    _name = 'leave.pwa.balance.import.line'
    _description = 'PWA Balance Import Line'
    _order = 'row_number, id'

    import_id = fields.Many2one(
        'leave.pwa.balance.import', required=True, ondelete='cascade', index=True,
    )
    row_number = fields.Integer(string='Row #')
    raw_name = fields.Char(string='Employee (file)')
    raw_remaining = fields.Char(string='Remaining (file)')
    remaining_days = fields.Float(digits=(16, 2))
    employee_id = fields.Many2one('hr.employee', string='Matched Employee')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('matched', 'Matched'),
        ('not_found', 'Employee Not Found'),
        ('invalid', 'Invalid Data'),
        ('duplicate', 'Duplicate in File'),
    ], default='pending', required=True)
    message = fields.Char()


class LeavePwaBalanceImport(models.Model):
    _name = 'leave.pwa.balance.import'
    _description = 'PWA Balance Import'
    _order = 'create_date desc, id desc'

    name = fields.Char(default='New', required=True, copy=False)
    year = fields.Integer(
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
    )
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )
    effective_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        help='Imported balances apply from this date for the mobile app.',
    )
    file_data = fields.Binary(string='Balance File', attachment=True)
    filename = fields.Char()
    line_ids = fields.One2many(
        'leave.pwa.balance.import.line', 'import_id', string='Lines',
    )
    log = fields.Text(readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('parsed', 'Parsed'),
        ('done', 'Applied'),
        ('error', 'Error'),
    ], default='draft', required=True, copy=False)
    matched_count = fields.Integer(compute='_compute_counts')
    error_count = fields.Integer(compute='_compute_counts')
    line_count = fields.Integer(compute='_compute_counts')

    @api.depends('line_ids', 'line_ids.state')
    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.matched_count = len(rec.line_ids.filtered(lambda l: l.state == 'matched'))
            rec.error_count = len(rec.line_ids.filtered(
                lambda l: l.state in ('not_found', 'invalid', 'duplicate')
            ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'leave.pwa.balance.import'
                ) or _('Balance Import')
        return super().create(vals_list)

    def _append_log(self, message):
        self.ensure_one()
        stamp = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f'[{stamp}] {message}'
        self.log = (self.log + '\n' + line) if self.log else line

    @staticmethod
    def _normalize_header(value):
        text = (value or '').strip().lower()
        text = re.sub(r'\s+', ' ', text)
        return text

    @classmethod
    def _detect_columns(cls, headers):
        name_col = id_col = remaining_col = None
        for idx, header in enumerate(headers):
            norm = cls._normalize_header(header)
            if norm in ID_HEADERS:
                id_col = idx
            elif norm in NAME_HEADERS:
                name_col = idx
            elif norm in REMAINING_HEADERS:
                remaining_col = idx
        if remaining_col is None and len(headers) >= 2:
            remaining_col = 1
        if name_col is None and id_col is None and headers:
            name_col = 0
        return name_col, id_col, remaining_col

    def _match_employee(self, raw_name, raw_id):
        Employee = self.env['hr.employee'].sudo()
        company = self.company_id
        domain = []
        if company:
            domain.append(('company_id', 'in', [False, company.id]))

        if raw_id:
            raw_id = str(raw_id).strip()
            if raw_id.isdigit():
                employee = Employee.browse(int(raw_id))
                if employee.exists():
                    if company and employee.company_id and employee.company_id != company:
                        return employee.browse(), _('Employee belongs to another company.')
                    return employee, False

        name = (raw_name or '').strip()
        if not name:
            return Employee.browse(), _('Missing employee name or ID.')

        exact = Employee.search(domain + [('name', '=ilike', name)])
        if len(exact) == 1:
            return exact, False
        if len(exact) > 1:
            return Employee.browse(), _('Multiple employees match this name.')

        partial = Employee.search(domain + [('name', 'ilike', name)], limit=2)
        if len(partial) == 1:
            return partial, False
        if len(partial) > 1:
            return Employee.browse(), _('Multiple employees match this name.')

        return Employee.browse(), _('No employee found.')

    def _parse_remaining(self, raw_value):
        text = (raw_value or '').strip()
        if not text:
            return None, _('Missing remaining days value.')
        text = text.replace(',', '.')
        try:
            value = float(text)
        except ValueError:
            return None, _('Invalid number: %s') % raw_value
        if value < 0:
            return None, _('Remaining days cannot be negative.')
        return value, False

    def _read_csv_rows(self, content_bytes):
        for encoding in ('utf-8-sig', 'utf-8', 'cp1256', 'latin-1'):
            try:
                text = content_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                text = None
        if text is None:
            raise UserError(_('Could not decode the uploaded file. Save it as UTF-8 CSV.'))

        sample = text[:2048]
        try:
            dialect = csv.Sniffer().has_header(sample) and csv.Sniffer().sniff(sample) or csv.excel
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(io.StringIO(text), dialect)
        rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not rows:
            raise UserError(_('The uploaded file is empty.'))
        return rows

    def action_parse_file(self):
        for rec in self:
            if not rec.file_data:
                raise UserError(_('Upload a CSV file first.'))
            content = base64.b64decode(rec.file_data)
            rows = rec._read_csv_rows(content)
            headers = [rec._normalize_header(cell) for cell in rows[0]]
            has_named_headers = any(
                h in NAME_HEADERS | ID_HEADERS | REMAINING_HEADERS for h in headers
            )
            data_rows = rows[1:] if has_named_headers else rows
            name_col, id_col, remaining_col = rec._detect_columns(rows[0] if has_named_headers else [])

            rec.line_ids.unlink()
            line_vals = []
            seen_employees = set()
            row_number = 0

            for row in data_rows:
                row_number += 1
                raw_name = row[name_col].strip() if name_col is not None and name_col < len(row) else ''
                raw_id = row[id_col].strip() if id_col is not None and id_col < len(row) else ''
                raw_remaining = (
                    row[remaining_col].strip()
                    if remaining_col is not None and remaining_col < len(row)
                    else ''
                )

                remaining_days, remaining_err = rec._parse_remaining(raw_remaining)
                employee, match_err = rec._match_employee(raw_name, raw_id)

                state = 'pending'
                message = False
                if remaining_err:
                    state = 'invalid'
                    message = remaining_err
                elif match_err:
                    state = 'not_found' if 'No employee' in match_err or 'Multiple' in match_err else 'invalid'
                    message = match_err
                elif employee:
                    key = employee.id
                    if key in seen_employees:
                        state = 'duplicate'
                        message = _('Duplicate row for the same employee.')
                    else:
                        seen_employees.add(key)
                        state = 'matched'
                        message = _('Ready to apply.')

                line_vals.append({
                    'import_id': rec.id,
                    'row_number': row_number,
                    'raw_name': raw_name or raw_id,
                    'raw_remaining': raw_remaining,
                    'remaining_days': remaining_days or 0.0,
                    'employee_id': employee.id if employee and state == 'matched' else False,
                    'state': state,
                    'message': message,
                })

            if line_vals:
                self.env['leave.pwa.balance.import.line'].create(line_vals)

            matched = len([l for l in line_vals if l['state'] == 'matched'])
            errors = len(line_vals) - matched
            rec._append_log(_('Parsed %s row(s): %s matched, %s with issues.') % (
                len(line_vals), matched, errors,
            ))
            rec.state = 'parsed' if line_vals else 'error'
        return True

    def action_apply(self):
        Balance = self.env['leave.pwa.employee.balance'].sudo()
        for rec in self:
            if rec.state not in ('parsed', 'error'):
                raise UserError(_('Parse the file before applying.'))
            matched_lines = rec.line_ids.filtered(lambda l: l.state == 'matched' and l.employee_id)
            if not matched_lines:
                raise UserError(_('No matched employees to apply.'))

            applied = 0
            for line in matched_lines:
                existing = Balance.search([
                    ('employee_id', '=', line.employee_id.id),
                    ('year', '=', rec.year),
                ], limit=1)
                vals = {
                    'employee_id': line.employee_id.id,
                    'year': rec.year,
                    'remaining_days': line.remaining_days,
                    'effective_date': rec.effective_date,
                    'import_id': rec.id,
                    'active': True,
                }
                if existing:
                    existing.write(vals)
                else:
                    Balance.create(vals)
                applied += 1

            rec._append_log(_('Applied balances for %s employee(s).') % applied)
            rec.state = 'done'
        return True

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
        return True
