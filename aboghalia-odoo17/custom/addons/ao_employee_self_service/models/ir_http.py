# -*- coding: utf-8 -*-
import os
from odoo import models

# Ensure node and rtlcss binary paths are present in system PATH for Odoo asset compilation
node_bin_path = '/home/saad/abighalia/.node/node-v20.17.0-linux-x64/bin'
local_bin_path = '/home/saad/snap/antigravity/5/.local/bin'

current_path = os.environ.get('PATH', '')
if node_bin_path not in current_path:
    os.environ['PATH'] = f"{node_bin_path}:{local_bin_path}:{current_path}"

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def webclient_rendering_context(self):
        res = super().webclient_rendering_context()
        lang_code = self.env.user.lang or 'ar_001'
        direction = self.env['res.lang']._lang_get_direction(lang_code) or 'rtl'
        res['html_data'] = {
            'lang': lang_code.replace('_', '-'),
            'dir': direction,
        }
        return res
