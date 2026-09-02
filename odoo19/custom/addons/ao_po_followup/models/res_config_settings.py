# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    po_accounting_url = fields.Char(
        string='Accounting Odoo URL',
        config_parameter='ao_po_followup.accounting_url',
        help='Base URL of Accounting Aboghalia, e.g. https://host:8022',
    )
    po_accounting_db = fields.Char(
        string='Accounting Database',
        config_parameter='ao_po_followup.accounting_db',
    )
    po_accounting_login = fields.Char(
        string='Accounting API Login',
        config_parameter='ao_po_followup.accounting_login',
    )
    po_accounting_password = fields.Char(
        string='Accounting API Password',
        config_parameter='ao_po_followup.accounting_password',
    )
    po_order_api_login = fields.Char(
        string='Incoming PO Order API Login',
        config_parameter='ao_po_followup.po_order_api_login',
        help='Basic Auth login Accounting uses for Send to Portal.',
    )
    po_order_api_password = fields.Char(
        string='Incoming PO Order API Password',
        config_parameter='ao_po_followup.po_order_api_password',
    )

    def action_set_po_followup_home_for_users(self):
        """Force PO Follow-up home action for all users in the PO Follow-up group."""
        self.ensure_one()
        group = self.env.ref('ao_po_followup.group_po_followup_user')
        users = self.env['res.users'].search([('groups_id', 'in', group.id)])
        users._ao_po_set_home_action_if_needed(force=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Home action updated',
                'message': 'PO Follow-up is now the home screen for %s user(s).' % len(users),
                'type': 'success',
                'sticky': False,
            },
        }
