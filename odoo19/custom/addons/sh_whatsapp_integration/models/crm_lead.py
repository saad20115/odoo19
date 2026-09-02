# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    crm_url = fields.Text("Url")

    # Send By Whatsapp Method
    def action_quotation_send_wp(self):
        """Opens a wizard to compose an email, with relevant mail template loaded by default"""

        if not self.partner_id.mobile:
            raise UserError(_("Partner Mobile Number Not Exist !"))

        self.ensure_one()
        lang = self.env.context.get("lang")
        template = self.env.ref("sh_whatsapp_integration.email_template_edi_crm_custom")
        if template.lang:
            lang = template._render_lang(self.ids)[self.id]

        ctx = {
            "default_model": "crm.lead",
            "default_res_ids": self.ids,
            "default_use_template": bool(template.id),
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "mark_so_as_sent": True,
            "custom_layout": "mail.mail_notification_paynow",
            "proforma": self.env.context.get("proforma", False),
            "force_email": True,
            "model_description": self.with_context(lang=lang),
            "default_is_wp": True,
        }

        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(False, "form")],
            "view_id": False,
            "target": "new",
            "context": ctx,
        }
