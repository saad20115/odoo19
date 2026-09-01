from odoo import api, models


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def _fetchmail_custom_values(self, custom_values=None):
        """Ensure incoming.mail records always receive the fetchmail server."""
        custom_values = dict(custom_values or {})
        fetchmail_server_id = self.env.context.get('default_fetchmail_server_id')
        if fetchmail_server_id:
            custom_values.setdefault('fetchmail_server_id', fetchmail_server_id)
        return custom_values

    @api.model
    def message_process(self, model, message, custom_values=None,
                        save_original=False, strip_attachments=False,
                        thread_id=None):
        custom_values = self._fetchmail_custom_values(custom_values)
        return super().message_process(
            model,
            message,
            custom_values=custom_values,
            save_original=save_original,
            strip_attachments=strip_attachments,
            thread_id=thread_id,
        )

    @api.model
    def _message_route_process(self, message, message_dict, routes):
        fetchmail_server_id = self.env.context.get('default_fetchmail_server_id')
        if fetchmail_server_id and routes:
            routes = [
                (
                    model,
                    thread_id,
                    {
                        **(custom_values or {}),
                        'fetchmail_server_id': fetchmail_server_id,
                    },
                    user_id,
                    alias,
                )
                for model, thread_id, custom_values, user_id, alias in routes
            ]
        return super()._message_route_process(message, message_dict, routes)
