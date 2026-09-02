# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import uuid


class AccountInvoice(models.Model):
    _inherit = "account.payment"
    text_message = fields.Text("Message", compute="_compute_get_message_detail_ap")
    payment_url = fields.Text("Url ")

    def action_quotation_send_wp(self):
        """Opens a wizard to compose an email, with relevant mail template loaded by default"""

        if not self.partner_id.mobile:
            raise UserError(_("Partner Mobile Number Not Exist !"))

        self.ensure_one()
        template = self.env.ref(
            "sh_whatsapp_integration.mail_template_data_payment_receipt_custom"
        )
        if template.lang:
            template._render_lang(self.ids)[self.id]

        ctx = {
            "default_model": "account.payment",
            "active_model": "account.payment",
            "active_id": self.ids[0],
            "default_res_ids": self.ids,
            "default_use_template": bool(template.id),
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "mark_so_as_sent": True,
            "custom_layout": "mail.mail_notification_paynow",
            "force_email": True,
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

    def _get_report_base_filename(self):
        self.ensure_one()
        if self.name:
            return "Payment Receipt %s" % (self.name)
        else:
            return "Payment Receipt"

    report_token = fields.Char("Access Token")

    def _get_token(self):
        """Get the current record access token"""
        if self.report_token:
            return self.report_token
        else:
            report_token = str(uuid.uuid4())
            self.write({"report_token": report_token})
            return report_token

    def get_download_report_url(self):
        url = ""
        if self.id:
            self.ensure_one()
            url = "/download/pay/" + "%s?access_token=%s" % (self.id, self._get_token())
        return url

    @api.depends("partner_id", "currency_id", "company_id")
    def _compute_get_message_detail_ap(self):
        for inv in self:
            txt_message = ""
            if inv and inv.payment_type == "inbound":
                txt_message = ""
                if (
                    inv.company_id.invoice_order_information_in_message
                    and inv.partner_id
                    and inv.currency_id
                    and inv.company_id
                ):
                    txt_message += (
                        "Dear " + "*" + str(inv.partner_id.name) + "*" + "," + "%0A%0A"
                    )

                    txt_message += (
                        " %0A%0AHere is the Payment "
                        + "*"
                        + str(inv.name)
                        + "*"
                        + "from"
                        + inv.company_id.name
                        + "."
                    )

                    txt_message += (
                        "We received payment of "
                        + "*"
                        + str(inv.amount)
                        + ""
                        + str(inv.currency_id.symbol)
                        + "*"
                        + ""
                    )
                    txt_message += " by  " + "*" + str(inv.journal_id.name) + "*"
                    if inv.name:
                        txt_message += ". Reference No :" + str(inv.name)
                    txt_message += "%0A%0A" + "Thank you." + "%0A%0A"

                if inv.company_id.inv_send_pdf_in_message:
                    base_url = (
                        self.env["ir.config_parameter"].sudo().get_param("web.base.url")
                    )
                    inv_url = (
                        "%0A *Click here to download Report :* %0A"
                        + base_url
                        + inv.get_download_report_url()
                    )
                    self.update(
                        {"payment_url": base_url + inv.get_download_report_url()}
                    )
                    txt_message += inv_url

                if inv.company_id.invoice_signature and inv.env.user.sign:
                    txt_message += "%0A%0A" + str(inv.env.user.sign)
            inv.text_message = txt_message.replace("&", "%26")

            if inv and inv.payment_type == "outbound":
                txt_message = ""
                if (
                    inv.company_id.invoice_order_information_in_message
                    and inv.partner_id
                    and inv.currency_id
                    and inv.company_id
                ):
                    txt_message += "Dear " + str(inv.partner_id.name) + "," + "%0A%0A"
                    txt_message += (
                        "We paid payment of "
                        + "*"
                        + str(inv.amount)
                        + ""
                        + str(inv.currency_id.symbol)
                        + "*"
                        + ""
                    )
                    txt_message += " by  " + "*" + str(inv.journal_id.name) + "*"
                    if inv.name:
                        txt_message += ". Reference No :" + str(inv.name) + "%0A%0A"
                    txt_message += "Thank you." + "%0A%0A"

                if inv.company_id.inv_send_pdf_in_message:
                    base_url = (
                        self.env["ir.config_parameter"].sudo().get_param("web.base.url")
                    )
                    inv_url = (
                        "%0A *Click here to download Report :* %0A"
                        + base_url
                        + inv.get_download_report_url()
                    )
                    self.update(
                        {"payment_url": base_url + inv.get_download_report_url()}
                    )
                    txt_message += inv_url

                if inv.company_id.invoice_signature and inv.env.user.sign:
                    txt_message += "%0A%0A" + str(inv.env.user.sign)
            inv.text_message = txt_message.replace("&", "%26")

    # Send By Whatsapp Direct Method
    def send_by_whatsapp_direct_to_ci(self):
        if self:
            for rec in self:
                if rec.company_id.invoice_display_in_message:
                    message = ""
                    if rec.text_message:
                        message = (
                            str(rec.text_message)
                            .replace("*", "")
                            .replace("_", "")
                            .replace("%0A", "<br/>")
                            .replace("%20", " ")
                            .replace("%26", "&")
                        )
                    self.env["mail.message"].create(
                        {
                            "partner_ids": [(6, 0, rec.partner_id.ids)],
                            "model": "account.payment",
                            "res_id": rec.id,
                            "author_id": self.env.user.partner_id.id,
                            "body": message or False,
                            "message_type": "comment",
                        }
                    )
                if self.partner_id.mobile:
                    return {
                        "type": "ir.actions.act_url",
                        "url": "https://web.whatsapp.com/send?l=&phone="
                        + self.partner_id.mobile
                        + "&text="
                        + self.text_message,
                        "target": "new",
                        "res_id": self.id,
                    }
                else:
                    raise UserError(_("Partner Mobile Number Not Exist"))
