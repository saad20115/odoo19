{
    'name': 'Incoming Mail Store',
    'version': '17.0.1.13.0',
    'category': 'Discuss',
    'summary': 'Store incoming emails from multiple providers in a dedicated model.',
    'description': """
        Central inbox for emails fetched from multiple incoming mail servers
        (Zoho, Hostinger, Gmail, etc.). Each fetchmail server can target this
        model in the "Create a New Record" field.
    """,
    'author': 'Abo Ghaly Accounting',
    'depends': ['mail'],
    'data': [
        'security/incoming_mail_security.xml',
        'security/ir.model.access.csv',
        'data/fetchmail_cron.xml',
        'views/incoming_mail_views.xml',
        'views/fetchmail_server_views.xml',
        'wizard/fetchmail_fetch_wizard_views.xml',
        'wizard/incoming_mail_reply_wizard_views.xml',
        'wizard/incoming_mail_assign_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
