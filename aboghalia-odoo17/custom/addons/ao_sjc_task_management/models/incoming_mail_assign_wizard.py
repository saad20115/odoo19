# -*- coding: utf-8 -*-
from odoo import models


class IncomingMailAssignWizard(models.TransientModel):
    _inherit = 'incoming.mail.assign.wizard'

    def action_assign(self):
        res = super().action_assign()
        for wizard in self:
            mail = wizard.incoming_mail_id
            assignee = wizard.user_id
            assigner = self.env.user
            # Always mark shared + assignment so SJC employee dashboards see the mail
            # even when Incoming Mail skipped shared_user_ids (assignee is inbox user).
            mail.sudo().write({
                'sjc_assigned_by_id': assigner.id,
                'shared_user_ids': [(4, assignee.id)],
            })
            self.env['incoming.mail.assignment'].sudo().create({
                'mail_id': mail.id,
                'user_id': assignee.id,
                'assigned_by_id': assigner.id,
            })
        return res
