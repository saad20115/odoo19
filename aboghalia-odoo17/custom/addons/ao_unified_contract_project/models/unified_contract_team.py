# -*- coding: utf-8 -*-

from odoo import models, fields, api

class UnifiedContractTeam(models.Model):
    _name = 'unified.contract.team'
    _description = 'إدارة فريق العمل'
    _order = 'project_id, sequence, id'

    name = fields.Char(
        string='اسم فريق العمل',
        required=True,
        placeholder='مثال: فريق المعاينة والتصاريح - حي المروة'
    )
    sequence = fields.Integer(
        string='التسلسل',
        default=10
    )
    project_id = fields.Many2one(
        'unified.contract.project',
        string='مشروع العقد الموحد',
        required=True,
        ondelete='cascade'
    )
    stage_id = fields.Many2one(
        'unified.contract.stage',
        string='مرحلة التنفيذ المرتبطة بالفريق',
        help='حدد مرحلة التنفيذ المسندة لهذا الفريق'
    )
    work_order_stage_id = fields.Many2one(
        'unified.contract.work.order.stage',
        string='مرحلة أمر العمل المرتبطة'
    )
    leader_id = fields.Many2one(
        'res.users',
        string='مدير الفريق / رئيس المجموعة',
        required=True,
        help='المستخدم المسؤول عن قيادة هذا الفريق'
    )
    member_ids = fields.Many2many(
        'res.users',
        'unified_contract_team_users_rel',
        'team_id',
        'user_id',
        string='أعضاء الفريق والمتعاونين',
        help='يمكن اختيار وتعيين أكثر من موظف/عضو في الفريق'
    )
    member_count = fields.Integer(
        string='عدد الأعضاء',
        compute='_compute_member_count'
    )
    permission_profile_id = fields.Many2one(
        'unified.contract.permission.profile',
        string='بروفايل / مجموعة الصلاحيات المعتمدة',
        help='حدد مجموعة الصلاحيات المجهزة مسبقاً لهذا الفريق'
    )
    notes = fields.Text(
        string='نطاق عمل وتوجيهات الفريق'
    )
    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        related='project_id.company_id',
        store=True,
        readonly=True
    )

    @api.depends('member_ids')
    def _compute_member_count(self):
        for record in self:
            record.member_count = len(record.member_ids)

    @api.onchange('leader_id', 'member_ids', 'permission_profile_id')
    def _onchange_sync_users(self):
        if self.permission_profile_id and self.permission_profile_id.id:
            self.permission_profile_id._sync_all_team_users()

    @api.model_create_multi
    def create(self, vals_list):
        records = super(UnifiedContractTeam, self).create(vals_list)
        if not self.env.context.get('skip_team_user_sync'):
            records._sync_users_to_permission_profile()
        return records

    def write(self, vals):
        res = super(UnifiedContractTeam, self).write(vals)
        if ('member_ids' in vals or 'leader_id' in vals or 'permission_profile_id' in vals) and not self.env.context.get('skip_team_user_sync'):
            self._sync_users_to_permission_profile()
        return res

    def unlink(self):
        profiles = self.mapped('permission_profile_id')
        res = super(UnifiedContractTeam, self).unlink()
        if not self.env.context.get('skip_team_user_sync'):
            profiles._sync_all_team_users()
        return res

    def _sync_users_to_permission_profile(self):
        """ Automatically sync team leader and members into the assigned permission group's user_ids """
        for team in self:
            if team.permission_profile_id:
                team.permission_profile_id._sync_all_team_users()
