# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class UnifiedContractProject(models.Model):
    _name = 'unified.contract.project'
    _description = 'مشروع العقد الموحد'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='اسم مشروع العقد الموحد',
        required=True,
        tracking=True
    )
    code = fields.Char(
        index=True,
        string='رقم العقد الموحد',
        required=True,
        copy=False,
        tracking=True,
        help='الرقم المرجعي الرسمي للعقد الموحد'
    )
    contract_date = fields.Date(
        string='تاريخ توقيع العقد',
        default=fields.Date.context_today,
        tracking=True
    )
    contract_end_date = fields.Date(
        string='تاريخ انتهاء العقد',
        tracking=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='العميل / المالك',
        tracking=True
    )
    contractor_ids = fields.Many2many(
        'res.partner',
        'unified_project_contractor_rel',
        'project_id',
        'partner_id',
        string='المقاولون المعتمدون للمشروع',
        help='قائمة المقاولين المعتمدين لتنفيذ أوامر العمل بهذا المشروع'
    )
    contract_entity = fields.Char(
        string='الجهة المالكة / الراعية',
        tracking=True,
        help='اسم الوزارة أو الهيئة المالكة للمشروع'
    )
    manager_id = fields.Many2one(
        'res.users',
        string='مدير المشروع',
        default=lambda self: self.env.user,
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        index=True,
        string='الشركة',
        default=lambda self: self.env.company,
        required=True
    )
    stage_id = fields.Many2one(
        'unified.contract.stage',
        index=True,
        string='المرحلة الحالية',
        default=lambda self: self._default_stage_id(),
        group_expand='_read_group_stage_ids',
        tracking=True
    )
    is_first_stage = fields.Boolean(
        string='المرحلة الأولى',
        compute='_compute_stage_position'
    )
    is_last_stage = fields.Boolean(
        string='المرحلة الأخيرة',
        compute='_compute_stage_position'
    )
    next_stage_name = fields.Char(
        string='اسم المرحلة التالية',
        compute='_compute_stage_names'
    )
    prev_stage_name = fields.Char(
        string='اسم المرحلة السابقة',
        compute='_compute_stage_names'
    )
    state = fields.Selection([
        ('draft', 'جديد / تحت الإعداد'),
        ('active', 'جاري التنفيذ / نشط'),
        ('in_progress', 'قيد التنفيذ'),
        ('on_hold', 'معلق مؤقتاً'),
        ('late', 'متأخر عن الجدول الزمنـي'),
        ('done', 'منتهي / مكتمل'),
        ('cancel', 'ملغـى'),
    ], string='حالة العقد', default='draft', tracking=True, index=True)

    description = fields.Html(
        string='نطاق العمل وملاحظات العقد'
    )
    work_order_ids = fields.One2many(
        'unified.contract.work.order',
        'project_id',
        string='أوامر العمل والمهام'
    )
    work_order_count = fields.Integer(
        string='عدد أوامر العمل',
        compute='_compute_work_order_count',
        store=True
    )
    team_ids = fields.One2many(
        'unified.contract.team',
        'project_id',
        string='فرق عمل مراحل التنفيذ'
    )
    team_count = fields.Integer(
        string='عدد فرق العمل',
        compute='_compute_team_count',
        store=True
    )

    @api.depends('stage_id')
    def _compute_stage_position(self):
        all_stages = self.env['unified.contract.stage'].search([], order='sequence asc, id asc')
        first_id = all_stages[0].id if all_stages else False
        last_id = all_stages[-1].id if all_stages else False
        for record in self:
            record.is_first_stage = bool(record.stage_id and record.stage_id.id == first_id)
            record.is_last_stage = bool(record.stage_id and record.stage_id.id == last_id)

    @api.depends('stage_id')
    def _compute_stage_names(self):
        all_stages = self.env['unified.contract.stage'].search([], order='sequence asc, id asc')
        for rec in self:
            current_seq = rec.stage_id.sequence if rec.stage_id else -1
            next_stages = [s for s in all_stages if s.sequence > current_seq]
            prev_stages = [s for s in all_stages if s.sequence < current_seq]
            
            if next_stages:
                rec.next_stage_name = f"الانتقال إلى: {next_stages[0].name} ➡️"
            else:
                rec.next_stage_name = "المرحلة التالية ➡️"
                
            if prev_stages:
                rec.prev_stage_name = f"إرجاع لمرحلة سابقة ⬅️"
            else:
                rec.prev_stage_name = "إرجاع لمرحلة سابقة ⬅️"

    @api.depends('team_ids')
    def _compute_team_count(self):
        for record in self:
            record.team_count = len(record.team_ids)

    @api.model
    def _default_stage_id(self):
        return self.env['unified.contract.stage'].search([], limit=1)

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        return self.env['unified.contract.stage'].search([])

    @api.depends('work_order_ids')
    def _compute_work_order_count(self):
        for record in self:
            record.work_order_count = len(record.work_order_ids)

    def _check_revert_stage_permission(self):
        """ Verify if current user is allowed to revert stage to a previous phase """
        if self.env.is_admin():
            return True
        user_profiles = self.env['unified.contract.permission.profile'].search([
            ('user_ids', 'in', [self.env.user.id]),
            ('can_revert_stage', '=', True)
        ])
        if not user_profiles:
            raise UserError(_('عذراً! ليس لديك صلاحية لإرجاع مرحلة المشروع إلى مرحلة سابقة. يتطلب ذلك تفعيل خيار (السماح بإرجاع المراحل للسابقة) في بروفايل الصلاحيات الخاص بك.'))
        return True

    def action_next_stage(self):
        """ Move project to the next stage by sequence """
        all_stages = self.env['unified.contract.stage'].search([], order='sequence asc, id asc')
        for rec in self:
            current_seq = rec.stage_id.sequence if rec.stage_id else -1
            next_stages = [s for s in all_stages if s.sequence > current_seq]
            if next_stages:
                next_stage = next_stages[0]
                rec.stage_id = next_stage.id
                if rec.state == 'draft':
                    rec.state = 'in_progress'

    def action_open_revert_wizard(self):
        """ Open wizard to allow reverting to ANY previous stage """
        self.ensure_one()
        self._check_revert_stage_permission()
        
        all_stages = self.env['unified.contract.stage'].search([
            ('sequence', '<', self.stage_id.sequence if self.stage_id else 999999)
        ], order='sequence desc')
        
        if not all_stages:
            raise UserError(_('المشروع في المرحلة الأولى بالفعل، لا توجد مراحل سابقة للإرجاع إليها.'))
            
        return {
            'name': _('إرجاع المشروع لمرحلة سابقة'),
            'type': 'ir.actions.act_window',
            'res_model': 'unified.contract.stage.revert.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'unified.contract.project',
                'default_res_id': self.id,
                'default_project_stage_id': all_stages[0].id,
                'previous_project_stage_ids': all_stages.ids,
            }
        }


    def _check_field_write_permissions(self, vals):
        """ Enforce unified.contract.field.permission settings for non-admin users at ORM layer """
        if self.env.is_admin():
            return
        user = self.env.user
        profiles = self.env['unified.contract.permission.profile'].search([
            ('user_ids', 'in', [user.id])
        ])
        if not profiles:
            return
        restricted_perms = self.env['unified.contract.field.permission'].search([
            ('profile_id', 'in', profiles.ids),
            ('model_id.model', '=', self._name),
            ('perm_write', '=', False)
        ])
        if not restricted_perms:
            return
        restricted_field_names = set(restricted_perms.mapped('field_id.name'))
        written_fields = set(vals.keys()).intersection(restricted_field_names)
        if written_fields:
            field_labels = [self._fields[fn].string or fn for fn in written_fields if fn in self._fields]
            raise UserError(_('عذراً! ليس لديك صلاحية تعديل الحقول التالية وفقاً لبروفايل الصلاحيات الخاص بك: %s') % (', '.join(field_labels)))

    def write(self, vals):
        self._check_field_write_permissions(vals)
        if 'stage_id' in vals and not self.env.context.get('skip_stage_permission_check'):
            new_stage = self.env['unified.contract.stage'].browse(vals['stage_id'])
            for rec in self:
                if rec.stage_id and new_stage and new_stage.sequence < rec.stage_id.sequence:
                    rec._check_revert_stage_permission()
        return super(UnifiedContractProject, self).write(vals)

    def action_view_work_orders(self):
        self.ensure_one()
        return {
            'name': _('أوامر العمل (Work Orders)'),
            'type': 'ir.actions.act_window',
            'res_model': 'unified.contract.work.order',
            'view_mode': 'tree,form,kanban',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_set_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_set_on_hold(self):
        self.write({'state': 'on_hold'})

    def action_set_done(self):
        self.write({'state': 'done'})

    def action_set_cancel(self):
        self.write({'state': 'cancel'})

    def action_reactivate(self):
        """ Reactivate a cancelled project back to in_progress """
        self.write({'state': 'in_progress'})
