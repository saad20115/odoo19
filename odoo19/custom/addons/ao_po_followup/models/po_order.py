# -*- coding: utf-8 -*-
import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PoOrder(models.Model):
    _name = 'po.order'
    _description = 'PO Order'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='PO',
        required=True,
        index=True,
        tracking=True,
        copy=False,
    )
    active = fields.Boolean(string='Active', default=True)
    document = fields.Binary(
        string='File',
        attachment=True,
        # Binary fields cannot use mail tracking (Odoo raises NotImplementedError).
    )
    document_filename = fields.Char(string='Filename')
    followup_id = fields.Many2one(
        'po.followup',
        string='PO Follow-up',
        ondelete='set null',
        copy=False,
        index=True,
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
        tracking=True,
    )
    received_from_accounting = fields.Boolean(
        string='Received from Accounting',
        default=False,
        copy=False,
        readonly=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Assigned To',
        tracking=True,
        index=True,
        domain="[('share', '=', False)]",
    )
    is_done = fields.Boolean(
        string='Done',
        default=False,
        tracking=True,
        help='Mark when the employee finished the final attachment process.',
    )
    status = fields.Selection(
        [
            ('unassigned', 'Unassigned'),
            ('assigned', 'Assigned'),
            ('done', 'Done'),
        ],
        string='Status',
        compute='_compute_status',
        store=True,
        index=True,
    )

    _sql_constraints = [
        ('po_order_name_uniq', 'unique(name)', 'A PO Order with this PO number already exists.'),
    ]

    @api.model
    def _clean_invoice_name(self, name):
        """Strip / from invoice numbers (INVM/2026/00218 -> INVM202600218)."""
        if not name:
            return name or ''
        cleaned = str(name).replace('/', '')
        return cleaned if cleaned and cleaned != '/' else ''

    @api.depends('user_id', 'is_done')
    def _compute_status(self):
        for record in self:
            if record.is_done:
                record.status = 'done'
            elif record.user_id:
                record.status = 'assigned'
            else:
                record.status = 'unassigned'

    @api.model
    def _recompute_status_for_all(self):
        """Fill status for rows created before the field existed."""
        records = self.with_context(active_test=False).search([])
        records._compute_status()
        return True

    @api.model
    def _fix_po_order_form_views(self):
        """Deactivate leftover old po.order form views so header buttons show."""
        keep = self.env.ref('ao_po_followup.view_po_order_form', raise_if_not_found=False)
        domain = [('model', '=', 'po.order'), ('type', '=', 'form')]
        views = self.env['ir.ui.view'].with_context(active_test=False).search(domain)
        for view in views:
            if keep and view.id == keep.id:
                view.write({'active': True, 'priority': 1})
            else:
                view.write({'active': False})
        return True

    def action_open_assign_wizard(self):
        """Open wizard to assign selected PO Orders to one user."""
        if not self:
            raise UserError(_('Select at least one PO Order.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assign User'),
            'res_model': 'po.order.assign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_ids': [(6, 0, self.ids)],
            },
        }

    def action_assign_to_me(self):
        """Assign only if free (or already mine). Safe if two users click together."""
        if not self:
            return True
        # Lock rows so the second concurrent click waits, then sees the first assignee
        self.env.cr.execute(
            "SELECT id, user_id FROM po_order WHERE id IN %s FOR UPDATE",
            (tuple(self.ids),),
        )
        locked = {row[0]: row[1] for row in self.env.cr.fetchall()}
        Users = self.env['res.users']
        for record in self:
            current_uid = locked.get(record.id)
            if current_uid and current_uid != self.env.user.id:
                raise UserError(_(
                    'PO %(po)s is already assigned to %(user)s.'
                ) % {
                    'po': record.name,
                    'user': Users.browse(current_uid).name,
                })
            record.write({
                'user_id': self.env.user.id,
                'is_done': False,
            })
        return True

    def action_mark_done(self):
        self.write({'is_done': True})
        return True

    def action_mark_todo(self):
        self.write({'is_done': False})
        return True

    def _post_invoice_to_chatter(self, invoice_name, document, document_filename):
        """Post invoice name and PDF into chatter (form hides these fields)."""
        self.ensure_one()
        body = _('Accounting invoice: %s') % (invoice_name or '-')
        attachments = []
        if document:
            filename = document_filename or ('%s.pdf' % (invoice_name or self.name or 'invoice'))
            raw = document
            if isinstance(raw, str):
                try:
                    raw = base64.b64decode(raw)
                except Exception:
                    raw = raw.encode('utf-8')
            attachments = [(filename, raw)]
        try:
            self.message_post(body=body, attachments=attachments)
        except Exception:
            # Do not fail the whole receive API if chatter/attachment posting fails.
            _logger.exception('Failed to post invoice PDF to PO Order chatter for %s', self.name)
            self.message_post(body=body)

    @api.model
    def create_from_accounting(self, vals):
        """Upsert PO Order from Accounting Send-to-Portal payload."""
        po_number = (vals.get('name') or vals.get('po_number') or '').strip()
        if not po_number:
            raise ValueError('po_number is required')

        invoice_name = self._clean_invoice_name(
            vals.get('remote_invoice_name') or vals.get('invoice_name')
        )
        document = vals.get('document')
        document_filename = vals.get('document_filename') or (
            '%s.pdf' % (invoice_name or po_number)
        )

        existing = self.with_context(active_test=False).search(
            [('name', '=', po_number)], limit=1
        )
        write_vals = {
            'name': po_number,
            'document': document,
            'document_filename': document_filename,
            'remote_invoice_id': vals.get('remote_invoice_id') or False,
            'remote_invoice_name': invoice_name or False,
            'received_from_accounting': True,
            'is_done': False,
            'active': True,
        }
        followup_id = vals.get('followup_id')
        if followup_id:
            write_vals['followup_id'] = int(followup_id)

        had_new_document = bool(document)
        if existing:
            if not write_vals.get('document'):
                write_vals.pop('document', None)
                write_vals.pop('document_filename', None)
                had_new_document = False
            existing.write(write_vals)
            record = existing
            record.message_post(body=_('Updated from Accounting Send to Portal.'))
        else:
            record = self.create(write_vals)
            record.message_post(body=_('Created from Accounting Send to Portal.'))

        if had_new_document or invoice_name:
            record._post_invoice_to_chatter(
                invoice_name,
                document if had_new_document else False,
                document_filename if had_new_document else False,
            )

        if record.followup_id:
            record.followup_id.mark_sent_to_portal(
                invoice_name=record.remote_invoice_name,
                invoice_id=record.remote_invoice_id,
            )
        elif followup_id:
            followup = self.env['po.followup'].browse(int(followup_id)).exists()
            if followup:
                followup.mark_sent_to_portal(
                    invoice_name=record.remote_invoice_name,
                    invoice_id=record.remote_invoice_id,
                )
        return record

    @api.model
    def archive_from_accounting(self, vals):
        """Archive PO Order + linked follow-up after Accounting Register Payment."""
        followup_id = int(vals.get('followup_id') or 0)
        po_number = (vals.get('po_number') or vals.get('name') or '').strip()
        invoice_id = int(vals.get('invoice_id') or vals.get('remote_invoice_id') or 0)

        Followup = self.env['po.followup'].with_context(active_test=False).sudo()
        Order = self.with_context(active_test=False).sudo()

        followups = Followup.browse()
        if followup_id:
            followups |= Followup.browse(followup_id).exists()
        if invoice_id:
            followups |= Followup.search([('remote_invoice_id', '=', invoice_id)])
        if po_number:
            followups |= Followup.search([('po_number', '=', po_number)])

        orders = Order.browse()
        if followups:
            orders |= Order.search([('followup_id', 'in', followups.ids)])
        if po_number:
            orders |= Order.search([('name', '=', po_number)])
        if invoice_id:
            orders |= Order.search([('remote_invoice_id', '=', invoice_id)])

        followups.archive_after_accounting_payment()
        for order in orders:
            if not order.active:
                continue
            order.write({'active': False})
            order.message_post(body=_(
                'Archived after Accounting Register Payment.'
            ))

        return {
            'followup_ids': followups.ids,
            'po_order_ids': orders.ids,
        }
