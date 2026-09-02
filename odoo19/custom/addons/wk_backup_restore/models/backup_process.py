# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
#################################################################################

from odoo import fields, api, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_resource
from odoo.tools.config import config

from odoo.addons.wk_backup_restore.models.lib import manage_backup_crons
from datetime import datetime
import subprocess
import os

import logging

_logger = logging.getLogger(__name__)


LOCATION = [
    ('local', 'Local'),
]

CYCLE = [
    ('half_day', 'Twice a day'),
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('monthly', 'Monthly'),
    ('yearly', 'Yearly'),
]

STATE = [
    ('draft', 'Draft'),
    ('confirm', 'Confirm'),
    ('running', 'Running'),
    ('cancel', 'Cancel')
]

class BackupProcess(models.Model):
    _name = "backup.process"
    _description = "Backup Process"


    def _default_db_name(self):
        return self._cr.dbname

    name = fields.Char(string="Process Name", default='New', help="Display name for the backup process.")
    frequency = fields.Integer(string="Frequency", default=1, help="Frequency for backuping the database.")
    frequency_cycle = fields.Selection(selection=CYCLE, string="Frequency Cycle", help="Select frequency cycle of Database Backup.")
    storage_path = fields.Char(string="Storage Path", help="The directory path where the backup files will be stored on server.")
    backup_location = fields.Selection(selection=LOCATION, string="Backup Location", default="local", help="Server where the backup file will be stored.")
    retention = fields.Integer(string="Backup Retention Count", default=7, help="Count of recent backups that will be retained after dropping old backups on server.")
    # start_time = fields.Datetime(string="Backup Starting Time", help="Time from when the database backup can be started.")
    db_name = fields.Char(string="Database Name", default=_default_db_name, help="Database used for the creating the backup.")
    backup_starting_time = fields.Datetime(string="Backup Starting Time", help="Set Database Backup start date and time.")
    state = fields.Selection(selection=STATE, default='draft', help="Current state of the backup process.")
    update_requested = fields.Boolean(string="Update Requested", default=False, help="Checked if any backup is requested in the database backup.")
    # master_pass = fields.Char(string="Master Password")
    backup_details_ids = fields.One2many(comodel_name="backup.process.detail", inverse_name="backup_process_id", string="Backup Details", help="Details of the database backups that has been created.")
    backup_format = fields.Selection([('zip', 'zip (includes filestore)'), ('dump', 'pg_dump custom format (without filestore)')], string="Backup Format", default="zip", help="Select the file format of the data backup file.") 
    enable_retention = fields.Boolean(string="Drop Old Backups", default=False, help="Check if you want to drop old backups stored on the server.")
    

    @api.onchange('frequency_cycle')
    def change_frequency_value(self):
        """
            Method to change the value of frequency for Twice a day
        """

        if self.frequency_cycle == 'half_day':
            self.frequency = 2
        else:
            self.frequency = 1
            
    
    @api.constrains('retention')
    def check_retention_value(self):
        """
            Method to check the value of retention field
        """

        if self.enable_retention:
            if self.retention < 1:
                raise UserError("Backup Retention Count should be at least 1.")

    def call_backup_script(self, master_pass=None, port_number=None, url=None, db_user=None, db_password=None):
        """
            Called by create_backup_request method, defined below
            Method to call script to create a cron for manage backups,
            calling script require few arguments, some are passed in this method same are prepared below
        """

        db_user = db_user or config.get('db_user')
        db_password = db_password or config.get('db_password')
        module_path = get_module_resource('wk_backup_restore')
        module_path = module_path + '/models/lib/saas_client_backup.py'
        backup_format = self.backup_format or "zip" 
        res = manage_backup_crons.add_cron(master_pass=master_pass, main_db=self._cr.dbname, db_name=self.db_name, backup_location=self.backup_location, frequency=self.frequency, frequency_cycle=self.frequency_cycle, storage_path=self.storage_path, url=url, db_user=db_user, db_password=db_password, process_id=self.id, module_path=module_path, backup_format=self.backup_format)
        if res.get('success'):
            self.state = 'running'
            return res

    def update_backup_request(self):
        """
            Method called from Cron, 
            Method called the script to update already created cron.
        """

        res = manage_backup_crons.update_cron(db_name=self.db_name, process_id=str(self.id), frequency=self.frequency, frequency_cycle=self.frequency_cycle)
        if res.get('success'):
            self.update_requested = False
    
    def create_backup_request(self):
        """
            Called from the crone:
            Method called the method to which call the crone script 
        """

        # master_pass = self.master_pass
        master_pass = config.get('master_passwd')
        if master_pass:
            url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            return self.call_backup_script(master_pass=master_pass, url=url)
        else:
            _logger.info("------Error While Creating Backup Request--Master Password(master_passwd) is not set in conf file!!----------------")

    def remove_attached_cron(self):
        """
            Called by the button over backup process page,
            To cancel the Backup Process record and to call the delete cron script
        """

        if self.state == 'running':
            res = manage_backup_crons.remove_cron(db_name=self.db_name, process_id=str(self.id), frequency=self.frequency, frequency_cycle=self.frequency_cycle)
        else:
            res = dict(
                success = True
            )
        if res.get('success'):
            self.state = 'cancel'
            return res
    
    @api.model
    def ignite_backup_server_crone(self):
        """
            Crone method to call functions either to create a new cron, or to update a existing one
        """

        current_time = datetime.now()
        processes = self.env['backup.process'].sudo().search([('backup_starting_time', '<=', current_time), ('state', '=', 'confirm')])
        for process in processes:
            process.create_backup_request()
        upt_processes = self.env['backup.process'].sudo().search([('backup_starting_time', '<=', current_time), ('state', '=', 'running'), ('update_requested', '=', True)])        
        for upt_process in upt_processes:
            if upt_process.update_requested:
                upt_process.update_backup_request()

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('backup.process')
        res = super(BackupProcess, self).create(vals)
        return res
    
    def write(self, vals):
        if self.state not in ['draft','cancel','confirm'] and self.backup_starting_time <= datetime.now() and not vals.get('update_requested') == False:
            vals['update_requested'] = True
        return super(BackupProcess, self).write(vals)


    def unlink(self):
        if self.state not in ['draft','cancel','confirm']:
            raise UserError("Not allowed")
        return super(BackupProcess, self).unlink()


    def confirm_process(self):
        """
            Called by the Confirm button over the backup process record
        """

        if self.state == 'draft':
            self.state ="confirm"

    def cancel_process(self):
        """
            Called by the Cancel button over the backup process record
        """

        if self.state in ['draft','confirm']:
            self.state ="cancel"
            
    @api.model
    def remove_old_backups(self):
        """
            Cron method to call functions to remove the backup file of the backup processes
        """
        
        processes = self.env['backup.process'].sudo().search([('state', '=', 'running'),('enable_retention', '=', True)])
        for rec in processes:
            details_ids = rec.backup_details_ids.filtered(lambda d: d.status == "Success")
            if details_ids:
                end_index = len(details_ids) - rec.retention
                if end_index>0:
                    updated_details_ids = details_ids[:end_index]
                    self.remove_backup_files(updated_details_ids)
    
    def remove_backup_files(self, bkp_details_ids):
        """
            Method to check if the backup file exist, and if exist then remove that backup file.
            Also, updates the status and the message of the backup process details.
            
            Args:
                bkp_details_ids ([object]): [all the backup process ids whose backup file needs to be deleted.]
        """
        try:
            for bkp in bkp_details_ids:
                if os.path.exists(bkp.url):
                    res = os.remove(bkp.url)
                    msg = 'Database backup dropped successfully  at ' + datetime.now().strftime("%m-%d-%Y-%H:%M:%S") + " after retention."
                    _logger.info("---- %r ---- ", msg)
                    bkp.message = msg
                    bkp.status = "Dropped"
            return True
        except Exception as e:
            _logger.error("Database backup remove error: " + str(e))
            return False
        



