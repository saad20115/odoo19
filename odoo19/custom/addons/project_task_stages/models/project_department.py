# Custom project extension.
# - Adds department hierarchy for tasks.
# - Supports parent/child task structure and department linkage.
#
# Developed by: Ziad Bakry

from odoo import fields, models

class ProjectDepartment(models.Model):
    _name = 'project.department'
    _description = 'Project Department'

    name = fields.Char(string="Department Name", required=True)
    parent_department = fields.Many2one('project.department', string="Parent")

    def action_open_tasks_related_to_department(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f"Tasks of {self.name}",
            'res_model': 'project.task',
            'view_mode': 'kanban,tree,form,calendar,pivot,graph,activity',
            'target': 'current',
            'domain': [('department_id','=',self.id)],
            'context': {
                'search_default_filter_main_task': 1,
                'group_by': 'department_id',
                'default_department_id': self.id,
            },
        }

    def action_open_tasks_related_to_department_as_parent(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f"Tasks of {self.name} as parent",
            'res_model': 'project.task',
            'view_mode': 'kanban,tree,form,calendar,pivot,graph,activity',
            'target': 'current',
            'domain': [('parent_department','=',self.id)],
            'context': {
                'search_default_filter_main_task': 1,
                'group_by': 'department_id',
            },
        }

