# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


YES_NO_SELECTION = [
    ('yes', 'Yes'),
    ('no', 'No'),
]

ASSIGN_STATE_SELECTION = [
    ('draft', 'Draft'),
    ('assigned', 'Assigned to Accounting'),
    ('sent_to_portal', 'Sent to Portal'),
]


class PoFollowup(models.Model):
    _name = 'po.followup'
    _description = 'PO Follow-up'
    _order = 'sequence desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(
        string='#',
        default=lambda self: self._default_sequence(),
        copy=False,
    )
    state = fields.Selection(
        ASSIGN_STATE_SELECTION,
        string='Status',
        default='draft',
        tracking=True,
        index=True,
        copy=False,
    )
    remote_invoice_id = fields.Integer(
        string='Remote Invoice ID',
        copy=False,
        readonly=True,
    )
    remote_invoice_name = fields.Char(
        string='Remote Invoice',
        copy=False,
        readonly=True,
    )
    assigned_date = fields.Datetime(
        string='Assigned Date',
        copy=False,
        readonly=True,
    )
    assign_error = fields.Text(
        string='Assign Error',
        copy=False,
        readonly=True,
    )
    po_number = fields.Char(string='PO', tracking=True, index=True)
    work_order_number = fields.Char(
        string='Work Order Number',
        tracking=True,
        index=True,
        copy=False,
    )
    contractor_id = fields.Many2one(
        'po.contractor',
        string='Contractor',
        tracking=True,
        ondelete='restrict',
    )
    office_id = fields.Many2one(
        'po.office',
        string='Office',
        tracking=True,
        ondelete='restrict',
    )
    entity_id = fields.Many2one(
        'po.entity',
        string='Entity',
        tracking=True,
        ondelete='restrict',
    )
    description = fields.Char(string='Description', tracking=True)
    technical_files_uploaded = fields.Selection(
        YES_NO_SELECTION,
        string='Technical Files Cloud Upload',
        default='no',
        tracking=True,
    )
    tax_invoice = fields.Selection(
        YES_NO_SELECTION,
        string='Tax Invoice',
        default='no',
        tracking=True,
    )
    invoice_number = fields.Char(string='Invoice Number', tracking=True)
    invoice_date = fields.Date(string='Invoice Date', tracking=True)
    estimation_date = fields.Date(string='Estimation Date', tracking=True)
    uploaded_to_system = fields.Selection(
        YES_NO_SELECTION,
        string='Uploaded to System',
        default='no',
        tracking=True,
    )
    expenditure = fields.Float(
        string='Expenditure',
        digits=(16, 2),
        tracking=True,
    )
    value = fields.Float(
        string='Value',
        digits=(16, 2),
        tracking=True,
    )
    value_with_tax = fields.Float(
        string='Value with Tax',
        digits=(16, 2),
        compute='_compute_value_with_tax',
        store=True,
        help='Automatically calculated as Value + 15% tax.',
    )
    attention = fields.Boolean(
        string='Attention',
        help='Highlight this row (e.g. needs follow-up).',
        default=False,
    )
    is_fully_done = fields.Boolean(
        string='All Triple Yes',
        compute='_compute_is_fully_done',
        store=True,
        index=True,
        help='Checked when Cloud Files, Tax Invoice, and On System are all Yes.',
    )

    @api.model
    def _default_sequence(self):
        last = self.search([], order='sequence desc, id desc', limit=1)
        return (last.sequence or 0) + 1 if last else 1

    @api.depends('po_number', 'work_order_number')
    def _compute_name(self):
        for record in self:
            parts = [p for p in (record.po_number, record.work_order_number) if p]
            record.name = ' / '.join(parts) if parts else 'New PO'

    @api.depends('value')
    def _compute_value_with_tax(self):
        for record in self:
            record.value_with_tax = round((record.value or 0.0) * 1.15, 2)

    @api.model
    def _recompute_value_with_tax_all(self):
        """Recompute stored Value + Tax for existing rows (runs on module upgrade)."""
        records = self.with_context(active_test=False).search([])
        if records:
            records._compute_value_with_tax()
        return True

    @api.depends('technical_files_uploaded', 'tax_invoice', 'uploaded_to_system')
    def _compute_is_fully_done(self):
        for record in self:
            record.is_fully_done = (
                record.technical_files_uploaded == 'yes'
                and record.tax_invoice == 'yes'
                and record.uploaded_to_system == 'yes'
            )

    @api.constrains('work_order_number')
    def _check_work_order_number_unique(self):
        for record in self:
            number = (record.work_order_number or '').strip()
            if not number:
                continue
            duplicate = self.search([
                ('work_order_number', '=', number),
                ('id', '!=', record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Work Order Number "%(number)s" already exists on PO %(po)s.'
                ) % {
                    'number': number,
                    'po': duplicate.po_number or duplicate.display_name,
                })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sequence'):
                vals['sequence'] = self._default_sequence()
            if vals.get('work_order_number'):
                vals['work_order_number'] = vals['work_order_number'].strip()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('work_order_number'):
            vals = dict(vals, work_order_number=vals['work_order_number'].strip())
        return super().write(vals)

    @api.model
    def get_dashboard_kpis(self, domain=None):
        """KPIs matching Google Sheet: totals + completion ratios by count."""
        domain = domain or []
        records = self.search(domain)

        po_count = len(records)
        po_value = sum(records.mapped('value'))

        # Invoicing = tax invoice done (تم)
        invoiced = records.filtered(lambda r: r.tax_invoice == 'yes')
        invoicing_count = len(invoiced)
        # Sheet "اجمالي الفوترة / القيمة" uses قيمة of invoiced rows
        invoicing_value = sum(invoiced.mapped('value'))

        expended = records.filtered(lambda r: r.expenditure)
        expenditure_count = len(expended)
        expenditure_value = sum(expended.mapped('expenditure'))

        invoicing_percentage = (invoicing_count / po_count * 100.0) if po_count else 0.0
        expenditure_percentage = (expenditure_count / po_count * 100.0) if po_count else 0.0

        return {
            'po_count': po_count,
            'po_value': po_value,
            'invoicing_count': invoicing_count,
            'invoicing_value': invoicing_value,
            'expenditure_count': expenditure_count,
            'expenditure_value': expenditure_value,
            'invoicing_percentage': round(invoicing_percentage, 2),
            'expenditure_percentage': round(expenditure_percentage, 2),
        }

    def _prepare_accounting_payload_item(self):
        self.ensure_one()
        untaxed = self.value or 0.0
        return {
            'followup_id': self.id,
            'po_number': self.po_number or '',
            'work_order_number': (self.work_order_number or '').strip(),
            'contractor_name': self.contractor_id.name or '',
            'office_name': self.office_id.name or '',
            'entity_name': self.entity_id.name or '',
            'description': self.description or self.name or '',
            'amount': untaxed,
            'amount_untaxed': untaxed,
            'value': untaxed,
            'estimation_date': (
                fields.Date.to_string(self.estimation_date) if self.estimation_date else False
            ),
            'invoice_date': fields.Date.to_string(self.invoice_date) if self.invoice_date else False,
            'invoice_number': self.invoice_number or '',
        }

    def action_assign_to_accounting(self):
        """Send selected draft POs to Accounting Odoo as draft invoices."""
        records = self.filtered(lambda r: r.state == 'draft')
        if not records:
            raise UserError(_('Select draft PO lines that are not already assigned.'))

        missing_po = records.filtered(lambda r: not r.po_number)
        if missing_po:
            raise UserError(_('Every selected line must have a PO number.'))

        missing_wo = records.filtered(lambda r: not (r.work_order_number or '').strip())
        if missing_wo:
            details = '\n'.join(
                '#%(seq)s — PO %(po)s (id %(id)s)' % {
                    'seq': rec.sequence,
                    'po': rec.po_number or '-',
                    'id': rec.id,
                }
                for rec in missing_wo
            )
            raise UserError(_(
                'Work Order Number is required before Assign to Accounting.\n'
                'Missing on:\n%s'
            ) % details)

        items = [rec._prepare_accounting_payload_item() for rec in records]
        payload = self.env['po.accounting.api'].create_draft_invoices(items)
        results = {str(row.get('followup_id')): row for row in (payload.get('results') or [])}

        success = self.env['po.followup']
        errors = []
        now = fields.Datetime.now()
        for record in records:
            row = results.get(str(record.id)) or {}
            if row.get('ok'):
                invoice_name = self.env['po.order']._clean_invoice_name(
                    row.get('invoice_name')
                )
                record.write({
                    'state': 'assigned',
                    'remote_invoice_id': row.get('invoice_id') or False,
                    'remote_invoice_name': invoice_name or False,
                    'assigned_date': now,
                    'assign_error': False,
                })
                record.message_post(body=_(
                    'Assigned to Accounting. Remote invoice: %s'
                ) % (invoice_name or row.get('invoice_id')))
                success |= record
            else:
                message = row.get('error') or _('Unknown error')
                record.write({'assign_error': message})
                errors.append('%s: %s' % (record.po_number, message))

        if errors and not success:
            raise UserError(_('Assignment failed:\n%s') % '\n'.join(errors))
        if errors:
            raise UserError(_(
                '%(ok)s assigned successfully.\nFailed:\n%(err)s'
            ) % {'ok': len(success), 'err': '\n'.join(errors)})
        return True

    def mark_sent_to_portal(self, invoice_name=None, invoice_id=None):
        """Called when Accounting pushes the finished PO back to Portal."""
        cleaned = self.env['po.order']._clean_invoice_name(invoice_name)
        for record in self:
            vals = {'state': 'sent_to_portal'}
            if invoice_id:
                vals['remote_invoice_id'] = invoice_id
            if cleaned:
                vals['remote_invoice_name'] = cleaned
            record.write(vals)
            record.message_post(body=_(
                'Accounting sent this PO to Portal PO Order (invoice: %s).'
            ) % (cleaned or invoice_id or '-'))
        return True

    def archive_after_accounting_payment(self):
        """Archive follow-up rows after Accounting Register Payment."""
        for record in self.with_context(active_test=False):
            if not record.active:
                continue
            record.write({'active': False})
            record.message_post(body=_(
                'Archived after Accounting Register Payment.'
            ))
        return True
