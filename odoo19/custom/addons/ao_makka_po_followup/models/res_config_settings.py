# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    makka_po_accounting_url = fields.Char(
        string='Accounting Odoo URL',
        config_parameter='ao_makka_po_followup.accounting_url',
        help='Base URL of Accounting Aboghalia, e.g. https://host:8022',
    )
    makka_po_accounting_db = fields.Char(
        string='Accounting Database',
        config_parameter='ao_makka_po_followup.accounting_db',
    )
    makka_po_accounting_login = fields.Char(
        string='Accounting API Login',
        config_parameter='ao_makka_po_followup.accounting_login',
    )
    makka_po_accounting_password = fields.Char(
        string='Accounting API Password',
        config_parameter='ao_makka_po_followup.accounting_password',
    )
    makka_po_order_api_login = fields.Char(
        string='Incoming Makka PO Order API Login',
        config_parameter='ao_makka_po_followup.po_order_api_login',
        help='Basic Auth login Accounting uses for Send to Portal.',
    )
    makka_po_order_api_password = fields.Char(
        string='Incoming Makka PO Order API Password',
        config_parameter='ao_makka_po_followup.po_order_api_password',
    )

    def action_test_makka_accounting_connection(self):
        """Verify Accounting URL + Incoming API credentials (auth only)."""
        self.ensure_one()
        # Persist current form values before testing.
        self.set_values()
        try:
            # Empty payload: auth runs first; "Expected non-empty items" means credentials OK.
            self.env['makka.po.accounting.api'].create_draft_invoices([])
            message = _('Connected successfully.')
            notif_type = 'success'
        except UserError as exc:
            text = str(exc)
            if 'Expected non-empty' in text or 'non-empty items' in text:
                message = _(
                    'Credentials OK. Accounting accepted login/password for '
                    '/api/makka_unified_contract/invoices.'
                )
                notif_type = 'success'
            else:
                message = text
                notif_type = 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Accounting API Test'),
                'message': message,
                'type': notif_type,
                'sticky': notif_type == 'danger',
            },
        }

    def action_set_makka_po_followup_home_for_users(self):
        """Force PO Follow-up Makka home action for all users in the PO Follow-up Makka group."""
        self.ensure_one()
        group = self.env.ref('ao_makka_po_followup.group_makka_po_followup_user')
        users = self.env['res.users'].search([('groups_id', 'in', group.id)])
        users._ao_makka_po_set_home_action_if_needed(force=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Home action updated',
                'message': 'PO Follow-up Makka is now the home screen for %s user(s).' % len(users),
                'type': 'success',
                'sticky': False,
            },
        }
