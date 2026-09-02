# Model to define task-related forms.
# - Stores form names used in different task stages (exploratory, execution, closure).
#
# Developed by: Ziad Bakry.

from odoo import fields, models

class ProjectTaskForm(models.Model):
    _name = 'project.task.form'
    _description = 'Project Task Form'

    name = fields.Char(string="Form Name", required=True)
