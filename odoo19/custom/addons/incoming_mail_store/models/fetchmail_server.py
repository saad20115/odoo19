import email
import logging
from datetime import timedelta

from odoo import api, fields, models, _

from odoo.addons.mail.models.fetchmail import MAX_POP_MESSAGES

_logger = logging.getLogger(__name__)

_PROVIDER_HOST_PATTERNS = {
    'gmail': ('gmail.com', 'googlemail.com'),
    'zoho': ('zoho.com', 'zohomail.com'),
    'outlook': (
        'outlook.com',
        'office365.com',
        'hotmail.com',
        'live.com',
        'microsoft.com',
    ),
    'hostinger': ('hostinger.com', 'hostinger.', 'titan.email'),
}


class FetchmailServer(models.Model):
    _inherit = 'fetchmail.server'

    provider = fields.Selection(
        [
            ('zoho', 'Zoho'),
            ('hostinger', 'Hostinger'),
            ('gmail', 'Gmail'),
            ('outlook', 'Outlook / Microsoft 365'),
            ('other', 'Other'),
        ],
        string='Email Provider',
        compute='_compute_provider',
        store=True,
        readonly=True,
        help='Detected automatically from the server hostname.',
    )

    @api.model
    def _detect_provider_from_server(self, server_name):
        hostname = (server_name or '').strip().lower()
        if not hostname:
            return False
        for provider, patterns in _PROVIDER_HOST_PATTERNS.items():
            if any(pattern in hostname for pattern in patterns):
                return provider
        return 'other'

    @api.depends('server')
    def _compute_provider(self):
        for server in self:
            server.provider = server._detect_provider_from_server(server.server)

    def _fetchmail_message_process(self, mail_thread, model, message, *, save_original, strip_attachments):
        """Process one fetched message and always link it to this server."""
        self.ensure_one()
        return mail_thread.message_process(
            model,
            message,
            custom_values={'fetchmail_server_id': self.id},
            save_original=save_original,
            strip_attachments=strip_attachments,
        )

    def fetch_mail(self):
        """Same as core fetchmail, but always links created records to this server."""
        additional_context = {
            'fetchmail_cron_running': True,
        }
        MailThread = self.env['mail.thread']
        for server in self:
            _logger.info(
                'start checking for new emails on %s server %s',
                server.server_type, server.name,
            )
            additional_context['default_fetchmail_server_id'] = server.id
            count, failed = 0, 0
            imap_server = None
            pop_server = None
            connection_type = server._get_connection_type()
            mail_thread = MailThread.with_context(**additional_context)
            if connection_type == 'imap':
                try:
                    imap_server = server.connect()
                    imap_server.select()
                    result, data = imap_server.search(None, '(UNSEEN)')
                    for num in data[0].split():
                        res_id = None
                        result, data = imap_server.fetch(num, '(RFC822)')
                        imap_server.store(num, '-FLAGS', '\\Seen')
                        try:
                            res_id = server._fetchmail_message_process(
                                mail_thread,
                                server.object_id.model,
                                data[0][1],
                                save_original=server.original,
                                strip_attachments=not server.attach,
                            )
                        except Exception:
                            _logger.info(
                                'Failed to process mail from %s server %s.',
                                server.server_type, server.name,
                                exc_info=True,
                            )
                            failed += 1
                        imap_server.store(num, '+FLAGS', '\\Seen')
                        self._cr.commit()
                        count += 1
                    _logger.info(
                        "Fetched %d email(s) on %s server %s; %d succeeded, %d failed.",
                        count, server.server_type, server.name, (count - failed), failed,
                    )
                except Exception:
                    _logger.info(
                        "General failure when trying to fetch mail from %s server %s.",
                        server.server_type, server.name,
                        exc_info=True,
                    )
                finally:
                    if imap_server:
                        try:
                            imap_server.close()
                            imap_server.logout()
                        except OSError:
                            _logger.warning(
                                'Failed to properly finish imap connection: %s.',
                                server.name, exc_info=True,
                            )
            elif connection_type == 'pop':
                try:
                    while True:
                        failed_in_loop = 0
                        num = 0
                        pop_server = server.connect()
                        (num_messages, total_size) = pop_server.stat()
                        pop_server.list()
                        for num in range(1, min(MAX_POP_MESSAGES, num_messages) + 1):
                            (header, messages, octets) = pop_server.retr(num)
                            message = (b'\n').join(messages)
                            res_id = None
                            try:
                                res_id = server._fetchmail_message_process(
                                    mail_thread,
                                    server.object_id.model,
                                    message,
                                    save_original=server.original,
                                    strip_attachments=not server.attach,
                                )
                                pop_server.dele(num)
                            except Exception:
                                _logger.info(
                                    'Failed to process mail from %s server %s.',
                                    server.server_type, server.name,
                                    exc_info=True,
                                )
                                failed += 1
                                failed_in_loop += 1
                            self.env.cr.commit()
                        _logger.info(
                            "Fetched %d email(s) on %s server %s; %d succeeded, %d failed.",
                            num, server.server_type, server.name,
                            (num - failed_in_loop), failed_in_loop,
                        )
                        if num_messages < MAX_POP_MESSAGES or failed_in_loop == num:
                            break
                        pop_server.quit()
                except Exception:
                    _logger.info(
                        "General failure when trying to fetch mail from %s server %s.",
                        server.server_type, server.name,
                        exc_info=True,
                    )
                finally:
                    if pop_server:
                        try:
                            pop_server.quit()
                        except OSError:
                            _logger.warning(
                                'Failed to properly finish pop connection: %s.',
                                server.name, exc_info=True,
                            )
            server.write({'date': fields.Datetime.now()})
        return True

    def _imap_date_criteria(self, date_value):
        self.ensure_one()
        return date_value.strftime('%d-%b-%Y')

    def _imap_search_date_range(self, date_from, date_to):
        self.ensure_one()
        imap_server = None
        try:
            imap_server = self.connect()
            imap_server.select()
            since_criteria = self._imap_date_criteria(date_from)
            before_criteria = self._imap_date_criteria(date_to + timedelta(days=1))
            result, data = imap_server.search(
                None, 'SINCE', since_criteria, 'BEFORE', before_criteria,
            )
            if result != 'OK' or not data or not data[0]:
                return []
            return data[0].split()
        finally:
            if imap_server:
                try:
                    imap_server.close()
                    imap_server.logout()
                except OSError:
                    pass

    @api.model
    def _extract_message_id(self, raw_message):
        if isinstance(raw_message, str):
            raw_message = raw_message.encode('utf-8')
        message = email.message_from_bytes(raw_message, policy=email.policy.SMTP)
        return message.get('Message-ID') or message.get('Message-Id')

    def _is_message_already_imported(self, raw_message):
        self.ensure_one()
        message_id = self._extract_message_id(raw_message)
        if not message_id or not self.object_id:
            return False
        return bool(self.env['mail.message'].search([
            ('message_id', '=', message_id),
            ('model', '=', self.object_id.model),
        ], limit=1))

    def _imap_count_existing_messages(self, message_nums):
        self.ensure_one()
        imap_server = None
        duplicate_count = 0
        try:
            imap_server = self.connect()
            imap_server.select()
            for num in message_nums:
                result, data = imap_server.fetch(num, '(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])')
                if not data or not data[0] or not isinstance(data[0], tuple):
                    continue
                header_bytes = data[0][1]
                if not header_bytes:
                    continue
                message_id = self._extract_message_id(header_bytes)
                if message_id and self.env['mail.message'].search([
                    ('message_id', '=', message_id),
                    ('model', '=', self.object_id.model),
                ], limit=1):
                    duplicate_count += 1
        finally:
            if imap_server:
                try:
                    imap_server.close()
                    imap_server.logout()
                except OSError:
                    pass
        return duplicate_count
