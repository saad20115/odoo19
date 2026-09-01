# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import fields, models, api


class HrContract(models.Model):
    """Extends the standard 'hr.contract' model to include additional fields
        for employee contracts."""
    _inherit = 'hr.contract'
    _description = 'Employee Contract'

    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string='Analytic Account',
                                          help="Select Analytic account")
    journal_id = fields.Many2one('account.journal',
                                 string='Salary Journal',
                                 help="Journal associated with the record")
    
    x_today_wage = fields.Float(string='اجر اليوم', compute="_compute_x_today_wage")
    x_hour_rate = fields.Float(string='اجر الساعه', compute="_compute_x_hour_rate")
    x_overtime_hour = fields.Float(string='ساعة العمل الإضافي', compute="_compute_x_overtime_hour")
    x_total_overtime = fields.Float(string='اجمالي العمل الاضافي', compute="_compute_x_total_overtime")
    x_number_of_overtime_hours = fields.Float(string='عدد ساعات العمل الاضافي')
    x_social_insurance = fields.Float(string='Social Insurance')
    



    
    @api.depends("x_overtime_hour","x_number_of_overtime_hours")
    def _compute_x_total_overtime(self):
        # Overtime amount is disabled from payroll calculations.
        for record in self:
            record.x_total_overtime = 0.0
    

    @api.depends("x_total_salary")
    def _compute_x_overtime_hour(self):
        for record in self:
            if record.x_total_salary:
                record.x_overtime_hour = record.x_total_salary * 0.004375
            else:
                record.x_overtime_hour = 0.0
    
    @api.depends("x_today_wage","x_total_salary")
    def _compute_x_today_wage(self):
        for record in self:
            if record.x_total_salary:
                record.x_today_wage = record.x_total_salary / 30
            else:
                record.x_today_wage = 0.0

    @api.depends("x_today_wage","x_hour_rate")
    def _compute_x_hour_rate(self):
        for record in self:
            if record.x_today_wage:
                record.x_hour_rate = record.x_today_wage / 8
            else:
                record.x_hour_rate = 0.0


    # @api.onchange("x_today_wage")
    # def _compute_work_duration(self):
    #     wdt =  self.env['arcgis.work.duration.type'].search([('x_work_type','=',self.x_work_type.id)] ,limit=1)
    #     self.x_consultant_code = wdt.x_consultant_code.id
    #     self.x_job_description = wdt.x_job_description.id
    #     self.x_section = wdt.x_section.id
    #     self.work_order_duration_date = wdt.x_job_duration


