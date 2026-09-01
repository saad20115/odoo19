# Extension of Project model.
# - Adds a project type field to classify projects (e.g., Unified Contract).
# - Supports project categorization for better management and reporting.
#
# Developed by: Ziad Bakry.

from odoo import fields, models

class Project(models.Model):
    _inherit = "project.project"

    PROJECT_TEMP_TYPE = [
        ('u_contract', 'العقد الموحد')
    ]

    project_template_type = fields.Selection(PROJECT_TEMP_TYPE, string="Project Type")