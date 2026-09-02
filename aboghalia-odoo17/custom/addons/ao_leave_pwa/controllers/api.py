# -*- coding: utf-8 -*-
"""Leave PWA API + patches for ao_attendance_app_api timeoff manager endpoints.

Aligns pending/approve/refuse with ao_leave_approval (current_level / can_decide)
instead of the legacy OpenHRMS validation_status_ids list.
"""
import json
import logging

import werkzeug.wrappers
from odoo import http, _
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.ao_attendance_app_api.controllers.controllers import (
    TimeoffController,
    MultiCompanyEmployeeMixin,
    validate_token,
    valid_response,
    invalid_response,
    _t,
)

_logger = logging.getLogger(__name__)


def _safe_int(value, default=None):
    """Coerce to int safely (blocks injection-style garbage)."""
    try:
        if value is None or value is False or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value, max_len=500):
    if value is None:
        return ''
    text = str(value).strip()
    if len(text) > max_len:
        text = text[:max_len]
    return text


def _pwa_env_ar(env):
    """Arabic translations for PWA user-facing errors."""
    ctx = dict(env.context or {})
    ctx['lang'] = 'ar_001'
    return env(context=ctx)


def _friendly_leave_error(exc):
    """Map Odoo/technical errors to readable Arabic messages for the PWA."""
    raw = str(exc or '').strip()
    if not raw:
        return _(
            "تعذر إرسال طلب الإجازة. يرجى التحقق من البيانات والمحاولة مرة أخرى."
        )
    if any('\u0600' <= ch <= '\u06FF' for ch in raw):
        return raw
    lower = raw.lower()
    overlap_tokens = (
        'overlap', 'already booked', 'double-book', 'overlaps',
        'same day', 'conflicting',
    )
    if any(token in lower for token in overlap_tokens):
        return _(
            "يوجد لديك طلب إجازة آخر في نفس الفترة. "
            "يرجى اختيار تواريخ مختلفة أو انتظار معالجة الطلب السابق."
        )
    if any(token in lower for token in ('not enough', 'insufficient', 'exceed', 'balance')):
        return _("رصيد الإجازة غير كافٍ لهذا الطلب.")
    if 'manager' in lower and ('no' in lower or 'missing' in lower):
        return _(
            "لا يمكن إرسال الطلب لأن المدير المباشر غير محدد على ملف الموظف. "
            "يرجى التواصل مع الموارد البشرية."
        )
    if 'mandatory' in lower or 'required field' in lower:
        return _("يرجى تعبئة جميع الحقول المطلوبة قبل الإرسال.")
    if 'with_context' in lower or 'attributeerror' in lower:
        return _(
            "تعذر إرسال طلب الإجازة بسبب خطأ تقني. يرجى المحاولة مرة أخرى أو التواصل مع الموارد البشرية."
        )
    return raw


def _overlap_leave_error(employee, date_from, date_to, env):
    """Return a detailed Arabic message when dates clash with existing requests."""
    overlapping = env['hr.leave'].sudo().search([
        ('employee_id', '=', employee.id),
        ('state', 'not in', ('cancel', 'refuse')),
        ('request_date_from', '<=', date_to),
        ('request_date_to', '>=', date_from),
    ], order='request_date_from desc', limit=3)
    if not overlapping:
        return None
    state_labels = {
        'draft': _('مسودة'),
        'confirm': _('قيد المراجعة'),
        'validate1': _('قيد الاعتماد'),
        'validate': _('معتمد'),
    }
    details = []
    for leave in overlapping:
        state_label = state_labels.get(leave.state, leave.state)
        details.append(_(
            "• من %(date_from)s إلى %(date_to)s (%(state)s)",
            date_from=leave.request_date_from.strftime('%d-%m-%Y') if leave.request_date_from else '—',
            date_to=leave.request_date_to.strftime('%d-%m-%Y') if leave.request_date_to else '—',
            state=state_label,
        ))
    return _(
        "يوجد طلب إجازة آخر يتداخل مع الفترة المحددة:\n%(details)s\n"
        "يرجى اختيار تواريخ مختلفة أو انتظار معالجة الطلب السابق.",
        details="\n".join(details),
    )


def _leave_create_error_response(exc, status=400, code='user_error'):
    message = _friendly_leave_error(exc)
    return invalid_response(code, message, status)


LEAVE_APPROVAL_GROUPS = (
    'ao_leave_approval.group_leave_project_manager',
    'ao_leave_approval.group_leave_general_manager',
    'ao_leave_approval.group_leave_hr_manager',
    'ao_leave_approval.group_leave_force_approver',
)


def _user_is_leave_approver(user):
    if not user:
        return False
    if user.has_group('hr_holidays.group_hr_holidays_user') or user.has_group(
        'hr_holidays.group_hr_holidays_manager'
    ):
        return True
    for xmlid in LEAVE_APPROVAL_GROUPS:
        if user.has_group(xmlid):
            return True
    # Direct managers of anyone with a user also act as leave approvers
    Emp = request.env['hr.employee'].sudo()
    return bool(Emp.search_count([
        ('parent_id.user_id', '=', user.id),
        ('user_id', '!=', False),
    ], limit=1))


def _format_leave_cycle(self, req, include_employee_name=False, include_company=False, include_validation=False):
    """Serialize hr.leave including ao_leave_approval cycle fields."""
    req = req.sudo()
    data = {
        "id": req.id,
        "name": req.name or "",
        "holiday_type": (
            _("غير مدفوعه") if getattr(req.holiday_status_id, 'unpaid', False) else _("مدفوعه")
        ),
        "holiday_status_id": req.holiday_status_id.id,
        "request_date_from": req.request_date_from.strftime('%Y-%m-%d') if req.request_date_from else None,
        "request_date_to": req.request_date_to.strftime('%Y-%m-%d') if req.request_date_to else None,
        "number_of_days": float(req.number_of_days or 0.0),
        "state": req.state,
        "state_display": dict(req._fields['state'].selection).get(req.state, req.state),
        "create_date": req.create_date.strftime('%Y-%m-%d %H:%M:%S') if req.create_date else None,
    }
    if include_employee_name:
        data["employee_name"] = req.employee_id.name or ""
        data["employee_id"] = req.employee_id.id
    if include_company and req.employee_id and req.employee_id.company_id:
        data["company_id"] = req.employee_id.company_id.id
        data["company_name"] = req.employee_id.company_id.name or ""

    hours_per_day = 8.0
    if req.employee_id:
        try:
            hours_per_day = request.env['saudi.leave.balance'].sudo()._get_hours_per_day(req.employee_id)
        except Exception:
            hours_per_day = 8.0
    data["hours_per_day"] = hours_per_day
    data["number_of_hours"] = round(float(req.number_of_days or 0.0) * hours_per_day, 1)

    current_level = getattr(req, 'current_level', False) or 'none'
    data["current_level"] = current_level
    if hasattr(req, '_get_current_level_label'):
        try:
            data["current_level_label"] = req._get_current_level_label(current_level) or ""
        except Exception:
            data["current_level_label"] = current_level
    else:
        data["current_level_label"] = current_level

    can_decide = False
    user = self._current_user()
    try:
        leave_sudo = req  # already sudo'd above
        if hasattr(leave_sudo, '_user_can_decide'):
            can_decide = bool(leave_sudo._user_can_decide(user))
        elif 'can_decide' in leave_sudo._fields:
            can_decide = bool(leave_sudo.with_user(user.id).sudo().can_decide)
    except Exception:
        can_decide = False
    data["can_decide"] = can_decide

    # Who must act now (for employee + everyone in the cycle)
    if data["state"] == 'confirm' and current_level not in (False, 'none', 'done'):
        data["waiting_for_key"] = current_level
        data["waiting_for"] = data.get("current_level_label") or current_level
    elif data["state"] == 'validate':
        data["waiting_for_key"] = "done"
        data["waiting_for"] = ""
    else:
        data["waiting_for_key"] = data["state"]
        data["waiting_for"] = ""

    # Did this user already approve at some level?
    my_decision = None
    uid = user.id
    if _user_touched_leave(req, uid):
        my_decision = "approved"
    elif data["state"] == "refuse" and can_decide is False:
        # rough: if refused and user is/was in cycle visibility
        my_decision = None
    data["my_decision"] = my_decision

    balance_warning = getattr(req, 'pwa_balance_warning', False) or False
    if balance_warning:
        data["balance_warning"] = balance_warning

    if include_validation:
        data["multi_level_validation"] = True
        data["is_validator"] = can_decide
        data["my_approval_status"] = False if can_decide else None
        # Progress through 4 levels for UI hints
        level_order = ['manager', 'project_manager', 'general_manager', 'hr_manager', 'done']
        try:
            idx = level_order.index(current_level) if current_level in level_order else 0
        except ValueError:
            idx = 0
        data["validators_approved"] = max(0, idx)
        data["validators_total"] = 4

    return data


def _user_touched_leave(leave, user_id):
    """True if this user already acted as an approver on this leave."""
    for field in (
        'manager_approver_id',
        'project_manager_approver_id',
        'general_manager_approver_id',
        'hr_manager_approver_id',
    ):
        if hasattr(leave, field) and getattr(leave, field) and getattr(leave, field).id == user_id:
            return True
    return False


def _load_manager_leave_cycle(self, request_id, allowed_company_ids):
    try:
        req_id = int(request_id)
    except Exception:
        return None, None
    user = self._current_user()
    allowed = [int(c) for c in (allowed_company_ids or []) if c]
    Leave = request.env['hr.leave'].sudo().with_context(allowed_company_ids=allowed or None)
    leave = Leave.browse(req_id)
    if not leave.exists():
        return None, None
    company_id = leave.employee_id.company_id.id if leave.employee_id.company_id else False
    if allowed and company_id and int(company_id) not in allowed:
        return None, None
    leave_sudo = leave.sudo()
    if hasattr(leave_sudo, '_user_can_decide') and leave_sudo._user_can_decide(user):
        return leave_sudo, company_id
    if _user_touched_leave(leave_sudo, user.id):
        return leave_sudo, company_id
    if user.has_group('hr_holidays.group_hr_holidays_manager') or user.has_group(
        'ao_leave_approval.group_leave_force_approver'
    ):
        return leave_sudo, company_id
    return None, None


def _get_all_pending_requests_cycle(self, **kwargs):
    try:
        user = self._current_user()
        allowed_company_ids = self._allowed_company_ids() or []
        allowed_company_ids = [int(c) for c in allowed_company_ids if c]
        if not allowed_company_ids:
            allowed_company_ids = [int(self._current_company_id() or 0)]
        try:
            page = max(1, int(kwargs.get('page', 1)))
            limit = max(1, min(int(kwargs.get('limit', 50)), 100))
        except Exception:
            page, limit = 1, 50

        Leave = request.env['hr.leave'].sudo().with_context(allowed_company_ids=allowed_company_ids)
        domain = [
            ('state', '=', 'confirm'),
            ('holiday_type', '=', 'employee'),
            ('employee_id.company_id', 'in', allowed_company_ids),
        ]
        candidates = Leave.search(domain, order='create_date desc')
        actually_pending = candidates.filtered(
            lambda l: hasattr(l, '_user_can_decide') and l.sudo()._user_can_decide(user)
        )
        total_count = len(actually_pending)
        offset = (page - 1) * limit
        page_slice = actually_pending[offset:offset + limit]

        response_data = {
            "data": [
                self._format_leave(
                    r, include_employee_name=True, include_company=True, include_validation=True,
                )
                for r in page_slice
            ],
            "meta": {"pagination": self._serialize_pagination(page, limit, total_count)},
        }
        return valid_response(response_data)
    except Exception as e:
        _logger.exception("get_all_pending_requests (cycle) failed")
        return invalid_response("server_error", str(e), 500)


def _get_all_approved_requests_cycle(self, **kwargs):
    """Leaves this user already approved at their level (may still be in cycle)."""
    try:
        user = self._current_user()
        allowed_company_ids = self._allowed_company_ids() or []
        allowed_company_ids = [int(c) for c in allowed_company_ids if c]
        if not allowed_company_ids:
            allowed_company_ids = [int(self._current_company_id() or 0)]
        try:
            page = max(1, int(kwargs.get('page', 1)))
            limit = max(1, min(int(kwargs.get('limit', 50)), 100))
        except Exception:
            page, limit = 1, 50
        offset = (page - 1) * limit

        Leave = request.env['hr.leave'].sudo().with_context(allowed_company_ids=allowed_company_ids)
        # "مقبول" for an approver = I approved at my stage (not only fully validated)
        domain = [
            ('holiday_type', '=', 'employee'),
            ('employee_id.company_id', 'in', allowed_company_ids),
            ('state', 'in', ['confirm', 'validate1', 'validate']),
            '|', '|', '|',
            ('manager_approver_id', '=', user.id),
            ('project_manager_approver_id', '=', user.id),
            ('general_manager_approver_id', '=', user.id),
            ('hr_manager_approver_id', '=', user.id),
        ]
        total_count = Leave.search_count(domain)
        leaves = Leave.search(domain, order='write_date desc, create_date desc', limit=limit, offset=offset)
        response_data = {
            "data": [
                self._format_leave(r, include_employee_name=True, include_company=True, include_validation=True)
                for r in leaves
            ],
            "meta": {"pagination": self._serialize_pagination(page, limit, total_count)},
        }
        return valid_response(response_data)
    except Exception as e:
        _logger.exception("get_all_approved_requests (cycle) failed")
        return invalid_response("server_error", str(e), 500)


def _get_all_refused_requests_cycle(self, **kwargs):
    try:
        user = self._current_user()
        allowed_company_ids = self._allowed_company_ids() or []
        allowed_company_ids = [int(c) for c in allowed_company_ids if c]
        if not allowed_company_ids:
            allowed_company_ids = [int(self._current_company_id() or 0)]
        try:
            page = max(1, int(kwargs.get('page', 1)))
            limit = max(1, min(int(kwargs.get('limit', 50)), 100))
        except Exception:
            page, limit = 1, 50
        offset = (page - 1) * limit

        Leave = request.env['hr.leave'].sudo().with_context(allowed_company_ids=allowed_company_ids)
        domain = [
            ('state', '=', 'refuse'),
            ('holiday_type', '=', 'employee'),
            ('employee_id.company_id', 'in', allowed_company_ids),
            '|', '|', '|', '|',
            ('manager_approver_id', '=', user.id),
            ('project_manager_approver_id', '=', user.id),
            ('general_manager_approver_id', '=', user.id),
            ('hr_manager_approver_id', '=', user.id),
            ('employee_id.parent_id.user_id', '=', user.id),
        ]
        total_count = Leave.search_count(domain)
        leaves = Leave.search(domain, order='create_date desc', limit=limit, offset=offset)
        response_data = {
            "data": [
                self._format_leave(r, include_employee_name=True, include_company=True)
                for r in leaves
            ],
            "meta": {"pagination": self._serialize_pagination(page, limit, total_count)},
        }
        return valid_response(response_data)
    except Exception as e:
        _logger.exception("get_all_refused_requests (cycle) failed")
        return invalid_response("server_error", str(e), 500)


def _approve_timeoff_request_cycle(self, **kwargs):
    try:
        try:
            payload = json.loads(request.httprequest.data.decode() or "{}")
        except Exception:
            return invalid_response("bad_json", _t("bad_json"), 400)
        request_id = _safe_int(payload.get("request_id"))
        if not request_id:
            return invalid_response("missing_fields", _t("missing_fields"), 400)

        user = self._current_user()
        allowed_company_ids = self._allowed_company_ids() or [int(self._current_company_id() or 0)]
        leave, _company_id = self._load_manager_leave(request_id, allowed_company_ids)
        if not leave:
            return invalid_response("not_found", _t("request_not_found_or_not_validator"), 404)

        leave_sudo = leave.sudo()
        user_is_force = user.has_group('ao_leave_approval.group_leave_force_approver')
        if hasattr(leave_sudo, '_user_can_decide') and not leave_sudo._user_can_decide(user):
            return invalid_response("access_error", _("You cannot approve this request at the current level."), 403)

        try:
            # with_user().sudo() so env.user is the approver but ACL/record rules don't block.
            leave_run = leave_sudo.with_user(user.id).sudo()
            if leave_sudo.state == 'confirm':
                if user_is_force and hasattr(leave_run, 'action_force_approve'):
                    leave_run.action_force_approve()
                else:
                    leave_run.action_approve()
            elif leave_sudo.state == 'validate1':
                leave_run.action_validate()
            else:
                return invalid_response(
                    "bad_state",
                    f"{_t('bad_state_approve')} ({leave_sudo.state})",
                    400,
                )
        except (UserError, AccessError) as err:
            # Force/validate may finish the leave then raise a trailing ACL/message error.
            # If the request is already done, treat as success for PWA UX.
            leave_sudo.invalidate_recordset()
            if leave_sudo.state not in ('validate', 'refuse'):
                code = "user_error" if isinstance(err, UserError) else "access_error"
                status = 400 if isinstance(err, UserError) else 403
                return invalid_response(code, str(err), status)

        leave_sudo.invalidate_recordset()
        fully_approved = leave_sudo.state == 'validate'
        level_label = (
            leave_sudo._get_current_level_label() if hasattr(leave_sudo, '_get_current_level_label') else ""
        )
        if fully_approved:
            msg = _t("fully_approved")
        else:
            msg = _("Approved. Forwarded to: %s") % (level_label or leave_sudo.current_level)
        return valid_response({
            "message": msg,
            "request_id": leave_sudo.id,
            "state": leave_sudo.state,
            "state_display": dict(leave_sudo._fields['state'].selection).get(leave_sudo.state, leave_sudo.state),
            "fully_approved": fully_approved,
            "current_level": getattr(leave_sudo, 'current_level', None),
            "current_level_label": level_label,
            "waiting_for": level_label if not fully_approved else "",
            "waiting_for_key": getattr(leave_sudo, 'current_level', None) if not fully_approved else "done",
        })
    except Exception as e:
        _logger.exception("approve_timeoff_request (cycle) failed")
        return invalid_response("server_error", str(e), 500)


def _refuse_timeoff_request_cycle(self, **kwargs):
    try:
        try:
            payload = json.loads(request.httprequest.data.decode() or "{}")
        except Exception:
            return invalid_response("bad_json", _t("bad_json"), 400)
        request_id = _safe_int(payload.get("request_id"))
        if not request_id:
            return invalid_response("missing_fields", _t("missing_fields"), 400)

        user = self._current_user()
        allowed_company_ids = self._allowed_company_ids() or [int(self._current_company_id() or 0)]
        leave, _company_id = self._load_manager_leave(request_id, allowed_company_ids)
        if not leave:
            return invalid_response("not_found", _t("request_not_found_or_not_validator"), 404)

        if leave.state == 'refuse':
            return invalid_response("already_refused", _t("already_refused"), 400)

        leave_sudo = leave.sudo()
        if hasattr(leave_sudo, '_user_can_decide') and not leave_sudo._user_can_decide(user):
            return invalid_response("access_error", _("You cannot refuse this request at the current level."), 403)

        try:
            leave_sudo.with_user(user.id).sudo().action_refuse()
        except UserError as ue:
            return invalid_response("user_error", str(ue), 400)
        except AccessError as ae:
            return invalid_response("access_error", str(ae), 403)

        leave_sudo.invalidate_recordset()
        return valid_response({
            "message": _t("refuse_success"),
            "request_id": leave_sudo.id,
            "state": leave_sudo.state,
            "state_display": dict(leave_sudo._fields['state'].selection).get(leave_sudo.state, leave_sudo.state),
        })
    except Exception as e:
        _logger.exception("refuse_timeoff_request (cycle) failed")
        return invalid_response("server_error", str(e), 500)


# ---------------------------------------------------------------------------
# Only patch non-routed helpers. Replacing @http.route methods strips routing
# metadata on registry rebuild (that broke /api/login on beta).
# Manager cycle endpoints live under /leave/api/manager/... below.
# ---------------------------------------------------------------------------
TimeoffController._format_leave = _format_leave_cycle
TimeoffController._load_manager_leave = _load_manager_leave_cycle


class LeavePwaApi(http.Controller, MultiCompanyEmployeeMixin):
    """Dedicated /leave/api helpers for the PWA (login + cycle-aware manager APIs)."""

    def _current_user(self):
        return request.env.user

    def _format_leave(self, req, include_employee_name=False, include_company=False, include_validation=False):
        return _format_leave_cycle(
            self, req,
            include_employee_name=include_employee_name,
            include_company=include_company,
            include_validation=include_validation,
        )

    def _serialize_pagination(self, page, limit, total):
        total_pages = (total + limit - 1) // limit if limit else 1
        return {
            "current_page": page,
            "per_page": limit,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }

    def _load_manager_leave(self, request_id, allowed_company_ids):
        return _load_manager_leave_cycle(self, request_id, allowed_company_ids)

    @http.route('/leave/api/login', type='http', auth='none', methods=['POST'], csrf=False)
    def leave_login(self, **kwargs):
        """PWA login against the current Odoo DB (beta/live). Uses api.access_token."""
        try:
            try:
                payload = json.loads(request.httprequest.data.decode() or "{}")
            except Exception:
                return invalid_response("bad_json", "Request body must be valid JSON", 400)
            username = _safe_str(payload.get("login"), max_len=128)
            password = payload.get("password") or ""
            if not isinstance(password, str):
                password = str(password)
            if len(password) > 256:
                return invalid_response("invalid_input", "Invalid credentials", 400)
            if not username or not password:
                return invalid_response("missing_fields", "login and password are required", 400)

            db = request.env.cr.dbname
            try:
                request.session.authenticate(db, username, password)
            except AccessError as aee:
                return invalid_response("access_error", "Error: %s" % aee.name, 403)
            except AccessDenied:
                return invalid_response("access_denied", "Login or password invalid", 401)

            uid = request.session.uid
            if not uid:
                return invalid_response("authentication_failed", "authentication failed", 401)

            user = request.env.user
            access_token = request.env["api.access_token"].find_or_create_token(
                user_id=uid, create=True,
            )
            is_manager = _user_is_leave_approver(user)
            companies = [{"id": c.id, "name": c.name} for c in user.company_ids]
            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({
                    "uid": uid,
                    "default_company_id": user.company_id.id if user.company_id else None,
                    "companies": companies,
                    "partner_id": user.partner_id.id,
                    "access_token": access_token,
                    "company_name": user.company_id.name if user.company_id else "",
                    "leave_approver": bool(is_manager),
                    "access": {
                        "timeoff": "manager" if is_manager else "user",
                    },
                }),
            )
        except Exception as e:
            _logger.exception("leave_login failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/leave/api/me', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_me(self, **kwargs):
        try:
            user = self._current_user()
            is_manager = _user_is_leave_approver(user)
            companies = [{"id": c.id, "name": c.name} for c in user.company_ids]
            employee = user.employee_id
            return valid_response({
                "uid": user.id,
                "name": user.name,
                "login": user.login,
                "employee_name": employee.name if employee else user.name,
                "default_company_id": user.company_id.id if user.company_id else None,
                "companies": companies,
                "leave_approver": is_manager,
                "access": {"timeoff": "manager" if is_manager else "user"},
            })
        except Exception as e:
            _logger.exception("leave_me failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/leave/api/manager/pending_count', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_pending_count(self, **kwargs):
        try:
            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids() or []
            allowed_company_ids = [int(c) for c in allowed_company_ids if c]
            if not allowed_company_ids:
                allowed_company_ids = [int(self._current_company_id() or 0)]
            Leave = request.env['hr.leave'].sudo().with_context(allowed_company_ids=allowed_company_ids)
            candidates = Leave.search([
                ('state', '=', 'confirm'),
                ('holiday_type', '=', 'employee'),
                ('employee_id.company_id', 'in', allowed_company_ids),
            ])
            count = len(candidates.filtered(
                lambda l: hasattr(l, '_user_can_decide') and l.sudo()._user_can_decide(user)
            ))
            return valid_response({"count": count})
        except Exception as e:
            _logger.exception("leave_pending_count failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/leave/api/manager/timeoff/requests/pending', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_manager_pending(self, **kwargs):
        return _get_all_pending_requests_cycle(self, **kwargs)

    @validate_token
    @http.route('/leave/api/manager/timeoff/requests/approved', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_manager_approved(self, **kwargs):
        return _get_all_approved_requests_cycle(self, **kwargs)

    @validate_token
    @http.route('/leave/api/manager/timeoff/requests/refused', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_manager_refused(self, **kwargs):
        return _get_all_refused_requests_cycle(self, **kwargs)

    @validate_token
    @http.route('/leave/api/manager/timeoff/approve', type='http', auth='public', methods=['POST'], csrf=False)
    def leave_manager_approve(self, **kwargs):
        return _approve_timeoff_request_cycle(self, **kwargs)

    @validate_token
    @http.route('/leave/api/manager/timeoff/refuse', type='http', auth='public', methods=['POST'], csrf=False)
    def leave_manager_refuse(self, **kwargs):
        return _refuse_timeoff_request_cycle(self, **kwargs)

    # ------------------------------------------------------------------
    # Employee endpoints — same 4-level cycle as Odoo backend
    # ------------------------------------------------------------------

    def _resolve_employee(self, user):
        """Find employee for user; prefer selected company, then any company."""
        company_id = int(self._current_company_id() or 0)
        employee = self._get_employee_for_user_in_company(user, company_id)
        if employee:
            return employee, int(employee.company_id.id)
        return None, company_id

    @validate_token
    @http.route('/leave/api/employee/types', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_employee_types(self, **kwargs):
        try:
            user = self._current_user()
            employee, company_id = self._resolve_employee(user)
            if not employee:
                return invalid_response(
                    "no_employee",
                    _("No employee linked to this user. Link a user on the employee form."),
                    400,
                )
            envc = self._force_company_env(company_id=company_id)
            data = envc['saudi.leave.balance'].sudo().get_pwa_leave_types(company_id)
            return valid_response(data)
        except Exception as e:
            _logger.exception("leave_employee_types failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/leave/api/employee/balance', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_employee_balance(self, **kwargs):
        try:
            user = self._current_user()
            employee, company_id = self._resolve_employee(user)
            if not employee:
                return invalid_response(
                    "no_employee",
                    _("No employee linked to this user. Link a user on the employee form."),
                    400,
                )
            envc = self._force_company_env(company_id=company_id)
            employee = envc['hr.employee'].sudo().browse(employee.id)
            saudi = envc['saudi.leave.balance'].sudo().compute_employee_balance(employee)
            return valid_response(saudi)
        except Exception as e:
            _logger.exception("leave_employee_balance failed")
            return invalid_response("server_error", str(e), 500)

    def _employee_requests(self, states):
        user = self._current_user()
        employee, company_id = self._resolve_employee(user)
        if not employee:
            return invalid_response(
                "no_employee",
                _("No employee linked to this user. Link a user on the employee form."),
                400,
            )
        envc = self._force_company_env(company_id=company_id)
        domain = [
            ('employee_id', '=', employee.id),
            ('state', 'in', list(states)),
        ]
        leaves = envc['hr.leave'].sudo().search(domain, order='create_date desc')
        return valid_response([
            self._format_leave(r, include_employee_name=True, include_company=True)
            for r in leaves
        ])

    @validate_token
    @http.route('/leave/api/employee/requests/pending', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_employee_pending(self, **kwargs):
        try:
            return self._employee_requests(('confirm', 'validate1'))
        except Exception as e:
            _logger.exception("leave_employee_pending failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/leave/api/employee/requests/approved', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_employee_approved(self, **kwargs):
        try:
            return self._employee_requests(('validate',))
        except Exception as e:
            _logger.exception("leave_employee_approved failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/leave/api/employee/requests/refused', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_employee_refused(self, **kwargs):
        try:
            return self._employee_requests(('refuse',))
        except Exception as e:
            _logger.exception("leave_employee_refused failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/leave/api/employee/create', type='http', auth='public', methods=['POST'], csrf=False)
    def leave_employee_create(self, **kwargs):
        """Create leave and enter ao_leave_approval cycle (Manager → … → HR)."""
        from datetime import datetime as dt

        try:
            user = self._current_user()
            employee, company_id = self._resolve_employee(user)
            if not employee:
                return invalid_response(
                    "no_employee",
                    _("No employee linked to this user. Link a user on the employee form."),
                    400,
                )
            try:
                payload = json.loads(request.httprequest.data.decode() or "{}")
            except Exception:
                return invalid_response("bad_json", _t("bad_json"), 400)

            holiday_status_id = _safe_int(payload.get("holiday_status_id"))
            request_date_from = _safe_str(payload.get("request_date_from"), max_len=32)
            request_date_to = _safe_str(payload.get("request_date_to"), max_len=32)
            name = _safe_str(payload.get("name"), max_len=200) or _("Time Off Request")
            request_unit_half = bool(payload.get("request_unit_half") or False)
            request_date_from_period = _safe_str(payload.get("request_date_from_period"), max_len=8).lower()

            if not holiday_status_id or not request_date_from or not request_date_to:
                return invalid_response("missing_fields", _t("create_missing_fields"), 400)
            if request_unit_half and request_date_from_period not in ("am", "pm"):
                return invalid_response("missing_fields", _t("create_half_day_period"), 400)

            try:
                date_from = dt.strptime(request_date_from, '%Y-%m-%d').date()
                date_to = dt.strptime(request_date_to, '%Y-%m-%d').date()
            except ValueError:
                return invalid_response("bad_date", _t("bad_date"), 400)
            if date_to < date_from:
                return invalid_response("bad_date_range", _t("bad_date_range"), 400)

            envc = self._force_company_env(company_id=company_id)
            env_ar = _pwa_env_ar(envc)
            employee = envc['hr.employee'].sudo().browse(employee.id)
            leave_type = envc['hr.leave.type'].sudo().browse(holiday_status_id)
            if not leave_type.exists():
                return invalid_response("leave_type_not_found", _t("leave_type_not_found"), 400)

            overlap_msg = _overlap_leave_error(employee, date_from, date_to, env_ar)
            if overlap_msg:
                return invalid_response("leave_overlap", overlap_msg, 400)

            balance_warning = None
            approver_balance_note = None
            balance_check = None
            if not getattr(leave_type, 'unpaid', False):
                balance_check = envc['saudi.leave.balance'].sudo().check_paid_leave_request(
                    employee, date_from, date_to, half_day=request_unit_half,
                )
                if balance_check.get('warning') == 'no_remaining_days':
                    balance_warning = _(
                        "تنبيه: لا يوجد لديك أيام إجازة متبقية. "
                        "يمكنك إرسال الطلب، ولكن الإجازة تُحسب من رصيدك فقط بعد اعتمادها."
                    )
                    approver_balance_note = _(
                        "تنبيه للمعتمد: الموظف لا يملك أيام إجازة مدفوعة متبقية في رصيده الحالي."
                    )
                elif balance_check.get('warning') == 'insufficient_days':
                    balance_warning = _(
                        "تنبيه: طلبك (%(requested)s يوم) أكبر من رصيدك المتبقي (%(remaining)s يوم). "
                        "يمكنك إرسال الطلب على أي حال.",
                        requested=balance_check['requested'],
                        remaining=balance_check['remaining'],
                    )
                    approver_balance_note = _(
                        "تنبيه للمعتمد: رصيد الموظف المتبقي (%(remaining)s يوم) "
                        "أقل من المطلوب في هذا الطلب (%(requested)s يوم).",
                        requested=balance_check['requested'],
                        remaining=balance_check['remaining'],
                    )

            # Require manager for cycle (same rule as ao_leave_approval)
            if not employee.parent_id or not employee.parent_id.user_id:
                return invalid_response(
                    "no_manager",
                    _("Employee %(name)s has no manager with a linked user. "
                      "Set the Manager on the employee before requesting time off.",
                      name=employee.name),
                    400,
                )

            ctx = dict(envc.context or {})
            ctx.update({
                "employee_id": int(employee.id),
                "default_employee_id": int(employee.id),
            })
            vals = {
                'name': name,
                'employee_id': int(employee.id),
                'holiday_status_id': holiday_status_id,
                'request_date_from': date_from,
                'request_date_to': date_to if not request_unit_half else date_from,
                'request_unit_half': request_unit_half,
                'request_date_from_period': request_date_from_period if request_unit_half else False,
                'company_id': company_id,
                'current_level': 'manager',
            }
            if approver_balance_note:
                vals['pwa_balance_warning'] = approver_balance_note

            # Create as the real user so ACLs/mail match backend behavior
            Leave = envc['hr.leave'].with_user(user.id).with_context(ctx)
            try:
                leave = Leave.create(vals)
            except (UserError, ValidationError) as ue:
                return _leave_create_error_response(ue, status=400, code='user_error')

            if leave.state == 'draft' and hasattr(leave, 'action_confirm'):
                try:
                    leave.action_confirm()
                except (UserError, ValidationError) as ue:
                    leave.sudo().unlink()
                    return _leave_create_error_response(ue, status=400, code='validation_error')

            # Ensure cycle level is set even if create path skipped it
            if leave.state == 'confirm' and getattr(leave, 'current_level', 'none') in (False, 'none'):
                leave.sudo().write({'current_level': 'manager'})
                if hasattr(leave, 'activity_update'):
                    leave.activity_update()

            leave.invalidate_recordset()
            data = self._format_leave(leave, include_employee_name=True, include_company=True)
            data["cycle"] = "ao_leave_approval"
            data["message"] = _(
                "Leave submitted. Waiting for: %(level)s",
                level=data.get("current_level_label") or _("Direct Manager"),
            )
            if balance_warning:
                data["balance_warning"] = balance_warning
            if balance_check:
                data["balance_check"] = balance_check
            return valid_response(data, status=201)
        except (UserError, ValidationError) as e:
            return _leave_create_error_response(e, status=400, code='user_error')
        except AccessError as e:
            return invalid_response("access_error", _friendly_leave_error(e), 403)
        except Exception as e:
            _logger.exception("leave_employee_create failed")
            return invalid_response("server_error", str(e), 500)

    # ------------------------------------------------------------------
    # Push notifications (Web Push registration; delivery needs HTTPS)
    # ------------------------------------------------------------------

    @validate_token
    @http.route('/leave/api/push/vapid', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_push_vapid(self, **kwargs):
        try:
            public = request.env['leave.pwa.subscription'].sudo().get_vapid_public_key()
            return valid_response({
                "publicKey": public or False,
                "secure_context_required": True,
            })
        except Exception as e:
            _logger.exception("leave_push_vapid failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/leave/api/push/subscribe', type='http', auth='public', methods=['POST'], csrf=False)
    def leave_push_subscribe(self, **kwargs):
        try:
            try:
                payload = json.loads(request.httprequest.data.decode() or "{}")
            except Exception:
                return invalid_response("bad_json", "Request body must be valid JSON", 400)
            subscription = payload.get("subscription") or payload
            if not isinstance(subscription, dict):
                return invalid_response("bad_subscription", "Invalid push subscription", 400)
            ua = request.httprequest.headers.get('User-Agent') or ''
            rec = request.env['leave.pwa.subscription'].sudo().register_subscription(
                self._current_user(), subscription, user_agent=ua,
            )
            if not rec:
                return invalid_response("bad_subscription", "Invalid push subscription", 400)
            return valid_response({"ok": True, "id": rec.id})
        except Exception as e:
            _logger.exception("leave_push_subscribe failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/leave/api/push/unsubscribe', type='http', auth='public', methods=['POST'], csrf=False)
    def leave_push_unsubscribe(self, **kwargs):
        try:
            try:
                payload = json.loads(request.httprequest.data.decode() or "{}")
            except Exception:
                return invalid_response("bad_json", "Request body must be valid JSON", 400)
            endpoint = _safe_str(payload.get("endpoint"), max_len=2048)
            request.env['leave.pwa.subscription'].sudo().unregister_endpoint(
                self._current_user(), endpoint,
            )
            return valid_response({"ok": True})
        except Exception as e:
            _logger.exception("leave_push_unsubscribe failed")
            return invalid_response("server_error", str(e), 500)
