# -*- coding: utf-8 -*-
from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_ao_fix_inaccessible_home_actions(self):
        """Replace inaccessible Home Actions with Discuss for internal users."""
        self.ensure_one()
        fixed = self.env['res.users']._ao_fix_inaccessible_home_actions(force_discuss=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Home actions fixed',
                'message': (
                    '%s user(s) had an inaccessible Home Action; '
                    'set to Discuss.'
                ) % fixed,
                'type': 'success',
                'sticky': False,
            },
        }
