# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _default_get_portal_redirect_url(self):
        """Helper to compute portal redirect URL for self service portal."""
        self.ensure_one()
        if not self.has_group('base.group_system'):
            return '/portal/self-service'
        return '/web'
