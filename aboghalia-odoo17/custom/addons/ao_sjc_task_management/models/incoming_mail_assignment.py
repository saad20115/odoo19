# -*- coding: utf-8 -*-
from odoo import fields, models


class IncomingMailAssignment(models.Model):
    _name = 'incoming.mail.assignment'
    _description = 'Incoming Mail Assignment Log'
    _order = 'assigned_date desc, id desc'

    mail_id = fields.Many2one(
        'incoming.mail',
        string='Incoming Mail',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Assignee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    assigned_by_id = fields.Many2one(
        'res.users',
        string='Assigned By',
        required=True,
        ondelete='restrict',
        index=True,
    )
    assigned_date = fields.Datetime(
        string='Assigned On',
        default=fields.Datetime.now,
        required=True,
    )
