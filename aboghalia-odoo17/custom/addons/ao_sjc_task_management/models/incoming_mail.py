# -*- coding: utf-8 -*-
from odoo import fields, models


class IncomingMail(models.Model):
    _inherit = 'incoming.mail'

    sjc_due_date = fields.Date(
        string='SJC Due Date',
        tracking=True,
        help='Dashboard overdue date. If empty, received date is used.',
    )
    sjc_assigned_by_id = fields.Many2one(
        'res.users',
        string='Last Assigned By',
        tracking=True,
        index=True,
        help='Last inbox user who assigned this email to an employee.',
    )
