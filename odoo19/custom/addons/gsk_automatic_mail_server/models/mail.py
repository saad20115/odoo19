from odoo import api, fields, models
import re

class MailMail(models.Model):
    _inherit = 'mail.mail'

    def send(self, auto_commit=False, raise_exception=False):
        for mail in self:
            emails = re.findall(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.[a-z]+", mail.email_from)
            if not mail.mail_server_id or not emails or mail.mail_server_id.smtp_user != emails[0]:
                mail_server = self.env['ir.mail_server'].sudo().search([('smtp_user','=',emails[0])],limit=1)
                if not mail_server:
                    mail_server = self.env['ir.mail_server'].sudo().search([('smtp_user','=',self.env.company.email)],limit=1)
                if not mail_server:
                    mail_server = self.env['ir.mail_server'].sudo().search([],limit=1)
                if mail_server:
                    mail.mail_server_id = mail_server.id
                    partner = self.env['res.partner'].sudo().search([('email','=',mail_server.smtp_user)],limit=1)
                    mail.email_from = partner.email_formatted if partner else self.env.company.email_formatted

        return super(MailMail, self).send(auto_commit=auto_commit,raise_exception=raise_exception)


