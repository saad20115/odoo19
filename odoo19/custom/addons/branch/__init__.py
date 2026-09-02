# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from . import models
from . import reports
from . import wizard
from . import controllers
# from .hooks import post_init_hook
from odoo import api, fields, SUPERUSER_ID, _


def _uninstall_hook(cr, registry):
    print("hi")
