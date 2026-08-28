# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UnifiedContractFieldPermission(models.Model):
    _name = 'unified.contract.field.permission'
    _description = 'صلاحيات وحالات حقول موديول العقد الموحد'
    _order = 'model_name, name'

    profile_id = fields.Many2one(
        'unified.contract.permission.profile',
        string='بروفايل الصلاحيات',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(
        string='اسم الحقل',
        required=True,
        placeholder='مثال: تاريخ العقد، نموذج 155، نسبة الإنجاز'
    )
    model_id = fields.Many2one(
        'ir.model',
        string='النموذج',
        ondelete='cascade'
    )
    model_name = fields.Char(
        string='اسم النموذج',
        related='model_id.name',
        store=True,
        readonly=True
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='الحقل',
        ondelete='cascade'
    )
    is_required = fields.Boolean(
        string='إلزامي',
        default=False,
        help='محدد = إلزامي (مطلوب) | غير محدد = اختياري'
    )

    perm_read = fields.Boolean(
        string='صلاحيات القراءة',
        default=True
    )
    perm_write = fields.Boolean(
        string='صلاحيات الكتابة',
        default=True
    )
    perm_create = fields.Boolean(
        string='إنشاء صلاحيات الوصول',
        default=True
    )
    perm_unlink = fields.Boolean(
        string='حذف صلاحيات الوصول',
        default=False
    )


class UnifiedContractActionPermission(models.Model):
    _name = 'unified.contract.action.permission'
    _description = 'قواعد السجلات والإجراءات'
    _order = 'name'

    profile_id = fields.Many2one(
        'unified.contract.permission.profile',
        string='بروفايل الصلاحيات',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(
        string='اسم القاعدة',
        required=True,
        placeholder='مثال: قاعدة الوصول للشركة، قاعدة الحقول الإلزامية'
    )
    domain_force = fields.Char(
        string='شروط وقواعد السجل (Domain)',
        placeholder="[('company_id', 'in', company_ids)]"
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='الحقل المستهدف في القاعدة'
    )
    rule_type = fields.Selection([
        ('record', 'قاعدة تصفية سجلات (Record Filter)'),
        ('field_required', 'تحكم بالقول: إلزامي (Mandatory Field)'),
        ('field_optional', 'تحكم بالحقول: اختياري (Optional Field)'),
    ], string='نوع القاعدة', default='record', required=True)

    perm_read = fields.Boolean(
        string='قراءة',
        default=True
    )
    perm_write = fields.Boolean(
        string='كتابة',
        default=True
    )
    perm_create = fields.Boolean(
        string='إنشاء',
        default=True
    )
    perm_unlink = fields.Boolean(
        string='حذف',
        default=False
    )


class UnifiedContractPermissionProfile(models.Model):
    _name = 'unified.contract.permission.profile'
    _description = 'المجموعات والصلاحيات'
    _order = 'parent_id, name'

    name = fields.Char(
        string='الاسم',
        required=True,
        placeholder='مثال: مجموعة مدراء المشاريع الموحدة، مجموعة مهندسي التنفيذ'
    )
    app_name = fields.Char(
        string='التطبيق',
        default='مشاريع العقد الموحد',
        required=True
    )
    share_group = fields.Boolean(
        string='مشاركة المجموعة',
        default=False
    )
    can_revert_stage = fields.Boolean(
        string='السماح بإرجاع المراحل للسابقة',
        default=False,
        help='عند تفعيل هذا الخيار، يُسمح للمستخدمين التابعين لهذه المجموعة بإرجاع المشاريع وأوامر العمل إلى مراحل سابقة'
    )
    parent_id = fields.Many2one(
        'unified.contract.permission.profile',
        string='موروث من',
        ondelete='restrict'
    )
    inherited_profile_ids = fields.Many2many(
        'unified.contract.permission.profile',
        'rel_permission_profile_inherited',
        'profile_id',
        'inherited_id',
        string='موروث (Inherited Groups)'
    )
    user_ids = fields.Many2many(
        'res.users',
        'rel_permission_profile_users',
        'profile_id',
        'user_id',
        string='المستخدمون'
    )
    user_count = fields.Integer(
        string='عدد المستخدمين',
        compute='_compute_user_count'
    )
    team_ids = fields.One2many(
        'unified.contract.team',
        'permission_profile_id',
        string='فرق العمل المربوطة بهذا البروفايل'
    )
    menu_ids = fields.Many2many(
        'ir.ui.menu',
        'rel_permission_profile_menus',
        'profile_id',
        'menu_id',
        string='القوائم'
    )
    view_ids = fields.Many2many(
        'ir.ui.view',
        'rel_permission_profile_views',
        'profile_id',
        'view_id',
        string='أدوات العرض'
    )
    access_right_ids = fields.One2many(
        'unified.contract.field.permission',
        'profile_id',
        string='صلاحيات الوصول وحالات الحقول'
    )
    rule_ids = fields.One2many(
        'unified.contract.action.permission',
        'profile_id',
        string='قواعد السجلات'
    )
    description = fields.Text(
        string='الملاحظات'
    )
    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        default=lambda self: self.env.company
    )

    @api.depends('user_ids')
    def _compute_user_count(self):
        for record in self:
            record.user_count = len(record.user_ids)

    def write(self, vals):
        res = super(UnifiedContractPermissionProfile, self).write(vals)
        if 'user_ids' in vals and not self.env.context.get('skip_team_user_sync'):
            self.with_context(skip_team_user_sync=True)._sync_profile_users_to_teams()
        return res

    def _sync_profile_users_to_teams(self):
        """ Direction 2: Sync Permission Profile user_ids back to linked Teams """
        teams = self.env['unified.contract.team'].search([('permission_profile_id', 'in', self.ids)])
        for team in teams:
            if team.permission_profile_id:
                team.write({'member_ids': [(6, 0, team.permission_profile_id.user_ids.ids)]})

    def action_sync_team_users(self):
        """ Manual action button to trigger real-time user sync from linked teams """
        self.ensure_one()
        self._sync_all_team_users()
        return True

    def _sync_all_team_users(self):
        """ Direction 1: Sync all leaders and members from linked teams into user_ids """
        all_teams = self.env['unified.contract.team'].search([('permission_profile_id', 'in', self.ids)])
        team_map = {}
        for t in all_teams:
            pid = t.permission_profile_id.id
            if pid not in team_map:
                team_map[pid] = self.env['res.users']
            if t.leader_id:
                team_map[pid] |= t.leader_id
            if t.member_ids:
                team_map[pid] |= t.member_ids

        for profile in self:
            users = team_map.get(profile.id, self.env['res.users'])
            profile.with_context(skip_team_user_sync=True).write({'user_ids': [(6, 0, users.ids)]})

    @api.model_create_multi
    def create(self, vals_list):
        records = super(UnifiedContractPermissionProfile, self).create(vals_list)
        target_models = self.env['ir.model'].search([
            ('model', 'in', [
                'unified.contract.project',
                'unified.contract.work.order',
                'unified.contract.team',
                'unified.contract.stage',
                'unified.contract.work.order.stage'
            ])
        ])
        for record in records:
            if not record.access_right_ids and target_models:
                record._populate_all_module_field_permissions(target_models)
            if not record.rule_ids:
                record._populate_default_record_rules()
        return records

    def action_generate_all_module_access_rights(self):
        """ Regenerate field permissions and record rules """
        self.ensure_one()
        self.access_right_ids.unlink()
        target_models = self.env['ir.model'].search([
            ('model', 'in', [
                'unified.contract.project',
                'unified.contract.work.order',
                'unified.contract.team',
                'unified.contract.stage',
                'unified.contract.work.order.stage'
            ])
        ])
        self._populate_all_module_field_permissions(target_models)
        self._populate_default_record_rules()
        self._sync_all_team_users()
        return True

    def _populate_all_module_field_permissions(self, target_models):
        """ Create access rights rows with is_required boolean checkbox """
        existing_field_ids = set(self.access_right_ids.mapped('field_id.id'))
        fields_records = self.env['ir.model.fields'].search([
            ('model_id', 'in', target_models.ids),
            ('state', '=', 'base')
        ])
        new_lines = []
        for f in fields_records:
            if f.id not in existing_field_ids:
                clean_label = f.field_description or f.name
                is_req = f.required or f.name in ['name', 'code', 'project_id', 'stage_id', 'leader_id']
                new_lines.append({
                    'profile_id': self.id,
                    'model_id': f.model_id.id,
                    'field_id': f.id,
                    'name': clean_label,
                    'is_required': is_req,
                    'perm_read': True,
                    'perm_write': True,
                    'perm_create': True,
                    'perm_unlink': False,
                })
        if new_lines:
            self.env['unified.contract.field.permission'].create(new_lines)

    def _populate_default_record_rules(self):
        """ Pre-populate record rules """
        default_rules = [
            {
                'profile_id': self.id,
                'name': 'قاعدة الوصول حسب شركة المستخدم للمشاريع',
                'rule_type': 'record',
                'domain_force': "[('company_id', 'in', company_ids)]",
                'perm_read': True,
                'perm_write': True,
                'perm_create': True,
                'perm_unlink': False,
            },
            {
                'profile_id': self.id,
                'name': 'قاعدة الوصول لأوامر العمل المسندة للفريق والمسؤول',
                'rule_type': 'record',
                'domain_force': "['|', ('user_id', '=', user.id), ('team_ids.member_ids', 'in', [user.id])]",
                'perm_read': True,
                'perm_write': True,
                'perm_create': True,
                'perm_unlink': False,
            }
        ]
        existing_rule_names = self.rule_ids.mapped('name')
        new_rule_lines = [r for r in default_rules if r['name'] not in existing_rule_names]
        if new_rule_lines:
            self.env['unified.contract.action.permission'].create(new_rule_lines)
