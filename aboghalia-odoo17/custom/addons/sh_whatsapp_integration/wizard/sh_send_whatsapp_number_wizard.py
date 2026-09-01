# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ShSendWhatsappNumber(models.TransientModel):
    _name = "sh.send.whatsapp.number.wizard"
    _description = "Send whatsapp message wizard"

    partner_ids = fields.Many2one("res.partner", string="Recipients")
    whatsapp_mobile = fields.Char(string="Whatsapp Number", required=True)
    message = fields.Text(required=True)
    crm_lead_id = fields.Many2one('crm.lead', string="Lead")

    @api.model
    def default_get(self, fields):
        if 'active_id' in self.env.context:
            active_id = self.env.context.get('active_id')
            if active_id:
                res = super(ShSendWhatsappNumber, self).default_get(fields)
                sh_message = ""
                crm = self.env['crm.lead'].browse(active_id)
                if crm.company_id.crm_lead_signature and self.env.user.sign:
                    sh_message += "%0A%0A%0A" + \
                        str(self.env.user.sign).replace(
                            '&', '%26') + "%0A%0A%0A"
                res.update({
                    'message': sh_message
                })
                return res
        elif 'active_id' not in fields:
            return super().default_get(fields)

    @api.onchange('partner_ids')
    def onchange_partner(self):
        if self.partner_ids:
            self.whatsapp_mobile = self.partner_ids.mobile

    def action_send_whatsapp_number(self):
        if self.whatsapp_mobile and self.message:
            for rec in self:
                if rec.partner_ids:
                    sh_message = ""
                    if self.message:
                        sh_message = str(self.message).replace(
                            '*', '').replace('_', '').replace('%0A', '<br/>').replace('%20', ' ').replace('%26', '&')
                    if self.crm_lead_id and self.crm_lead_id.company_id.crm_lead_display_in_message:
                        self.env['mail.message'].create({
                                                        'partner_ids': [(6, 0, rec.partner_ids.ids)] or False,
                                                        'model': 'crm.lead',
                                                        'res_id': self.env.context.get('active_id'),
                                                        'author_id': self.env.user.partner_id.id,
                                                        'body': sh_message or False,
                                                        'message_type': 'comment',
                                                        })
                    return {
                        'type': 'ir.actions.act_url',
                        'url': "https://web.whatsapp.com/send?l=&phone="+rec.whatsapp_mobile+"&text=" + self.message.replace('&', '%26'),
                        'target': 'new',
                        'res_id': self.id,
                    }
        else:
            raise UserError(_("Please Select Recipients OR Add Whatsapp Number"))
