from odoo import models, fields, api


class AoSection(models.Model):
    _name = "ao.section.samir"

    name = fields.Char(string="name")
    color = fields.Selection(selection=[
        ('0', 'None'),
        ('1', 'Dark Blue'),
        ('2', 'Tan'),
        ('3', 'Maximum Blue Green'),
        ('4', 'Skobeloff'),
        ('5', 'Platinum'),
        ('6', 'Black'),

    ],
        string="Color",
        default='0'
    )


class AoRequest(models.Model):
    _name = "ao.request.samir"
    name = fields.Char(string="name")


class AoExchange(models.Model):
    _name = "ao.exchange.samir"
    name = fields.Char(string="name")


class AoManagement(models.Model):
    _name = "ao.management.samir"

    name = fields.Char(string="name")


class State(models.Model):
    _name = "ao.state.samir"

    name = fields.Char(string="name")


class HrExpense(models.Model):
    _inherit = "hr.expense"

    y_section = fields.Many2one('ao.section.samir', string="القسم")
    active = fields.Boolean(string="Active", default=True)
    x_request_type = fields.Many2one('ao.request.samir', string="نوع الطلب")
    x_exchange_method = fields.Many2one('ao.exchange.samir', string="طريقة الصرف")
    x_management_approval = fields.Many2one('ao.management.samir', string="اعتماد اإلدارة")
    x_state = fields.Many2one('ao.state.samir', string="الحالة")
    x_responses = fields.Text(string="الردود")
    x_notes = fields.Text(string="الملاحظات")
    priority = fields.Selection(
        [('0', 'Low'), ('1', 'Normal'), ('2', 'High'), ('3', 'Very High')],
        string='الأولوية',
        default='1'
    )
    color_selection = fields.Char(string="Color Selection", compute="compute_color")
    customer_id = fields.Many2one(comodel_name='res.partner', string="Customer")
    state_convent = fields.Boolean(string='موقف التصفية')
    acc_no_from_partner_bank = fields.Char(
        string='الحساب البنكي',
        compute='_compute_acc_no_from_partner_bank',
        store=True,
    )
    loan_check = fields.Boolean(default=False)
    manager = fields.Many2one('res.users', string='Manager', related='sheet_id.user_id')

    @api.depends('customer_id')
    def _compute_acc_no_from_partner_bank(self):
        for expense in self:
            if expense.customer_id:
                bank_lines = expense.customer_id.bank_ids
                if bank_lines:
                    expense.acc_no_from_partner_bank = bank_lines[0].acc_number
                else:
                    expense.acc_no_from_partner_bank = False
            else:
                expense.acc_no_from_partner_bank = False

    @api.depends('y_section')
    def compute_color(self):
        for rec in self:
            rec.color_selection = rec.y_section.color

    def create_loan(self):
        self.loan_check = True
        res = self.env['hr.loan'].create(
            {'employee_id': self.employee_id.id, 'loan_amount': self.total_amount_currency})
        return {
            'name': 'Sale Order Form',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'hr.loan',
            'res_id': res.id,
            'type': 'ir.actions.act_window',
        }

    # def action_active(self):
    #     for rec in self:
    #         rec.active = True

    # def action_active_draft(self):
    #     for rec in self:
    #         rec.active = False

    def action_expense_return(self):
        for expense in self:
            if expense.state == 'done':
                expense.state = 'draft'


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    message_main_attachment_id = fields.Many2one(
        'ir.attachment',
        groups="base.group_user"
    )

    def action_new_expense(self):
        return {
            'name': 'New Expense',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'hr.expense',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def action_view_my_approvals(self):
        self.ensure_one()
        action = self.env.ref('hr_expense.hr_expense_actions_my_all')
        if action:
            action_data = action.read()[0]
            action_data['domain'] = [('manager', '=', self.name)]
            return action_data
        return {}

    def action_view_my_tasks(self):
        self.ensure_one()
        action = self.env.ref('project.action_view_my_task')
        if action:
            return action.read()[0]
        return {}

    approvals_count = fields.Integer(compute='_compute_approvals_count',
                                     string='Approvals',
                                     help='Count of Approvals')

    tasks_count = fields.Integer(compute='_compute_tasks_count',
                                 string='Tasks',
                                 help='Count of Tasks')

    def _compute_approvals_count(self):
        """Get count of documents."""
        for rec in self:
            rec.approvals_count = self.env[
                'hr.expense.sheet'].sudo().search_count(
                [('user_id.name', '=', rec.name)])

    def _compute_tasks_count(self):
        """Get count of documents."""
        for rec in self:
            rec.tasks_count = self.env[
                'project.task'].sudo().search_count(
                [('user_ids', 'in', rec.user_id.id)])


class Saudi(models.Model):
    _name = 'saudi.arabia'
    _description = 'Samir library'
    _inherit = 'mail.thread'

    transaction_number = fields.Integer(string='رقم المعاملة')
    export_number = fields.Integer(string='رقم الصادر')
    import_number = fields.Integer(string='رقم الوارد')
    date = fields.Date(string='الوقت و التاريخ', tracking=True)
    customer_name = fields.Many2one('res.partner', string='اسم العميل/الجهه')
    responsible_empolyee = fields.Many2one('res.users', string='الموظف المسؤل')
    status = fields.Char(string='الحالة')
    transaction_type = fields.Char(string='نوع المعاملة')
    transaction_subject = fields.Char(string='موضوع المعاملة/الجهه')
    project_name = fields.Many2one('project.project', string='اسم المشروع')
    another = fields.Char(string='اخرى')
    referred_to = fields.Char(string='احالة الي', tracking=True)
