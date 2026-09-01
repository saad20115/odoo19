# Extension of Project Task model.
# - Adds department linkage and parent department hierarchy.
# - Introduces task type (main/sub-task) and task status tracking.
# - Includes Exploratory, Execution, and Closure stage fields with forms and attachments.
# - Tracks inspections, procedures, and recommendations for each stage.
# - Automatically sets finished date when task status is marked as finished.
#
# Developed by: Ziad Bakry.

from odoo import fields, models, api

class ProjectTask(models.Model):
    _inherit = "project.task"

    TASK_TYPE = [
        ('task', 'مهمة رئيسية'),
        ('sub_task', 'مهمة فرعية'),
    ]

    DURATION_EVERY = [
        ('minutes', 'دقائق'),
        ('hours', 'ساعات'),
        ('days', 'أيام'),
        ('weeks', 'أسابيع'),
        ('months', 'شهور'),
    ]

    STATUS = [
        ('not_started', 'لم تبدأ بعد'),
        ('started', 'تم البدء'),
        ('finished', 'تم الانتهاء')
    ]

    INSPECTION_STATUS = [
        ('violation', 'يوجد مخالفات'),
        ('no_violation', 'لا يوجد مخالفات'),
    ]

    department_id = fields.Many2one('project.department', string="Department")
    parent_department = fields.Many2one('project.department', related="department_id.parent_department", string="Parent Department", store=True)
    task_type = fields.Selection(TASK_TYPE, string="Task Type", default="task", required=True)

    task_order_number = fields.Char(string="Task Order Number")
    contractor_id = fields.Many2one('res.partner', string="Contractor Name")
    station_number = fields.Char(string="Station Number")
    site_coordinates = fields.Char(string="Site Coordinates", help="Enter a Google Maps link")
    assignment_date = fields.Date(string="Assignment Date")
    task_order_duration = fields.Float(string="Task Order Duration")
    task_duration_every = fields.Selection(DURATION_EVERY, string="Duration Every", default="days")
    task_attachment_ids = fields.Many2many(
        'ir.attachment',
        'attachment_task_rel',
        'task_id', 'attachment_id',
        string="Attachments",help='Attachments related to this task.')


    # Sub Task Fields
    task_status = fields.Selection(STATUS, string="Task Status")
    finished_date = fields.Date(string="Finished Date")


    # Exploratory Stage Tab Fields
    # Task Name = self.name
    # Task Order Number = self.task_order_number
    exp_redirect_to = fields.Many2one('res.users', string="Redirect to")
    exp_state = fields.Selection(STATUS, string="Exploratory State", default="not_started")
    exp_obstacles = fields.Text(string="Obstacles")
    exp_permit_required = fields.Boolean(string="Permit Required")
    exp_required_forms = fields.Many2many(
        'project.task.form',
        'task_exp_form_rel',
        'task_id','form_id',
        string="Required Forms")

    exp_attachment_ids = fields.Many2many(
        'ir.attachment',
        'attachment_exploratory_task_rel',
        'task_id', 'attachment_id',
        string="Attachments", help="Attachments related to exploratory stage for this task")

    exp_description = fields.Text(string="Exploratory Description")


    # Execution Stage Tab Fields
    # Task Name = self.name
    # Task Order Number = self.task_order_number
    exec_redirect_to = fields.Many2one('res.users', string="Redirect to")
    exec_state = fields.Selection(STATUS, string="Execution State", default="not_started")
    exec_estimated_quantities = fields.Float(string="Estimated Quantities")
    exec_executed_quantities = fields.Float(string="Executed & Final Quantities")
    exec_inspection_status = fields.Selection(INSPECTION_STATUS, string="Inspection Status")
    exec_image_attachment_ids = fields.Many2many('ir.attachment', string="Attach Images", domain=[('mimetype', 'like', 'image/%')], help="Attach related images")

    exec_procedure_203 = fields.Boolean(string="Procedure 203", default=False)
    exec_date = fields.Date(string="Execution Date")

    exec_required_forms = fields.Many2many(
        'project.task.form',
        'task_exec_form_rel',
        'task_id', 'form_id',
        string="Required Forms")

    exec_attachment_ids = fields.Many2many(
        'ir.attachment',
        'attachment_execution_task_rel',
        'task_id', 'attachment_id',
        string="Attachments", help="Attachments related to execution stage for this task")

    exec_recommendations = fields.Text(string="Recommendations")


    # Closure Stage Tab Fields
    # Task Name = self.name
    # Task Order Number = self.task_order_number
    cls_redirect_to = fields.Many2one('res.users', string="Redirect to")
    cls_state = fields.Selection(STATUS, string="Closure State", default="not_started")
    cls_certificate_issued = fields.Boolean(string="Certificate Issued", default=False)
    cls_procedure_155 = fields.Boolean(string="Procedure 155", default=False)
    cls_final_quantities_approved = fields.Boolean(string="Final Quantities Approved", default=False)

    cls_required_forms = fields.Many2many(
        'project.task.form',
        'task_cls_form_rel',
        'task_id', 'form_id',
        string="Required Forms")

    cls_attachment_ids = fields.Many2many(
        'ir.attachment',
        'attachment_closure_task_rel',
        'task_id', 'attachment_id',
        string="Attachments", help="Attachments related to closure stage for this task")

    cls_description = fields.Text(string="Description")


    @api.onchange('task_status')
    def _onchange_status(self):
        for rec in self:
            if rec.task_status == 'finished':
                rec.finished_date = fields.Date.today()
            else:
                rec.finished_date = False