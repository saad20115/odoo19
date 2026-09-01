import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BATCH_SIZE = 50
PRESCAN_LIMIT = 100


class FetchmailFetchJob(models.Model):
    _name = 'fetchmail.fetch.job'
    _description = 'Fetch Date Range Job'
    _order = 'create_date desc'

    name = fields.Char(compute='_compute_name', store=True)
    fetchmail_server_id = fields.Many2one(
        'fetchmail.server',
        string='Incoming Mail Server',
        required=True,
        ondelete='cascade',
    )
    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('done', 'Done'),
            ('failed', 'Failed'),
        ],
        default='pending',
        required=True,
    )
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    message_nums = fields.Text(help='Remaining IMAP message numbers stored as JSON.')
    total_found = fields.Integer(string='Emails Found')
    imported_count = fields.Integer(string='Imported')
    skipped_count = fields.Integer(string='Already Imported')
    failed_count = fields.Integer(string='Failed')
    result_message = fields.Text(string='Result')

    @api.depends('fetchmail_server_id.name', 'date_from', 'date_to')
    def _compute_name(self):
        for job in self:
            server_name = job.fetchmail_server_id.name or _('Server')
            job.name = _(
                '%(server)s from %(date_from)s to %(date_to)s',
                server=server_name,
                date_from=job.date_from or '',
                date_to=job.date_to or '',
            )

    @api.model
    def _cron_process_jobs(self):
        jobs = self.search([('state', 'in', ('pending', 'running'))], limit=5)
        for job in jobs:
            try:
                job._process_batch()
            except Exception:
                _logger.exception('Fetch date range job %s failed', job.id)
                job.write({
                    'state': 'failed',
                    'result_message': _(
                        'Unexpected error while fetching emails. Check the server logs.'
                    ),
                })
                job._notify_user('danger')
        if self.search_count([('state', 'in', ('pending', 'running'))]):
            self.env.ref('incoming_mail_store.ir_cron_fetchmail_date_range')._trigger()

    @api.model
    def create_from_wizard(self, server, date_from, date_to):
        server.ensure_one()
        if date_from > date_to:
            raise UserError(_('The start date must be before or equal to the end date.'))
        if server.server_type != 'imap':
            raise UserError(_('Fetch by date range is only supported for IMAP servers.'))
        if server.state != 'done':
            raise UserError(_('Please confirm the incoming mail server first.'))
        if not server.object_id:
            raise UserError(_('Set "Create a New Record" on this incoming mail server first.'))

        running_job = self.search([
            ('fetchmail_server_id', '=', server.id),
            ('state', 'in', ('pending', 'running')),
        ], limit=1)
        if running_job:
            raise UserError(_(
                'A fetch job is already running for server "%(server)s". '
                'Please wait until it finishes.',
                server=server.name,
            ))

        message_nums = server._imap_search_date_range(date_from, date_to)
        if not message_nums:
            raise UserError(_(
                'No emails were found from %(date_from)s to %(date_to)s in mailbox %(mailbox)s.',
                date_from=date_from,
                date_to=date_to,
                mailbox=server.user,
            ))

        decoded_nums = [
            num.decode() if isinstance(num, bytes) else str(num)
            for num in message_nums
        ]
        if len(decoded_nums) <= PRESCAN_LIMIT:
            duplicate_count = server._imap_count_existing_messages(decoded_nums)
            if duplicate_count == len(decoded_nums):
                raise UserError(_(
                    'All %(count)s email(s) from %(date_from)s to %(date_to)s are already imported in Odoo.',
                    count=len(decoded_nums),
                    date_from=date_from,
                    date_to=date_to,
                ))

        job = self.create({
            'fetchmail_server_id': server.id,
            'date_from': date_from,
            'date_to': date_to,
            'message_nums': json.dumps(decoded_nums),
            'total_found': len(decoded_nums),
            'user_id': self.env.uid,
        })
        self.env.ref('incoming_mail_store.ir_cron_fetchmail_date_range')._trigger()
        return job

    def _process_batch(self):
        self.ensure_one()
        if self.state == 'done':
            return

        server = self.fetchmail_server_id
        if server.state != 'done' or server.server_type != 'imap':
            self.write({
                'state': 'failed',
                'result_message': _('The server must be a confirmed IMAP server.'),
            })
            self._notify_user('danger')
            return

        remaining = json.loads(self.message_nums or '[]')
        if not remaining:
            self.write({
                'state': 'done',
                'result_message': self._build_result_message(),
            })
            self._notify_user('success')
            return

        self.write({'state': 'running'})
        imap_server = None
        try:
            imap_server = server.connect()
            imap_server.select()
            batch = remaining[:BATCH_SIZE]
            rest = remaining[BATCH_SIZE:]
            mail_thread = self.env['mail.thread'].with_context(
                fetchmail_cron_running=True,
                default_fetchmail_server_id=server.id,
            )
            imported = self.imported_count
            skipped = self.skipped_count
            failed = self.failed_count

            for num in batch:
                try:
                    result, data = imap_server.fetch(num, '(BODY.PEEK[])')
                    if not data or not data[0] or not isinstance(data[0], tuple):
                        failed += 1
                        continue
                    raw_message = data[0][1]
                    if server._is_message_already_imported(raw_message):
                        skipped += 1
                    else:
                        res_id = mail_thread.message_process(
                            server.object_id.model,
                            raw_message,
                            custom_values={'fetchmail_server_id': server.id},
                            save_original=server.original,
                            strip_attachments=not server.attach,
                        )
                        if res_id:
                            imported += 1
                        else:
                            skipped += 1
                except Exception:
                    _logger.info(
                        'Failed to process date-range mail on server %s',
                        server.name,
                        exc_info=True,
                    )
                    failed += 1
                self.env.cr.commit()

            vals = {
                'message_nums': json.dumps(rest),
                'imported_count': imported,
                'skipped_count': skipped,
                'failed_count': failed,
            }
            if rest:
                vals['state'] = 'pending'
                self.write(vals)
                self.env.ref('incoming_mail_store.ir_cron_fetchmail_date_range')._trigger()
            else:
                vals['state'] = 'done'
                vals['result_message'] = self._build_result_message(
                    imported=imported,
                    skipped=skipped,
                    failed=failed,
                )
                self.write(vals)
                server.write({'date': fields.Datetime.now()})
                self._notify_user('success')
        except Exception as error:
            _logger.exception('Fetch date range batch failed for job %s', self.id)
            self.write({
                'state': 'failed',
                'result_message': _('Connection or server error: %s') % error,
            })
            self._notify_user('danger')
        finally:
            if imap_server:
                try:
                    imap_server.close()
                    imap_server.logout()
                except OSError:
                    pass

    def _build_result_message(self, imported=None, skipped=None, failed=None):
        self.ensure_one()
        imported = self.imported_count if imported is None else imported
        skipped = self.skipped_count if skipped is None else skipped
        failed = self.failed_count if failed is None else failed

        if imported == 0 and skipped > 0 and failed == 0:
            return _(
                'No new emails imported. %(skipped)d email(s) from %(date_from)s to %(date_to)s were already in Odoo.',
                skipped=skipped,
                date_from=self.date_from,
                date_to=self.date_to,
            )
        if imported == 0 and skipped == 0 and failed == 0:
            return _(
                'No emails were imported from %(total)d message(s) found from %(date_from)s to %(date_to)s.',
                total=self.total_found,
                date_from=self.date_from,
                date_to=self.date_to,
            )
        return _(
            'Fetch completed: %(imported)d imported, %(skipped)d already existed, '
            '%(failed)d failed (out of %(total)d found).',
            imported=imported,
            skipped=skipped,
            failed=failed,
            total=self.total_found,
        )

    def _notify_user(self, notif_type='success'):
        self.ensure_one()
        partner = self.user_id.partner_id
        if not partner:
            return
        self.env['bus.bus']._sendone(partner, 'simple_notification', {
            'title': _('Email fetch from %s to %s') % (self.date_from, self.date_to),
            'message': self.result_message or _('Fetch job finished.'),
            'type': notif_type,
        })
