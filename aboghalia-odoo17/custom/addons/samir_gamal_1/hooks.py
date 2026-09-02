# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

MODULE = 'samir_gamal_1'
LEFTOVER_MENU_MODULES = ('samir', 'samir_gamal')


def cleanup_leftover_employee_request_ui(env):
    """Hide leftover views/menus from uninstalled samir / samir_gamal copies.

    Live still has old employee.request views with lower IDs than samir_gamal_1,
    so Odoo was showing that older UI instead of the beta form (WhatsApp,
    partner phone, request topic, archive).
    """
    cr = env.cr
    cr.execute(
        """
        UPDATE ir_ui_view v
           SET active = false
         WHERE v.active = true
           AND v.model IN (
               'employee.request',
               'employee.request.analysis',
               'employee.request.type',
               'employee.request.tag'
           )
           AND NOT EXISTS (
               SELECT 1
                 FROM ir_model_data imd
                WHERE imd.model = 'ir.ui.view'
                  AND imd.res_id = v.id
                  AND imd.module = %s
           )
     RETURNING v.id, v.name
        """,
        [MODULE],
    )
    views = cr.fetchall()
    if views:
        _logger.info(
            "samir_gamal_1: deactivated leftover employee.request views: %s",
            views,
        )

    cr.execute(
        """
        UPDATE ir_ui_menu m
           SET active = false
         WHERE m.active = true
           AND EXISTS (
               SELECT 1
                 FROM ir_model_data imd
                WHERE imd.model = 'ir.ui.menu'
                  AND imd.res_id = m.id
                  AND imd.module = ANY(%s)
                  AND imd.name = 'menu_employee_request'
           )
     RETURNING m.id
        """,
        [list(LEFTOVER_MENU_MODULES)],
    )
    menus = cr.fetchall()
    if menus:
        _logger.info(
            "samir_gamal_1: deactivated leftover الاتصالات الإدارية menus: %s",
            menus,
        )


def post_init_hook(env_or_cr, registry=None):
    # This Odoo 17 tree calls hooks with env; some addons still use (cr, registry).
    if registry is None and hasattr(env_or_cr, 'cr'):
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    cleanup_leftover_employee_request_ui(env)
