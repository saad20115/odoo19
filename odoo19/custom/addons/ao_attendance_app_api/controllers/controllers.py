# -*- coding: utf-8 -*-
import os
import json
import logging
import functools
import werkzeug.wrappers
import pytz
import base64
from datetime import datetime, date
import calendar
from odoo import fields, http
from odoo.http import request, Response
from odoo.exceptions import AccessDenied, AccessError, ValidationError, UserError
from dotenv import load_dotenv
from odoo.modules.module import get_module_resource
from bs4 import BeautifulSoup
import re

# from odoo.custom_addons.ao_attendance_app_api.models.common import invalid_response, valid_response


env_file = get_module_resource('ao_attendance_app_api', 'config', '.env')
load_dotenv(dotenv_path=env_file)
HOST = os.getenv('HOST')
_logger = logging.getLogger(__name__)


def default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, bytes):
        return str(o)


def valid_response(data, status=200):
    """Valid Response
    This will be return when the http request was successfully processed."""
    data = {"count": len(data) if not isinstance(data, str) else 1, "data": data}
    return werkzeug.wrappers.Response(
        status=status, content_type="application/json; charset=utf-8", response=json.dumps(data, default=default),
    )


def invalid_response(typ, message=None, status=401):
    """Invalid Response
    This will be the return value whenever the server runs into an error
    either from the client or the server."""
    # return json.dumps({})
    return werkzeug.wrappers.Response(
        status=status,
        content_type="application/json; charset=utf-8",
        response=json.dumps(
            {
                "success": False,
                "type": typ,
                "message": str(message) if str(message) else "wrong arguments (missing validation)"
            },
            default=datetime.isoformat,
        )
    )


def _request_lang():
    """Resolve the client's preferred language from the Accept-Language
    header. Returns 'ar' or 'en' (default 'en').
    Examples accepted: 'ar', 'ar_SA', 'ar-SA', 'ar, en;q=0.8'."""
    try:
        hdr = (request.httprequest.headers.get("Accept-Language") or "").strip()
    except Exception:
        hdr = ""
    if not hdr:
        return "en"
    # Take the first language tag, strip region.
    first = hdr.split(",")[0].split(";")[0].strip().lower()
    base = first.split("-")[0].split("_")[0]
    if base.startswith("ar"):
        return "ar"
    return "en"


# Timeoff endpoint user-facing messages, keyed by a stable English string id.
# Add new keys here as you add user-facing strings in the endpoints.
_TIMEOFF_MESSAGES = {
    # auth / generic errors
    "bad_json":               {"en": "Request body must be valid JSON",
                               "ar": "محتوى الطلب يجب أن يكون JSON صحيح"},
    "missing_fields":         {"en": "Required fields are missing",
                               "ar": "حقول مطلوبة غير مكتملة"},
    "no_company":             {"en": "No company selected",
                               "ar": "لا توجد شركة محددة"},
    "no_companies":           {"en": "No companies selected",
                               "ar": "لا توجد شركات محددة"},
    "no_employee":            {"en": "No employee linked to this user in the selected company",
                               "ar": "لا يوجد موظف مرتبط بهذا المستخدم في الشركة المحددة"},
    "bad_date":               {"en": "Dates must be in YYYY-MM-DD format",
                               "ar": "صيغة التاريخ يجب أن تكون YYYY-MM-DD"},
    "bad_date_range":         {"en": "End date must be on or after start date",
                               "ar": "تاريخ الانتهاء يجب أن يكون بعد أو يساوي تاريخ البداية"},
    "invalid_days":           {"en": "number_of_days must be a number",
                               "ar": "عدد الأيام يجب أن يكون رقم"},
    "invalid_id":             {"en": "request_id must be an integer",
                               "ar": "رقم الطلب يجب أن يكون عدد صحيح"},
    "create_missing_fields":  {"en": "holiday_status_id, request_date_from, request_date_to are required",
                               "ar": "نوع الإجازة وتاريخ البداية وتاريخ الانتهاء حقول مطلوبة"},
    "create_half_day_period": {"en": "request_date_from_period must be 'am' or 'pm' when request_unit_half is true",
                               "ar": "يجب تحديد فترة (صباحًا أو مساءً) عند اختيار نصف يوم"},
    "leave_type_not_found":   {"en": "Time off type not found",
                               "ar": "نوع الإجازة غير موجود"},
    "insufficient_balance":   {"en": "Not enough allocation",
                               "ar": "الرصيد غير كافٍ"},
    "request_not_found":      {"en": "Time-off request not found",
                               "ar": "طلب الإجازة غير موجود"},
    "request_not_found_or_not_validator":
                              {"en": "Time-off request not found, or you are not a validator for it",
                               "ar": "طلب الإجازة غير موجود، أو ليس لديك صلاحية اعتماده"},
    "bad_state_cancel":       {"en": "Cannot cancel a request in this state",
                               "ar": "لا يمكن إلغاء الطلب في حالته الحالية"},
    "bad_state_approve":      {"en": "Cannot approve a request in this state",
                               "ar": "لا يمكن اعتماد الطلب في حالته الحالية"},
    "bad_state_validate":     {"en": "Cannot validate a request in this state",
                               "ar": "لا يمكن التحقق من الطلب في حالته الحالية"},
    "already_approved":       {"en": "You have already approved this request. Waiting for other validators.",
                               "ar": "لقد قمت بالموافقة على هذا الطلب من قبل. بانتظار باقي المعتمدين."},
    "already_validated":      {"en": "You have already validated this request. Waiting for other validators.",
                               "ar": "لقد قمت بالتحقق من هذا الطلب من قبل. بانتظار باقي المعتمدين."},
    "already_refused":        {"en": "This request has already been refused.",
                               "ar": "هذا الطلب مرفوض بالفعل."},
    # success messages
    "cancel_success":         {"en": "Time-off request cancelled successfully",
                               "ar": "تم إلغاء طلب الإجازة بنجاح"},
    "approve_success":        {"en": "Time-off request approved successfully",
                               "ar": "تم اعتماد طلب الإجازة بنجاح"},
    "refuse_success":         {"en": "Time-off request refused successfully",
                               "ar": "تم رفض طلب الإجازة بنجاح"},
    "validate_success":       {"en": "Time-off request validated successfully",
                               "ar": "تم التحقق من طلب الإجازة بنجاح"},
    "fully_approved":         {"en": "Time-off request fully approved",
                               "ar": "تم اعتماد طلب الإجازة بالكامل"},
    "fully_validated":        {"en": "Time-off request fully validated",
                               "ar": "تم التحقق من طلب الإجازة بالكامل"},
    "partial_approval":       {"en": "Your approval recorded. Waiting on {n} more validator(s).",
                               "ar": "تم تسجيل موافقتك. بانتظار {n} معتمدين آخرين."},
    "partial_validation":     {"en": "Your validation recorded. Waiting on {n} more validator(s).",
                               "ar": "تم تسجيل تحققك. بانتظار {n} معتمدين آخرين."},
}


def _t(key, **kwargs):
    """Translate a message key into the request's preferred language.
    Falls back to English, then to the key itself if not found."""
    entry = _TIMEOFF_MESSAGES.get(key)
    if not entry:
        return key
    lang = _request_lang()
    msg = entry.get(lang) or entry.get("en") or key
    if kwargs:
        try:
            return msg.format(**kwargs)
        except Exception:
            return msg
    return msg


def validate_token(func):
    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        access_token = request.httprequest.headers.get("access-token")
        if not access_token:
            return invalid_response("access_token_not_found", "missing access token in request header", 401)

        token_rec = request.env["api.access_token"].sudo().search(
            [("token", "=", access_token)],
            order="id DESC",
            limit=1
        )
        if not token_rec or token_rec.find_or_create_token(user_id=token_rec.user_id.id) != access_token:
            return invalid_response("access_token", "token seems to have expired or invalid", 401)

        user = token_rec.user_id
        request.session.uid = user.id
        request.env = request.env(user=user)

        # =========================
        # Multi-company
        # =========================

        u = user.sudo()
        base_allowed_ids = u.company_ids.ids or ([u.company_id.id] if u.company_id else [])

        header_company_ids = request.httprequest.headers.get("x-company-ids")
        selected_ids = []

        if header_company_ids:
            try:
                selected_ids = [int(x.strip()) for x in header_company_ids.split(",") if x.strip()]
            except Exception:
                return invalid_response("invalid_company_ids", "x-company-ids must be comma-separated integers", 400)
        else:
            selected_ids = request.session.get("company_ids") or []

        try:
            selected_ids = [int(x) for x in selected_ids] if isinstance(selected_ids, list) else []
        except Exception:
            selected_ids = []

        selected_ids = list(dict.fromkeys([cid for cid in selected_ids if cid]))  # unique, remove 0

        bad = [cid for cid in selected_ids if cid not in base_allowed_ids]
        if bad:
            return invalid_response("company_forbidden", f"user not allowed in companies: {bad}", 403)

        effective_allowed_ids = selected_ids if selected_ids else base_allowed_ids

        header_company_id = request.httprequest.headers.get("x-company-id")
        session_company_id = request.session.get("company_id")

        company_id = None
        if header_company_id:
            try:
                company_id = int(header_company_id)
            except Exception:
                return invalid_response("invalid_company", "x-company-id must be integer", 400)
        elif session_company_id:
            try:
                company_id = int(session_company_id)
            except Exception:
                company_id = None

        if company_id and company_id not in effective_allowed_ids:
            return invalid_response("company_forbidden", "current company not in selected/allowed companies", 403)

        if not company_id:
            company_id = user.company_id.id if user.company_id else (
                effective_allowed_ids[0] if effective_allowed_ids else False)

        request.update_context(
            allowed_company_ids=effective_allowed_ids,
            company_id=company_id,
            force_company=company_id,
        )

        # Ensure session.context exists then update it
        request.session.context = dict(request.session.context or {})
        request.session.context.update({
            "allowed_company_ids": effective_allowed_ids,
            "company_id": company_id,
            "force_company": company_id,
        })

        # Keep simple session keys
        request.session["company_ids"] = effective_allowed_ids
        request.session["company_id"] = company_id

        return func(self, *args, **kwargs)

    return wrap


class MultiCompanyEmployeeMixin(object):

    def _current_company_id(self):
        # prefer force_company (your API-selected current company), then company_id, then env.company
        return (
            request.env.context.get("force_company")
            or request.env.context.get("company_id")
            or request.env.company.id
        )

    def _get_employee_for_user_in_company(self, user, company_id):
        Employee = request.env["hr.employee"].sudo()

        emp = Employee.search([
            ("user_id", "=", user.id),
            ("company_id", "=", int(company_id or 0)),
            ("active", "=", True),
        ], limit=1)
        if emp:
            return emp

        allowed_ids = (
                request.env.context.get("allowed_company_ids")
                or (request.session.context.get("allowed_company_ids") if getattr(request.session, "context",
                                                                                  None) else [])
                or []
        )
        allowed_ids = [int(x) for x in allowed_ids if x]

        if allowed_ids:
            emp = Employee.search([
                ("user_id", "=", user.id),
                ("company_id", "in", allowed_ids),
                ("active", "=", True),
            ], limit=1)
            if emp:
                return emp

        return Employee.search([("user_id", "=", user.id), ("active", "=", True)], limit=1)

    def _allowed_company_ids(self):
        # prefer context, then session fallback
        return (
            request.env.context.get("allowed_company_ids")
            or (request.session.context.get("allowed_company_ids") if getattr(request.session, "context", None) else [])
            or []
        )

    def _company_scope_domain(self, field_name="company_id", allow_global=True):

        allowed_ids = self._allowed_company_ids()
        if allow_global:
            return [(field_name, "in", [False] + allowed_ids)]
        return [(field_name, "in", allowed_ids)]

    def _force_company_env(self, company_id=None, allowed_company_ids=None):
        allowed_ids = allowed_company_ids or self._allowed_company_ids() or []
        if not allowed_ids:
            cur = self._current_company_id()
            allowed_ids = [cur] if cur else []

        cid = int(company_id or self._current_company_id() or (allowed_ids[0] if allowed_ids else 0)) or 0
        if allowed_ids and cid not in allowed_ids:
            cid = allowed_ids[0]

        ctx = dict(request.env.context or {})
        ctx.update({
            "allowed_company_ids": [int(x) for x in allowed_ids if x],
            "company_id": cid,
            "force_company": cid,
        })
        return request.env(context=ctx)

    def _iter_company_envs(self):
        company_ids = self._allowed_company_ids() or [self._current_company_id()]
        company_ids = [int(x) for x in company_ids if x]
        for cid in company_ids:
            yield cid, self._force_company_env(company_id=cid, allowed_company_ids=company_ids)


class AppLogin(http.Controller, MultiCompanyEmployeeMixin):

    def get_user_timezone_now(self, user_timezone='Asia/Riyadh'):
        """Get current datetime in user's timezone"""
        utc_now = datetime.utcnow()
        utc_tz = pytz.timezone('UTC')
        user_tz = pytz.timezone(user_timezone)

        # Convert UTC to user timezone
        utc_dt = utc_tz.localize(utc_now)
        user_dt = utc_dt.astimezone(user_tz)
        return user_dt

    def get_day_boundaries_utc(self, date_in_user_tz, user_timezone='Asia/Riyadh'):
        """Get start and end of day in UTC for a given date in user timezone"""
        user_tz = pytz.timezone(user_timezone)
        utc_tz = pytz.timezone('UTC')

        # Create start of day (00:00:00) in user timezone
        start_of_day = user_tz.localize(datetime.combine(date_in_user_tz, datetime.min.time()))
        # Create end of day (23:59:59) in user timezone
        end_of_day = user_tz.localize(datetime.combine(date_in_user_tz, datetime.max.time()))

        # Convert to UTC for database query
        start_utc = start_of_day.astimezone(utc_tz).replace(tzinfo=None)
        end_utc = end_of_day.astimezone(utc_tz).replace(tzinfo=None)

        return start_utc, end_utc

    def get_month_boundaries_utc(self, year, month, user_timezone='Asia/Riyadh'):
        """Get start and end of month in UTC for given year/month in user timezone"""
        user_tz = pytz.timezone(user_timezone)
        utc_tz = pytz.timezone('UTC')

        # First day of month in user timezone
        first_day = datetime(year, month, 1)
        start_of_month = user_tz.localize(first_day)

        # First day of next month in user timezone
        if month == 12:
            next_month_start = datetime(year + 1, 1, 1)
        else:
            next_month_start = datetime(year, month + 1, 1)
        end_of_month = user_tz.localize(next_month_start)

        # Convert to UTC
        start_utc = start_of_month.astimezone(utc_tz).replace(tzinfo=None)
        end_utc = end_of_month.astimezone(utc_tz).replace(tzinfo=None)

        return start_utc, end_utc

    def convert_to_user_timezone(self, utc_time, user_timezone):
        """Convert UTC time to the user's local timezone."""
        if not utc_time:
            return None
        # Set UTC time zone
        utc_zone = pytz.UTC
        # Get the user's timezone
        user_tz = pytz.timezone(user_timezone)

        # Convert the time to user's timezone
        utc_time = utc_zone.localize(utc_time)  # Ensure the time is timezone-aware
        user_time = utc_time.astimezone(user_tz)  # Convert to user's time zone

        return user_time

    def convert_float_to_hours_and_minutes(self, float_hours):
        # Extract hours
        hours = int(float_hours)

        # Extract minutes and convert to seconds
        minutes = int((float_hours - hours) * 60)
        # Get remaining seconds

        # Format the output as "00 hours and 00 seconds"
        return f"{hours:02} Hrs and {minutes:02} Mins"

    @http.route('/api/login', type='http', methods=['POST'], auth='none', csrf=False)
    def login_employee(self):
        payload = request.httprequest.data.decode()
        payload = json.loads(payload)
        username, password = (
            payload.get("login"),
            payload.get("password"),
        )
        _credentials_includes_in_body = all([username, password])
        if not _credentials_includes_in_body:
            return invalid_response(
                "missing error", "either of the following are missing [username,password]", 403
            )
        db = request.env.cr.dbname
        try:
            request.session.authenticate(db, username, password)
        except AccessError as aee:
            return invalid_response("Access error", "Error: %s" % aee.name)
        except AccessDenied as ade:
            return invalid_response("Access denied", "Login or password invalid")

        uid = request.session.uid
        # odoo login failed:
        if not uid:
            info = "authentication failed"
            error = "authentication failed"
            _logger.error(info)
            return invalid_response(401, error, info)

        # Generate tokens
        access_token = request.env["api.access_token"].find_or_create_token(user_id=uid, create=True)

        # Check Timeoff Access
        has_timeoff_access = request.env.user.has_group('hr_holidays.group_hr_holidays_user') or \
                             request.env.user.has_group('hr_holidays.group_hr_holidays_manager')
        has_attendance_access = request.env.user.has_group('hr_attendance.group_hr_attendance_manager')

        companies = request.env.user.company_ids

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps(
                {
                    "uid": uid,
                    "default_company_id": request.env.user.company_id.id if uid else None,
                    "companies": [{"id": c.id, "name": c.name} for c in companies],
                    "partner_id": request.env.user.partner_id.id,
                    "access_token": access_token,
                    "company_name": request.env.user.company_id.name if request.env.user.company_id else "",
                    "country": request.env.user.country_id.name,
                    "contact_address": request.env.user.contact_address,
                    "access": {
                        "attendance": "manager" if has_attendance_access else "user",
                        "expenses": "user",
                        "payroll": "user",
                        "timeoff": "manager" if has_timeoff_access else "user",
                        "skip_biometric": request.env.user.employee_id.skip_biometric or False


                    },
                }
            )
        )

    @validate_token
    @http.route("/api/user/switch-company", methods=["POST"], type="http", auth="none", csrf=False)
    def switch_company(self, **kwargs):
        try:
            payload = request.httprequest.data.decode("utf-8") or "{}"
            data = json.loads(payload)

            company_id = int(data.get("company_id") or 0)
            if not company_id:
                return invalid_response("missing_company", "company_id is required", 400)

            user = request.env.user

            u = request.env.user.sudo()
            allowed_ids = request.env.context.get("allowed_company_ids") or u.company_ids.ids or (
                [u.company_id.id] if u.company_id else [])

            if company_id not in allowed_ids:
                return invalid_response("company_forbidden", "user not allowed in this company", 403)

            # session/context only (NO write on res.users)
            request.session["company_id"] = company_id
            request.session.context = dict(request.session.context or {})
            request.session.context.update({
                "allowed_company_ids": allowed_ids,
                "company_id": company_id,
                "force_company": company_id,
            })

            request.update_context(
                allowed_company_ids=allowed_ids,
                company_id=company_id,
                force_company=company_id,
            )

            return valid_response({
                "message": "Company switched successfully",
                "company_id": company_id,
                "allowed_company_ids": allowed_ids,
                "default_company_id": company_id,
            }, status=200)

        except Exception as e:
            _logger.exception("switch_company error")
            return invalid_response("error", str(e), 500)

    @validate_token
    @http.route("/api/user/selected-companies", methods=["GET"], type="http", auth="none", csrf=False)
    def get_selected_companies(self, **kwargs):
        try:
            user = request.env.user

            selected_ids = self._allowed_company_ids()
            if not selected_ids:
                u = user.sudo()
                selected_ids = u.company_ids.ids or ([u.company_id.id] if u.company_id else [])


            current_company_id = self._current_company_id()

            companies = request.env["res.company"].sudo().browse(selected_ids).exists()

            data = [{
                "id": c.id,
                "name": c.name,
                "is_current": (c.id == current_company_id),
            } for c in companies]

            data.sort(key=lambda x: (not x["is_current"], x["id"]))

            return request.make_json_response({
                "current_company_id": current_company_id,
                "selected_company_ids": selected_ids,
                "companies": data,
            }, status=200)

        except Exception as e:
            _logger.exception("get_selected_companies error")
            return invalid_response("error", str(e), 500)

    @validate_token
    @http.route("/api/user/select-companies", methods=["POST"], type="http", auth="none", csrf=False)
    def select_companies(self, **kwargs):
        try:
            payload = request.httprequest.data.decode("utf-8") or "{}"
            data = json.loads(payload)

            user = request.env.user
            u = request.env.user.sudo()

            u = request.env.user.sudo()

            allowed_ids = u.company_ids.ids

            if not allowed_ids:
                return invalid_response("no_allowed_companies", "User has no allowed companies", 403)

            company_ids = data.get("company_ids") or []
            if not isinstance(company_ids, list):
                return invalid_response("invalid_company_ids", "company_ids must be a list", 400)

            try:
                company_ids = [int(x) for x in company_ids]
            except Exception:
                return invalid_response("invalid_company_ids", "company_ids must be integers", 400)

            company_ids = list(dict.fromkeys([cid for cid in company_ids if cid]))

            if not company_ids:
                return invalid_response("missing_company_ids", "company_ids is required", 400)

            bad = [cid for cid in company_ids if cid not in allowed_ids]
            if bad:
                return invalid_response("company_forbidden", f"user not allowed in companies: {bad}", 403)

            request.session["company_ids"] = company_ids

            current_company_id = request.session.get("company_id")
            try:
                current_company_id = int(current_company_id) if current_company_id else None
            except Exception:
                current_company_id = None

            if not current_company_id or current_company_id not in company_ids:
                current_company_id = company_ids[0]

            request.session["company_id"] = current_company_id

            request.session.context = dict(request.session.context or {})
            request.session.context.update({
                "allowed_company_ids": company_ids,
                "company_id": current_company_id,
                "force_company": current_company_id,
            })

            request.update_context(
                allowed_company_ids=company_ids,
                company_id=current_company_id,
                force_company=current_company_id,
            )

            return valid_response({
                "message": "Companies selected successfully",
                "selected_company_ids": company_ids,
                "current_company_id": current_company_id,
                "allowed_company_ids": allowed_ids,
                "default_company_id": current_company_id,
            }, status=200)

        except Exception as e:
            _logger.exception("select_companies error")
            return invalid_response("error", str(e), 500)

    # @validate_token
    # @http.route("/api/user/check-in-out", methods=["POST"], type="http", auth="none", csrf=False)
    # def check_in_out(self, **post):
    #     try:
    #         user_id = request.uid
    #         user_obj = request.env['res.users'].browse(user_id)
    #         employee = user_obj.employee_id
    #
    #         payload = request.httprequest.data.decode()
    #         payload = json.loads(payload)
    #
    #         longitude = payload.get("longitude")
    #         latitude = payload.get("latitude")
    #         ip_address = payload.get("ip_address")
    #         uuid = payload.get("uuid")
    #         action_date = fields.Datetime.now()
    #
    #         # Ensure we're in a proper transaction
    #         with request.env.cr.savepoint():
    #             if employee.last_attendance_id:
    #                 if employee.last_attendance_id.check_out:
    #                     # Check in
    #                     new_att = request.env['hr.attendance'].with_user(user_obj).create({
    #                         'employee_id': employee.sudo().id,
    #                         'check_in': action_date,
    #                         'in_longitude': longitude,
    #                         'in_latitude': latitude,
    #                         'in_ip_address': ip_address,
    #                         'in_mode': 'systray'
    #                     })
    #
    #                     employee.sudo().write({'last_attendance_id': new_att.id})
    #                     uuid_record = request.env['uuid.model'].sudo().check_and_update_uuid(uuid, employee.sudo().id)
    #
    #                     # Commit the transaction explicitly
    #                     request.env.cr.commit()
    #
    #                     return valid_response([{
    #                         "attendance_state": "checked in",
    #                         "message": "Checked in successfully",
    #                         "uuid": uuid_record["message"]
    #                     }], status=200)
    #                 else:
    #                     # Check out
    #                     att = employee.last_attendance_id
    #                     att.write({
    #                         'check_out': action_date,
    #                         'out_longitude': longitude,
    #                         'out_latitude': latitude,
    #                         'out_ip_address': ip_address,
    #                         'out_mode': 'systray'
    #                     })
    #
    #                     uuid_record = request.env['uuid.model'].sudo().check_and_update_uuid(uuid, employee.sudo().id)
    #
    #                     # Commit the transaction explicitly
    #                     request.env.cr.commit()
    #
    #                     return valid_response([{
    #                         "attendance_state": "checked out",
    #                         "message": "Checked out successfully",
    #                         "uuid": uuid_record["message"]
    #                     }], status=200)
    #             else:
    #                 # First check in
    #                 new_att = request.env['hr.attendance'].with_user(user_obj).create({
    #                     'employee_id': employee.sudo().id,
    #                     'check_in': action_date,
    #                     'in_longitude': longitude,
    #                     'in_latitude': latitude,
    #                     'in_ip_address': ip_address,
    #                     'in_mode': 'systray'
    #                 })
    #
    #                 employee.sudo().write({'last_attendance_id': new_att.id})
    #                 uuid_record = request.env['uuid.model'].sudo().check_and_update_uuid(uuid, employee.sudo().id)
    #
    #                 # Commit the transaction explicitly
    #                 request.env.cr.commit()
    #
    #                 return valid_response([{
    #                     "attendance_state": "checked in",
    #                     "message": "Checked in successfully",
    #                     "uuid": uuid_record["message"]
    #                 }], status=200)
    #
    #     except Exception as e:
    #         # Rollback on any error
    #         request.env.cr.rollback()
    #         _logger.error(f"Check-in/out error: {str(e)}")
    #         return invalid_response("error", str(e), 400)

    @validate_token
    @http.route("/api/user/check-in-out", methods=["POST"], type="http", auth="none", csrf=False)
    def check_in_out(self, **post):
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].sudo().browse(user_id)
            company_id = self._current_company_id()
            employee = self._get_employee_for_user_in_company(request.env.user, company_id)

            if not employee:
                return invalid_response("no_employee", _t("no_employee"), 404)

            payload = request.httprequest.data.decode()
            payload = json.loads(payload)

            longitude = payload.get("longitude")
            latitude = payload.get("latitude")
            ip_address = payload.get("ip_address")
            uuid = payload.get("uuid")
            action_date = fields.Datetime.now()

            with request.env.cr.savepoint():
                last_att = employee.sudo().with_context({'check_access_rule': False}).last_attendance_id

                if last_att and not last_att.check_out:
                    last_att.sudo().with_context({'check_access_rule': False}).write({
                        'check_out': action_date,
                        'out_longitude': longitude,
                        'out_latitude': latitude,
                        'out_ip_address': ip_address,
                        'out_mode': 'systray'
                    })

                    uuid_record = request.env['uuid.model'].sudo().check_and_update_uuid(uuid, employee.id)

                    return valid_response([{
                        "attendance_state": "checked out",
                        "message": "Checked out successfully",
                        "uuid": uuid_record["message"]
                    }], status=200)
                else:
                    new_att = request.env['hr.attendance'].sudo().with_context({'check_access_rule': False}).create({
                        'employee_id': employee.id,
                        'check_in': action_date,
                        'in_longitude': longitude,
                        'in_latitude': latitude,
                        'in_ip_address': ip_address,
                        'in_mode': 'systray'
                    })

                    employee.sudo().write({'last_attendance_id': new_att.id})
                    uuid_record = request.env['uuid.model'].sudo().check_and_update_uuid(uuid, employee.id)

                    return valid_response([{
                        "attendance_state": "checked in",
                        "message": "Checked in successfully",
                        "uuid": uuid_record["message"]
                    }], status=200)

        except Exception as e:
            _logger.error(f"Check-in/out error: {str(e)}")
            return invalid_response("error", str(e), 400)

    @validate_token
    @http.route("/api/user/attendance-state", methods=["GET"], type="http", auth="none", csrf=False)
    def get_attendance_state(self, **kwargs):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        company_id = self._current_company_id()
        employee = self._get_employee_for_user_in_company(request.env.user, company_id)
        if not employee:
            return invalid_response("no_employee", _t("no_employee"), 404)

        # حساب can_check_in و message
        can_check_in = False
        check_in_message = ""
        earliest_check_in_time = None

        if employee.last_attendance_id:
            try:
                if employee.last_attendance_id.check_out:
                    can_check_in, check_in_message, earliest_check_in_time = self._can_employee_check_in(employee)

                    response_data = {"attendance_state": "checked_out", "can_check_in": can_check_in,
                                     "message": check_in_message}
                    if earliest_check_in_time:
                        response_data["earliest_check_in_time"] = earliest_check_in_time

                    return werkzeug.wrappers.Response(
                        status=200,
                        content_type="application/json; charset=utf-8",
                        headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                        response=json.dumps(response_data),
                    )
                else:
                    # checked_in
                    return werkzeug.wrappers.Response(
                        status=200,
                        content_type="application/json; charset=utf-8",
                        headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                        response=json.dumps({"attendance_state": "checked_in", "can_check_in": False, "message": ""}),
                    )
            except Exception as e:
                return invalid_response("error", str(e), 400)
        else:
            can_check_in, check_in_message, earliest_check_in_time = self._can_employee_check_in(employee)

            response_data = {"attendance_state": "checked_out", "can_check_in": can_check_in,
                             "message": check_in_message}
            if earliest_check_in_time:
                response_data["earliest_check_in_time"] = earliest_check_in_time

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps(response_data),
            )

    def _can_employee_check_in(self, employee):
        """
        Returns: (can_check_in, message, earliest_check_in_time)
        """
        from datetime import datetime, time, timedelta
        import pytz

        def float_to_time(f):
            hours = int(f)
            minutes = int(round((f - hours) * 60))
            if minutes == 60:
                hours += 1
                minutes = 0
            if hours >= 24:
                hours = 23
                minutes = 59
            return time(hour=hours, minute=minutes)

        try:
            if request.env.user.has_group('hr_attendance_custom.group_free_checkout'):
                return True, "", None

            if not employee.resource_calendar_id:
                return True, "", None

            employee_tz = pytz.timezone(employee.tz or 'UTC')

            now_utc = datetime.utcnow()
            now_utc = pytz.UTC.localize(now_utc)
            now_local = now_utc.astimezone(employee_tz)

            local_date = now_local.date()
            day_of_week = str(local_date.weekday())
            envc = self._force_company_env()

            shifts = envc['resource.calendar.attendance'].sudo().search([
                ('calendar_id', '=', employee.resource_calendar_id.id),
                ('dayofweek', '=', day_of_week),
                ('day_period', '!=', 'break')
            ])

            if not shifts:
                return True, "", None

            shift_starts = []
            for shift in shifts:
                start_time = float_to_time(shift.hour_from)
                start_datetime_naive = datetime.combine(local_date, start_time)
                shift_starts.append(start_datetime_naive)

            if not shift_starts:
                return True, "", None

            earliest_start_naive = min(shift_starts)
            earliest_start_local = employee_tz.localize(earliest_start_naive, is_dst=None)

            earliest_allowed = earliest_start_local - timedelta(minutes=15)

            now_local_clean = now_local.replace(second=0, microsecond=0)
            earliest_allowed_clean = earliest_allowed.replace(second=0, microsecond=0)

            if now_local_clean < earliest_allowed_clean:
                earliest_check_in_time_str = earliest_allowed.strftime('%H:%M')
                shift_start_time_str = earliest_start_local.strftime('%H:%M')
                return False, f"You cannot log in 15 minutes before your shift starts (shift starts at {shift_start_time_str})", earliest_check_in_time_str
            else:
                return True, "", None

        except Exception as e:
            return True, "", None

    @validate_token
    @http.route("/api/user/total-hours", methods=["GET"], type="http", auth="none", csrf=False)
    def get_total_hours(self, **kwargs):
        try:
            user = request.env['res.users'].sudo().browse(request.uid)
            company_id = self._current_company_id()
            employee = self._get_employee_for_user_in_company(request.env.user, company_id)
            if not employee:
                return invalid_response("no_employee", _t("no_employee"), 404)

            if not employee:
                return valid_response([{"error": "No employee associated with this user"}], status=400)

            user_timezone = 'Asia/Riyadh'
            current_dt = self.get_user_timezone_now(user_timezone)
            today_local = current_dt.date()
            start_utc, end_utc = self.get_day_boundaries_utc(today_local, user_timezone)

            attendances = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', start_utc),
                ('check_in', '<', end_utc),
                ('check_out', '!=', False)
            ], order='check_in asc')

            # Early return if no attendances found
            if not attendances:
                return werkzeug.wrappers.Response(
                    status=200,
                    content_type="application/json; charset=utf-8",
                    headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                    response=json.dumps({"total_hours": "0h 0m"}),
                )

            total_seconds = 0.0
            for attendance in attendances:
                delta = attendance.check_out - attendance.check_in
                total_seconds += delta.total_seconds()

            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            time_format = f"{hours}h {minutes}m"

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"total_hours": time_format}),
            )

        except Exception as e:
            return valid_response([{"error": str(e)}], status=500)

    @validate_token
    @http.route("/api/user/this-pay-period", methods=["GET"], type="http", auth="none", csrf=False)
    def get_this_pay_period_hours(self, **kwargs):
        try:
            user = request.env['res.users'].sudo().browse(request.uid)
            company_id = self._current_company_id()
            employee = self._get_employee_for_user_in_company(request.env.user, company_id)
            if not employee:
                return invalid_response("no_employee", _t("no_employee"), 404)

            if not employee:
                return valid_response([{"error": "No employee associated with this user"}], status=400)

            # Import required modules
            from datetime import datetime
            import calendar

            # Set up Riyadh timezone
            riyadh_tz = pytz.timezone('Asia/Riyadh')

            # Get current date in Riyadh timezone
            today = datetime.now(riyadh_tz)

            # Calculate first day of month at 00:00:00 in Riyadh time
            first_day_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Calculate last day of month at 23:59:59 in Riyadh time
            last_day_of_month = today.replace(day=calendar.monthrange(today.year, today.month)[1], hour=23, minute=59,
                                              second=59, microsecond=999999)

            # Convert to UTC for database query (Odoo stores datetime in UTC)
            first_day_utc = first_day_of_month.astimezone(pytz.UTC).replace(tzinfo=None)
            last_day_utc = last_day_of_month.astimezone(pytz.UTC).replace(tzinfo=None)

            # Get all completed attendances in this month
            attendances = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.sudo().id),
                ('check_in', '>=', first_day_utc),
                ('check_in', '<=', last_day_utc),
                ('check_in', '!=', False),
                ('check_out', '!=', False),
            ])

            total_seconds = 0
            for att in attendances:
                total_seconds += (att.check_out - att.check_in).total_seconds()

            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)

            time_format = f"{hours}h {minutes}m"

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"total_time_for_this_month": time_format}),
            )
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)

    @validate_token
    @http.route("/api/user/profile", methods=["GET"], type="http", auth="none", csrf=False)
    def get_user_info1(self, **post):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        company_id = self._current_company_id()
        employee = self._get_employee_for_user_in_company(request.env.user, company_id)
        if not employee:
            return invalid_response("no_employee", _t("no_employee"), 404)

        contact = user_obj.partner_id
        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps(
                {
                    "uid": user_id,
                    "name": contact.name,
                    "email": contact.email,
                    "phone": contact.phone,
                    "company_id": company_id,
                    "company_name": employee.company_id.name if employee.company_id else "",
                    "department": employee.department_id.name if employee.department_id else "",
                    "job_title": employee.job_id.name if employee.job_id else "",
                }
            ),
        )

    @validate_token
    @http.route("/api/user/today-att", methods=["GET"], type="http", auth="none", csrf=False)
    def get_user_info2(self, **post):

        response = []
        seen_attendance_ids = set()

        user_timezone = "Asia/Riyadh"
        current_dt_riyadh = self.get_user_timezone_now(user_timezone)
        today_riyadh = current_dt_riyadh.date()
        start_utc, end_utc = self.get_day_boundaries_utc(today_riyadh, user_timezone)

        allowed_company_ids = self._allowed_company_ids() or [self._current_company_id()]
        allowed_company_ids = set(allowed_company_ids)

        for company_id, envc in self._iter_company_envs():

            if company_id not in allowed_company_ids:
                continue

            employee = self._get_employee_for_user_in_company(request.env.user, company_id)
            if not employee:
                continue

            Attendance = envc["hr.attendance"].sudo()

            domain = [
                ("check_in", ">=", start_utc),
                ("check_in", "<", end_utc),
                ("employee_id", "=", employee.id),
            ]

            if "company_id" in Attendance._fields:
                domain.append(("company_id", "=", company_id))

            attendances = Attendance.search(domain, order="check_in desc")

            company_name = ""
            try:
                company_name = envc["res.company"].sudo().browse(company_id).name or ""
            except Exception:
                company_name = ""

            for attendance in attendances:

                if attendance.id in seen_attendance_ids:
                    continue
                seen_attendance_ids.add(attendance.id)

                check_in_riyadh = None
                check_out_riyadh = None
                try:
                    if attendance.check_in:
                        check_in_riyadh = self.convert_to_user_timezone(attendance.check_in, user_timezone)
                    if attendance.check_out:
                        check_out_riyadh = self.convert_to_user_timezone(attendance.check_out, user_timezone)
                except Exception:
                    check_in_riyadh = None
                    check_out_riyadh = None

                user_check_in = check_in_riyadh.strftime("%I:%M %p") if check_in_riyadh else None
                user_check_out = check_out_riyadh.strftime("%I:%M %p") if check_out_riyadh else None

                edit_request = None
                try:
                    edit_request = envc["hr.attendance.edit.request"].sudo().search([
                        ("attendance_id", "=", attendance.id),
                    ], limit=1)
                except Exception:
                    edit_request = None

                api_updated = False
                try:
                    api_updated = bool(getattr(attendance, "x_api_updated", False))
                except Exception:
                    api_updated = False

                has_request = bool(edit_request) or api_updated

                response.append({
                    "company_id": company_id,
                    "company_name": company_name,
                    "employee_id": employee.id,

                    "id": attendance.id,
                    "check_in": user_check_in,
                    "check_out": user_check_out,
                    "worked_hours": self.convert_float_to_hours_and_minutes(attendance.worked_hours),
                    "in_longitude": attendance.in_longitude,
                    "in_latitude": attendance.in_latitude,
                    "out_longitude": attendance.out_longitude,
                    "out_latitude": attendance.out_latitude,
                    "has_request": has_request,
                })

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps(response if response else []),
        )

    @validate_token
    @http.route("/api/user/month-att", methods=["GET"], type="http", auth="none", csrf=False)
    def get_user_info3(self, **post):

        response = []
        seen_attendance_ids = set()

        user_timezone = "Asia/Riyadh"

        current_dt_riyadh = self.get_user_timezone_now(user_timezone)
        current_month = current_dt_riyadh.month
        current_year = current_dt_riyadh.year

        start_utc, end_utc = self.get_month_boundaries_utc(current_year, current_month, user_timezone)

        allowed_company_ids = self._allowed_company_ids() or [self._current_company_id()]
        allowed_company_ids = set(allowed_company_ids)

        for company_id, envc in self._iter_company_envs():

            if company_id not in allowed_company_ids:
                continue

            employee = self._get_employee_for_user_in_company(request.env.user, company_id)
            if not employee:
                continue

            Attendance = envc["hr.attendance"].sudo()

            domain = [
                ("employee_id", "=", employee.id),
                ("check_in", ">=", start_utc),
                ("check_in", "<", end_utc),
            ]

            if "company_id" in Attendance._fields:
                domain.append(("company_id", "=", company_id))

            attendances = Attendance.search(domain, order="check_in desc")

            att_ids = attendances.ids
            request_att_ids = set()
            api_updated_att_ids = set()

            if att_ids:
                try:
                    EditReq = envc["hr.attendance.edit.request"].sudo()
                    req_domain = [
                        ("attendance_id", "in", att_ids),
                        ("employee_id", "=", employee.id),
                    ]
                    if "company_id" in EditReq._fields:
                        req_domain.append(("company_id", "=", company_id))

                    reqs = EditReq.search(req_domain)
                    request_att_ids = set(reqs.mapped("attendance_id").ids)
                except Exception:
                    request_att_ids = set()

                try:
                    if "x_api_updated" in Attendance._fields:
                        api_updated_att_ids = set(
                            Attendance.search([("id", "in", att_ids), ("x_api_updated", "=", True)]).ids
                        )
                    else:
                        api_updated_att_ids = set()
                except Exception:
                    api_updated_att_ids = set()

            company_name = ""
            try:
                company_name = envc["res.company"].sudo().browse(company_id).name or ""
            except Exception:
                company_name = ""

            for attendance in attendances:

                if attendance.id in seen_attendance_ids:
                    continue
                seen_attendance_ids.add(attendance.id)

                check_in_riyadh = None
                check_out_riyadh = None
                try:
                    if attendance.check_in:
                        check_in_riyadh = self.convert_to_user_timezone(attendance.check_in, user_timezone)
                    if attendance.check_out:
                        check_out_riyadh = self.convert_to_user_timezone(attendance.check_out, user_timezone)
                except Exception:
                    check_in_riyadh = None
                    check_out_riyadh = None

                user_check_in = check_in_riyadh.strftime("%I:%M %p") if check_in_riyadh else None
                user_check_out = check_out_riyadh.strftime("%I:%M %p") if check_out_riyadh else None
                day_date = check_in_riyadh.strftime("%d %B %Y") if check_in_riyadh else None

                response.append({
                    "company_id": company_id,
                    "company_name": company_name,
                    "employee_id": employee.id,

                    "attendance_id": attendance.id,
                    "date": day_date,
                    "check_in": user_check_in,
                    "check_out": user_check_out,
                    "worked_hours": self.convert_float_to_hours_and_minutes(attendance.worked_hours),
                    "in_longitude": attendance.in_longitude,
                    "in_latitude": attendance.in_latitude,
                    "out_longitude": attendance.out_longitude,
                    "out_latitude": attendance.out_latitude,

                    "has_request": (attendance.id in request_att_ids) or (attendance.id in api_updated_att_ids),
                })

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps(response if response else []),
        )


class ExpensesController(http.Controller, MultiCompanyEmployeeMixin):

    @validate_token
    @http.route('/api/employee/expenses', type='http', auth='public', methods=['POST'], csrf=False)
    def create_expense(self, **kwargs):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        company_id = self._current_company_id()
        employee = self._get_employee_for_user_in_company(request.env.user, company_id)
        if not employee:
            return invalid_response("no_employee", _t("no_employee"), 404)

        product_id = kwargs.get('category_id')
        description = kwargs.get('description')
        total_amount = kwargs.get('total_amount')
        request_type_id = kwargs.get('request_type_id')
        uploaded_files = request.httprequest.files

        try:
            # Validate required fields
            if not all([product_id, description, total_amount]):
                return Response(
                    json.dumps({'success': False, 'error': 'Missing required fields'}),
                    content_type='application/json',
                    status=400
                )

            try:
                product_id = int(product_id)
                total_amount = float(total_amount)
            except ValueError:
                return Response(
                    json.dumps({'success': False, 'error': 'Invalid data format'}),
                    content_type='application/json',
                    status=400
                )

            envc = self._force_company_env()

            product = envc['product.product'].sudo().search(
                [('id', '=', product_id)] + self._company_scope_domain('company_id', allow_global=True),
                limit=1
            )
            if not product:
                return Response(
                    json.dumps({'success': False, 'error': f'Product with ID {product_id} not found'}),
                    content_type='application/json',
                    status=404
                )

            company_id = self._current_company_id()
            company = request.env['res.company'].sudo().browse(company_id)
            currency = company.currency_id
            if not currency:
                return Response(
                    json.dumps({'success': False, 'error': 'Company has no currency set'}),
                    content_type='application/json',
                    status=400
                )

            # =========================
            # SAFE CREATE (x_request_type optional + FK-safe)
            # =========================
            vals = {
                'name': description,
                'product_id': product.id,
                'total_amount_currency': total_amount,
                'employee_id': employee.sudo().id,
                'company_id': company_id,
                'currency_id': currency.id,
                'date': fields.Date.today(),
            }

            # ✅ Write request type only if:
            # 1) field exists on hr.expense
            # 2) model ao.request.samir exists/loaded
            # 3) referenced record exists (avoid FK violation)
            if request_type_id and 'x_request_type' in envc['hr.expense']._fields:
                try:
                    rt_id = int(request_type_id)
                except Exception:
                    return Response(
                        json.dumps({'success': False, 'error': 'request_type_id must be an integer'}),
                        content_type='application/json',
                        status=400
                    )

                if 'ao.request.samir' in envc:
                    rt = envc['ao.request.samir'].sudo().browse(rt_id)
                    if not rt.exists():
                        return Response(
                            json.dumps({
                                'success': False,
                                'error': f'Invalid request_type_id={rt_id}: not found in ao.request.samir'
                            }),
                            content_type='application/json',
                            status=400
                        )
                    vals['x_request_type'] = rt_id

            expense = envc['hr.expense'].sudo().create(vals)

            # Handle file attachment
            if uploaded_files:
                files = uploaded_files.to_dict(flat=False)
                for file in files.get("file", []):
                    file_content = file.read()
                    file_name = file.filename
                    file_data = base64.b64encode(file_content)

                    request.env['ir.attachment'].sudo().create({
                        'name': file_name,
                        'type': 'binary',
                        'datas': file_data,
                        'res_model': 'hr.expense',
                        'res_id': expense.id,
                    })

            return Response(
                json.dumps({
                    'success': True,
                    'record_id': expense.id,
                }),
                content_type='application/json',
                status=201
            )

        except Exception as e:
            return Response(
                json.dumps({'success': False, 'error': str(e)}),
                content_type='application/json',
                status=500
            )

    @validate_token
    @http.route("/api/employee/expenses/new", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_new_expenses(self, **post):
        """Get new (draft) expenses from all selected companies"""
        try:
            user = request.env.user
            allowed_company_ids = self._allowed_company_ids()

            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)

            all_expenses = []
            total_count = 0

            # Loop through each selected company
            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)

                if not employee:
                    continue

                domain = [
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'draft'),
                    ('company_id', '=', company_id),
                ]

                expenses = envc['hr.expense'].sudo().search(domain)
                total_count += len(expenses)

                for expense in expenses:
                    expense_data = {
                        "id": expense.id,
                        "name": expense.name,
                        "date": expense.date.strftime('%Y-%m-%d') if expense.date else "",
                        "total_amount": expense.total_amount
                    }

                    # Add company info if multiple companies selected
                    if len(allowed_company_ids) > 1:
                        expense_data["company_id"] = company_id
                        expense_data["company_name"] = expense.company_id.name

                    all_expenses.append(expense_data)

            # Sort by id
            all_expenses.sort(key=lambda x: x['id'])

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"results": total_count, "data": all_expenses}),
            )

        except Exception as e:
            _logger.error(f"Error in get_employee_new_expenses: {str(e)}", exc_info=True)
            return invalid_response("error", str(e), 500)

    @validate_token
    @http.route("/api/employee/expenses/pending", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_pending_expenses(self, **post):
        """Get pending expenses from all selected companies"""
        try:
            user = request.env.user
            allowed_company_ids = self._allowed_company_ids()

            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)

            all_expenses = []
            total_count = 0

            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)

                if not employee:
                    continue

                domain = [
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ['reported', 'submitted']),
                    ('company_id', '=', company_id),
                ]

                expenses = envc['hr.expense'].sudo().search(domain)
                total_count += len(expenses)

                for expense in expenses:
                    expense_data = {
                        "id": expense.id,
                        "name": expense.name,
                        "date": expense.date.strftime('%Y-%m-%d') if expense.date else "",
                        "total_amount": expense.total_amount
                    }

                    if len(allowed_company_ids) > 1:
                        expense_data["company_id"] = company_id
                        expense_data["company_name"] = expense.company_id.name

                    all_expenses.append(expense_data)

            all_expenses.sort(key=lambda x: x['id'])

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"results": total_count, "data": all_expenses}),
            )

        except Exception as e:
            _logger.error(f"Error in get_employee_pending_expenses: {str(e)}", exc_info=True)
            return invalid_response("error", str(e), 500)

    @validate_token
    @http.route("/api/employee/expenses/done", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_done_expenses(self, **post):
        """Get done/refused expenses from all selected companies"""
        try:
            user = request.env.user
            allowed_company_ids = self._allowed_company_ids()

            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)

            all_expenses = []

            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)

                if not employee:
                    continue

                # Done expenses
                done_domain = [
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ['approved', 'done']),
                    ('company_id', '=', company_id),
                ]

                done_expenses = envc['hr.expense'].sudo().search(done_domain)

                for expense in done_expenses:
                    expense_data = {
                        "id": expense.id,
                        "name": expense.name,
                        "date": expense.date.strftime('%Y-%m-%d') if expense.date else "",
                        "state": expense.state,
                        "total_amount": expense.total_amount
                    }

                    if len(allowed_company_ids) > 1:
                        expense_data["company_id"] = company_id
                        expense_data["company_name"] = expense.company_id.name

                    all_expenses.append(expense_data)

                # Refused expenses
                refused_domain = [
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'refused'),
                    ('company_id', '=', company_id),
                ]

                refused_expenses = envc['hr.expense'].sudo().search(refused_domain)

                for expense in refused_expenses:
                    expense_data = {
                        "id": expense.id,
                        "name": expense.name,
                        "date": expense.date.strftime('%Y-%m-%d') if expense.date else "",
                        "state": expense.state,
                        "total_amount": expense.total_amount,
                        "reject_reason": expense.sheet_id.reject_reason if expense.sheet_id and expense.sheet_id.reject_reason else ""
                    }

                    if len(allowed_company_ids) > 1:
                        expense_data["company_id"] = company_id
                        expense_data["company_name"] = expense.company_id.name

                    all_expenses.append(expense_data)

            # Sort by date
            def _sort_key(el):
                try:
                    return datetime.strptime(el.get('date') or '1970-01-01', '%Y-%m-%d')
                except Exception:
                    return datetime(1970, 1, 1)

            all_expenses.sort(key=_sort_key)

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({
                    "results": len(all_expenses),
                    "data": all_expenses
                })
            )

        except Exception as e:
            _logger.error(f"Error in get_employee_done_expenses: {str(e)}", exc_info=True)
            return invalid_response("error", str(e), 500)

    @validate_token
    @http.route("/api/employee/expenses/reviewed/card", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_expenses_reviewed_count(self, **post):
        """Get total reviewed expenses amount from all selected companies"""
        try:
            user = request.env.user
            allowed_company_ids = self._allowed_company_ids()

            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)

            total_reviewed_amount = 0.0

            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)

                if not employee:
                    continue

                reviewed_expenses = envc['hr.expense'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'draft'),
                    ('company_id', '=', company_id),
                ])

                total_reviewed_amount += sum(reviewed_expenses.mapped('total_amount'))

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"reviewed_expense_card": total_reviewed_amount}),
            )

        except Exception as e:
            _logger.error(f"Error in get_employee_expenses_reviewed_count: {str(e)}", exc_info=True)
            return invalid_response("error", str(e), 500)

    @validate_token
    @http.route("/api/employee/expenses/approved/card", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_expenses_approved_count(self, **post):
        """Get total approved expenses amount from all selected companies"""
        try:
            user = request.env.user
            allowed_company_ids = self._allowed_company_ids()

            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)

            total_approved_amount = 0.0

            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)

                if not employee:
                    continue

                approved_expenses = envc['hr.expense'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'approved'),
                    ('company_id', '=', company_id),
                ])

                total_approved_amount += sum(approved_expenses.mapped('total_amount'))

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"approved_expense_card": total_approved_amount}),
            )

        except Exception as e:
            _logger.error(f"Error in get_employee_expenses_approved_count: {str(e)}", exc_info=True)
            return invalid_response("error", str(e), 500)

    @validate_token
    @http.route("/api/employee/expenses/total/card", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_expenses_total_count(self, **post):
        """Get total expenses amount (draft + approved) from all selected companies"""
        try:
            user = request.env.user
            allowed_company_ids = self._allowed_company_ids()

            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)

            total_all = 0.0

            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)

                if not employee:
                    continue

                draft_expenses = envc['hr.expense'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'draft'),
                    ('company_id', '=', company_id),
                ])

                approved_expenses = envc['hr.expense'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'approved'),
                    ('company_id', '=', company_id),
                ])

                total_all += sum(draft_expenses.mapped('total_amount'))
                total_all += sum(approved_expenses.mapped('total_amount'))

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"total_expense_card": total_all}),
            )

        except Exception as e:
            _logger.error(f"Error in get_employee_expenses_total_count: {str(e)}", exc_info=True)
            return invalid_response("error", str(e), 500)

    @validate_token
    @http.route("/api/expenses/categories", methods=["GET"], type="http", auth="none", csrf=False)
    def get_category_expenses(self, **post):
        # user_id = request.uid
        # user_obj = request.env['res.users'].browse(user_id)
        company_id = self._current_company_id()
        envc = self._force_company_env()
        categories = envc['product.product'].sudo().search([('can_be_expensed', '=', True),] + self._company_scope_domain('company_id',allow_global=True))

        category_dict = {
            category.id: category.name for category in sorted(categories, key=lambda c: c.id)
        }

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps({"categories": category_dict}),
        )

    @validate_token
    @http.route("/api/expenses/request-types", methods=["GET"], type="http", auth="none", csrf=False)
    def get_request_types(self, **kw):
        try:
            envc = self._force_company_env()

            Model = envc["ao.request.samir"].sudo()

            domain = []
            if "company_id" in Model._fields:
                domain += self._company_scope_domain("company_id", allow_global=True)

            request_types = Model.search(domain, order="id asc")

            data = {str(r.id): (r.name or "") for r in request_types}

            return request.make_json_response({"request_types": data}, status=200)

        except Exception as e:
            _logger.exception("get_request_types error")
            return invalid_response("error", str(e), 500)

    @validate_token
    @http.route('/api/employee/expenses/expense-details', type='http', auth='public', methods=['GET'], csrf=False)
    def get_expense_details(self, **kwargs):
        company_id = self._current_company_id()
        employee = self._get_employee_for_user_in_company(request.env.user, company_id)
        if not employee:
            return invalid_response("no_employee", _t("no_employee"), 404)

        expense_id = kwargs.get("expense_id")
        if not expense_id:
            return invalid_response("missing_expense_id", "expense_id is required", 400)

        try:
            envc = self._force_company_env()
            record = envc['hr.expense'].sudo().search(
                [('employee_id', '=', employee.id), ('id', '=', int(expense_id))]
                + self._company_scope_domain('company_id', allow_global=False),
                limit=1
            )

            if not record:
                return request.make_json_response({
                    "status": "error",
                    "message": "Record not found!"
                }, status=404)

            # -------------------------
            # Messages (safe text)
            # -------------------------
            messages = []
            for message in record.message_ids:
                if message.message_type != "notification":
                    html_content = message.body or ""
                    soup = BeautifulSoup(html_content, 'html.parser')
                    text = soup.get_text(separator=' ', strip=True)
                    if text:
                        messages.append(text)

            # -------------------------
            # Attachments
            # -------------------------
            attachments = request.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'hr.expense'),
                ('res_id', '=', record.id)
            ])

            sent_attachments = []
            for attachment in attachments:
                sent_attachments.append({
                    'name': attachment.name or '',
                    'mimetype': attachment.mimetype or '',
                    'base64': attachment.datas.decode() if attachment.datas else '',
                    'extension': (attachment.name.split('.')[-1] if attachment.name and '.' in attachment.name else ''),
                })

            # -------------------------
            # SAFE request type read
            # -------------------------
            request_type_id = -1
            request_type_name = ""

            if 'x_request_type' in record._fields:
                try:
                    rt = record.x_request_type  # may fail if comodel not loaded
                    if rt and rt.exists():
                        request_type_id = rt.id
                        request_type_name = rt.name or ""
                except Exception:
                    # comodel missing/not loaded OR broken relation
                    request_type_id = -1
                    request_type_name = ""

            vals = {
                "id": record.id,
                "description": record.name or '',
                "category_id": record.product_id.id if record.product_id else -1,
                "category_name": record.product_id.name if record.product_id else '',
                "request_type_id": request_type_id,
                "request_type_name": request_type_name,
                "state": record.state or '',
                "reject_reason": (
                    record.sheet_id.reject_reason if record.sheet_id and record.sheet_id.reject_reason else ''),
                "date": (record.date.isoformat() if record.date else ''),
                "total_amount": record.total_amount_currency,
                "attachments": sent_attachments,
                "messages": messages
            }

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"data": vals}),
            )

        except Exception as e:
            _logger.exception("expense-details error")
            return Response(
                json.dumps({'success': False, 'error': str(e)}),
                content_type='application/json',
                status=500
            )

    @validate_token
    @http.route('/api/employee/expenses/expense-edit', type='http', auth='public', methods=['PUT'], csrf=False)
    def expense_edit(self, **kwargs):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        company_id = self._current_company_id()
        employee = self._get_employee_for_user_in_company(request.env.user, company_id)
        if not employee:
            return invalid_response("no_employee", _t("no_employee"), 404)

        expense_id = kwargs.get("expense_id")
        product_id = kwargs.get('category_id')
        description = kwargs.get('description')
        total_amount = kwargs.get('total_amount')
        request_type_id = kwargs.get('request_type_id')
        uploaded_files = request.httprequest.files

        try:
            envc = self._force_company_env()

            record = envc['hr.expense'].sudo().search(
                [('employee_id', '=', employee.id), ('id', '=', int(expense_id))]
                + self._company_scope_domain('company_id', allow_global=False),
                limit=1
            )

            if not record:
                return request.make_json_response({
                    "status": "error",
                    "message": "Record not found!"
                }, status=404)

            # Validate required fields
            if not all([product_id, description, total_amount]):
                return Response(
                    json.dumps({'success': False, 'error': 'Missing required fields'}),
                    content_type='application/json',
                    status=400
                )

            try:
                product_id = int(product_id)
                total_amount = float(total_amount)
            except ValueError:
                return Response(
                    json.dumps({'success': False, 'error': 'Invalid data format'}),
                    content_type='application/json',
                    status=400
                )

            product = envc['product.product'].sudo().search(
                [('id', '=', product_id)] + self._company_scope_domain('company_id', allow_global=True),
                limit=1
            )
            if not product:
                return Response(
                    json.dumps({'success': False, 'error': f'Product with ID {product_id} not found'}),
                    content_type='application/json',
                    status=404
                )

            company_id = self._current_company_id()
            company = request.env['res.company'].sudo().browse(company_id)
            currency = company.currency_id
            if not currency:
                return Response(
                    json.dumps({'success': False, 'error': 'Company has no currency set'}),
                    content_type='application/json',
                    status=400
                )

            # ✅ Update values
            update_vals = {
                'name': description,
                'product_id': product.id,
                'total_amount_currency': total_amount,
                'employee_id': employee.sudo().id,
                'currency_id': currency.id,
                'date': fields.Date.today(),
                'company_id': company_id,
            }

            # ✅ Only write request type if the field exists (avoid Invalid field error)
            if request_type_id and 'x_request_type' in envc['hr.expense']._fields:
                update_vals['x_request_type'] = int(request_type_id)

            envc['hr.expense'].sudo().browse(record.id).write(update_vals)

            # Handle file attachment
            if uploaded_files:
                files = uploaded_files.to_dict(flat=False)
                for file in files.get("file", []):
                    file_content = file.read()
                    file_name = file.filename
                    file_data = base64.b64encode(file_content)

                    request.env['ir.attachment'].sudo().create({
                        'name': file_name,
                        'type': 'binary',
                        'datas': file_data,
                        'res_model': 'hr.expense',
                        'res_id': record.id,
                    })

            return Response(
                json.dumps({'success': True, 'record_id': record.id}),
                content_type='application/json',
                status=200
            )

        except Exception as e:
            return Response(
                json.dumps({'success': False, 'error': str(e)}),
                content_type='application/json',
                status=500
            )


class FaceRecognitionController(http.Controller, MultiCompanyEmployeeMixin):

    @validate_token
    @http.route('/api/employee/test', type='http', auth='none', methods=['POST'], csrf=False)
    def test(self, **kwargs):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        company_id = self._current_company_id()
        employee = self._get_employee_for_user_in_company(request.env.user, company_id)
        if not employee:
            return invalid_response("no_employee", _t("no_employee"), 404)

        payload = request.httprequest.data.decode()
        payload = json.loads(payload)

        uuid = payload.get("uuid")

        try:
            uuid_record = request.env['uuid.model'].sudo().check_and_update_uuid(uuid, employee.sudo().id)

            if uuid_record["state"] == "approved":
                return request.make_json_response(
                    ({
                        "status": "success",
                        "message": uuid_record["message"]
                    }),
                    status=200
                )
            elif uuid_record["state"] == "rejected":
                return request.make_json_response(
                    ({
                        "status": "fail",
                        "message": uuid_record["message"]
                    }),
                    status=400
                )
            elif uuid_record["state"] == "created":
                return request.make_json_response(
                    ({
                        "status": "success",
                        "message": uuid_record["message"]
                    }),
                    status=201
                )
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})

    @validate_token
    @http.route('/api/employee/uuid', type='http', auth='none', methods=['POST'], csrf=False)
    def post_biometric(self, **kwargs):
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            company_id = self._current_company_id()
            employee = self._get_employee_for_user_in_company(request.env.user, company_id)
            if not employee:
                return invalid_response("no_employee", _t("no_employee"), 404)

            payload = request.httprequest.data.decode()
            payload = json.loads(payload)

            uuid = payload.get("uuid")

            # check if accepting new UUIDs for employees is enabled/disabled
            if employee.checked_toggle_flag == False:
                return json.dumps({
                    'success': False,
                    'state': 'rejected',
                    'message': "You can't add UUIDs"
                })
            else:
                # uuid_record = request.env['uuid.model'].sudo().check_and_update_bio(uuid, employee.sudo().id)
                uuid_record = request.env['uuid.model'].sudo().create({'uuid': uuid, 'employee_id': employee.sudo().id})
                if not uuid_record:  # Handle case where method returns None
                    return json.dumps({
                        'success': False,
                        'state': 'error',
                        'message': 'UUID verification failed (no response)'
                    })

                # Return the state and message from bio_record
                return request.make_json_response(({"status": "success"}), status=200)
                # return json.dumps({
                #     'success': uuid_record.get('state') == 'approved',
                #     'state': uuid_record.get('state', 'error'),
                #     'message': uuid_record.get('message', 'Unknown uuid status')
                # })

            # if uuid_record.get('uuid_status') == 'approved':
            #     return json.dumps({
            #         'success': True,
            #         'state': 'approved',
            #         'message': uuid_record.get('message', 'Biometric verification successful')
            #     })
            # else:
            #     return json.dumps({
            #         'success': False,
            #         'state': 'rejected',
            #         'message': uuid_record.get('message', 'Biometric verification failed')
            #     })

        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})

    @validate_token
    @http.route('/employee/api/face/recognition', type='http', auth='none', methods=['POST'], csrf=False)
    def post_image(self, **kwargs):
        try:
            # Get patient_id from request
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            company_id = self._current_company_id()
            employee = self._get_employee_for_user_in_company(request.env.user, company_id)
            if not employee:
                return json.dumps(
                    {'success': False, 'error': 'No employee linked to this user in the selected company'})

            # Handle image file
            image = kwargs.get('image')
            image_base64 = False
            if image:
                image_base64 = base64.b64encode(image.read()).decode('utf-8')

            image_record = request.env['image.model'].sudo().create({
                'images': image_base64,
                'employee_id_rel': employee.sudo().id  # This links it to the patient
            })

            return json.dumps({'success': True, 'image_id': image_record.id, 'employee_id': employee.sudo().id})

        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})


class PayrollController(http.Controller, MultiCompanyEmployeeMixin):

    @validate_token
    @http.route('/api/employee/payslip', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_details(self, **kwargs):
        try:
            payslip_id = kwargs.get("payslip_id")
            if not payslip_id:
                return invalid_response("missing", "payslip_id is required", 400)

            try:
                payslip_id = int(payslip_id)
            except Exception:
                return invalid_response("invalid", "payslip_id must be an integer", 400)

            allowed_company_ids = self._allowed_company_ids() or []
            if not allowed_company_ids:
                allowed_company_ids = [self._current_company_id()]

            payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
            if not payslip.exists():
                return invalid_response("not_found", "Payslip not found", 404)

            if payslip.company_id and payslip.company_id.id not in allowed_company_ids:
                return invalid_response("not_found", "Payslip is not in selected companies", 404)

            if not payslip.employee_id or payslip.employee_id.user_id.id != request.env.user.id:
                return invalid_response("not_found", "Payslip not found or not yours", 404)

            envc = self._force_company_env(
                company_id=payslip.company_id.id if payslip.company_id else None,
                allowed_company_ids=allowed_company_ids
            )
            payslip = envc['hr.payslip'].sudo().browse(payslip_id)

            lines_data = []
            for line in payslip.line_ids:
                lines_data.append({
                    'name': line.name,
                    'code': line.code,
                    'category': line.category_id.name if line.category_id else None,
                    'total': line.total,
                    'amount': line.amount,
                    'quantity': line.quantity,
                    'rate': line.rate,
                })

            return request.make_json_response({
                "status": "success",
                "data": {
                    "payslip_id": payslip.id,
                    "company_id": payslip.company_id.id if payslip.company_id else None,
                    "company_name": payslip.company_id.name if payslip.company_id else "",
                    "period": f"{payslip.date_from.strftime('%d %b')} to {payslip.date_to.strftime('%d %b')}" if payslip.date_from and payslip.date_to else "",
                    "lines": lines_data,
                    "net_salary": payslip.line_ids.filtered(lambda l: l.code == 'NET').total,
                    "state": payslip.state,
                }
            }, status=200)

        except Exception as e:
            return invalid_response("error", str(e), 500)

    # def get_payslip(self, **kwargs):
    #     try:
    #         payslip_id = kwargs.get("payslip_id")
    #         employee_id = kwargs.get("employee_id")
    #         date_start = kwargs.get("date_start")
    #         date_end = kwargs.get("date_end")
    #         vals = {}

    #         employee_obj = request.env['hr.employee'].sudo().search([("id", "=", employee_id)], limit=1)
    #         if not employee_obj:
    #             return valid_response([{"error": "No employee associated with this ID"}], status=404)

    #         payslip_obj = request.env['hr.payslip'].sudo().search([("id", "=", payslip_id)], limit=1)
    #         if not payslip_obj:
    #             return valid_response([{"error": "No payslip associated with this ID"}], status=404)

    #         vals = {
    #             "id": payslip_obj.id,
    #             "name": payslip_obj.name,
    #             "date_from": payslip_obj.date_from,
    #             "date_to": payslip_obj.date_to,
    #             "status": payslip_obj.state,
    #             "payslip_net": payslip_obj.payslip_net,
    #             "total_salary": payslip_obj.x_total_salary,
    #             "x_total": payslip_obj.x_total
    #         }

    #         if date_start:
    #             date_start_datetime = datetime.strptime(date_start, "%m/%d/%Y")
    #             payslip_from_date_start = request.env['hr.payslip'].sudo().search(
    #                 [
    #                     ("id", "=", payslip_id),
    #                     ("date_from", "=", date_start_datetime)
    #                 ],
    #                 limit=1
    #             )
    #             if not payslip_from_date_start:
    #                 return valid_response([{"error": "No payslip associated with this date"}], status=404)

    #             vals = {
    #                 "id": payslip_from_date_start.id,
    #                 "name": payslip_from_date_start.name,
    #                 "date_from": payslip_from_date_start.date_from,
    #                 "date_to": payslip_from_date_start.date_to,
    #                 "status": payslip_from_date_start.state,
    #                 "payslip_net": payslip_from_date_start.payslip_net,
    #                 "total_salary": payslip_from_date_start.x_total_salary,
    #                 "x_total": payslip_from_date_start.x_total
    #             }

    #         if date_end:
    #             date_end_datetime = datetime.strptime(date_end, "%m/%d/%Y")
    #             payslip_from_date_end = request.env['hr.payslip'].sudo().search(
    #                 [
    #                     ("id", "=", payslip_id),
    #                     ("date_from", "=", date_end_datetime)
    #                 ],
    #                 limit=1
    #             )
    #             if not payslip_from_date_end:
    #                 return valid_response([{"error": "No payslip associated with this date"}], status=404)

    #             vals = {
    #                 "id": payslip_from_date_end.id,
    #                 "name": payslip_from_date_end.name,
    #                 "date_from": payslip_from_date_end.date_from,
    #                 "date_to": payslip_from_date_end.date_to,
    #                 "status": payslip_from_date_end.state,
    #                 "payslip_net": payslip_from_date_end.payslip_net,
    #                 "total_salary": payslip_from_date_end.x_total_salary,
    #                 "x_total": payslip_from_date_end.x_total
    #             }

    #         return request.make_json_response(({
    #             "status": "success",
    #             "data": vals
    #         }), status=200)
    #     except Exception as e:
    #         return valid_response({"error": str(e)}, status=500)

    @validate_token
    @http.route('/api/employee/total-payslips', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_payslips(self, **kwargs):
        """
        Get payslips from all selected companies
        If only one company selected, returns data for that company only
        If multiple companies selected, returns combined data with company info
        """
        try:
            user = request.env.user

            # Get selected companies from session
            allowed_company_ids = self._allowed_company_ids()

            if not allowed_company_ids:
                return valid_response({
                    'status': 'error',
                    'message': 'No companies selected.'
                }, status=400)

            all_payslips = []

            # Loop through each selected company
            for company_id, envc in self._iter_company_envs():
                # Get employee in this company
                employee = self._get_employee_for_user_in_company(user, company_id)

                if not employee:
                    # User has no employee record in this company - skip
                    continue

                # Get payslips for this employee in this company
                payslips = envc['hr.payslip'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('company_id', '=', company_id),
                ], order='date_from asc')

                for slip in payslips:
                    month_name = slip.date_from.strftime('%B %Y') if slip.date_from else ''
                    period = f"{slip.date_from.strftime('%d %b')} to {slip.date_to.strftime('%d %b')}" if slip.date_from and slip.date_to else ''
                    net_salary = slip.line_ids.filtered(lambda l: l.code == 'NET').total

                    payslip_data = {
                        'payslip_id': slip.id,
                        'month': month_name,
                        'period': period,
                        'net_salary': net_salary,
                        'status': slip.state,
                    }

                    # Add company info if multiple companies selected
                    if len(allowed_company_ids) > 1:
                        payslip_data['company_id'] = company_id
                        payslip_data['company_name'] = slip.company_id.name

                    all_payslips.append(payslip_data)

            return valid_response(all_payslips)

        except Exception as e:
            _logger.error(f"Error in get_employee_payslips: {str(e)}", exc_info=True)
            return valid_response({"error": str(e)}, status=500)
    # def get_total_payslips(self, **kwargs):
    #     try:
    #         user_id = request.uid
    #         user_obj = request.env['res.users'].browse(user_id)
    #         employee_obj = user_obj.employee_id

    #         if not employee_obj:
    #             return valid_response([{"error": "No employee associated with this ID"}], status=404)

    #         payslip_recs = []
    #         for rec in employee_obj.slip_ids:
    #             vals = {
    #                 "id": rec.id,
    #                 "name": rec.name
    #             }
    #             payslip_recs.append(vals)
    #         return valid_response(payslip_recs)
    #     except Exception as e:
    #         return valid_response({"error": str(e)}, status=500)


class TimeoffController(http.Controller, MultiCompanyEmployeeMixin):
    # =============================================================
    # TIMEOFF — rewritten 2026-05-12 for SJC mobile app
    # All endpoints:
    #   - require a valid access-token header
    #   - run as the token user (request.env.user, never request.uid)
    #   - return predictable response shape: {"count": N, "data": ...}
    #   - return 4xx on user errors, 5xx only on unexpected exceptions
    # =============================================================

    def _current_user(self):
        """Token-authenticated user (the validate_token decorator sets
        request.env to be authenticated as this user)."""
        return request.env.user

    def _format_leave(self, req, include_employee_name=False, include_company=False, include_validation=False):
        """Serialize an hr.leave record for the mobile app."""
        data = {
            "id": req.id,
            "name": req.name or "",
            "holiday_type": req.holiday_status_id.name or "",
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
        if include_company and req.employee_id and req.employee_id.company_id:
            data["company_id"] = req.employee_id.company_id.id
            data["company_name"] = req.employee_id.company_id.name or ""
        if include_validation:
            data["multi_level_validation"] = bool(req.multi_level_validation)
            my_uid = self._current_user().id
            my_row = req.validation_status_ids.filtered(lambda v: v.user_id.id == my_uid)
            data["my_approval_status"] = bool(my_row[0].validation_status) if my_row else None
            data["is_validator"] = bool(my_row) and not (my_row[0].validation_status if my_row else False)
            data["validators_approved"] = len(req.validation_status_ids.filtered(lambda v: v.validation_status))
            data["validators_total"] = len(req.validation_status_ids)
        return data

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

    @validate_token
    @http.route('/api/employee/timeoff/create', type='http', auth='public', methods=['POST'], csrf=False)
    def create_timeoff_request(self, **kwargs):
        """Create a new time-off request for the authenticated user, in the
        currently-selected company."""
        try:
            user = self._current_user()
            company_id = int(self._current_company_id() or 0)
            if not company_id:
                return invalid_response("no_company", _t("no_company"), 400)

            employee = self._get_employee_for_user_in_company(user, company_id)
            if not employee:
                return invalid_response("no_employee", _t("no_employee"), 404)

            try:
                payload = json.loads(request.httprequest.data.decode() or "{}")
            except Exception:
                return invalid_response("bad_json", _t("bad_json"), 400)

            holiday_status_id = payload.get("holiday_status_id")
            request_date_from = payload.get("request_date_from")
            request_date_to = payload.get("request_date_to")
            name = payload.get("name") or "Time Off Request"
            number_of_days = payload.get("number_of_days")
            request_unit_half = bool(payload.get("request_unit_half") or False)
            request_date_from_period = payload.get("request_date_from_period") or ""

            if not holiday_status_id or not request_date_from or not request_date_to:
                return invalid_response("missing_fields", _t("create_missing_fields"), 400)
            if request_unit_half and request_date_from_period not in ("am", "pm"):
                return invalid_response("missing_fields", _t("create_half_day_period"), 400)

            try:
                date_from = datetime.strptime(request_date_from, '%Y-%m-%d').date()
                date_to = datetime.strptime(request_date_to, '%Y-%m-%d').date()
            except ValueError:
                return invalid_response("bad_date", _t("bad_date"), 400)

            if date_to < date_from:
                return invalid_response("bad_date_range", _t("bad_date_range"), 400)

            envc = self._force_company_env(company_id=company_id)

            leave_type = envc['hr.leave.type'].sudo().browse(int(holiday_status_id))
            if not leave_type.exists():
                return invalid_response("leave_type_not_found", _t("leave_type_not_found"), 404)

            # Balance pre-check (only for types that require allocation)
            # In Odoo 17, requires_allocation is a selection: 'yes' or 'no'.
            requires_alloc = (leave_type.requires_allocation == 'yes')
            allow_negative = bool(
                getattr(leave_type, "allows_negative", False)
                or getattr(leave_type, "allow_negative", False)
                or getattr(leave_type, "allow_override_limit", False)
            )

            ctx = dict(envc.context or {})
            ctx.update({
                "employee_id": int(employee.id),
                "default_employee_id": int(employee.id),
            })
            lt_ctx = leave_type.with_context(ctx)
            remaining = getattr(lt_ctx, "virtual_remaining_leaves", None)
            if remaining is None:
                remaining = getattr(lt_ctx, "remaining_leaves", 0.0)
            try:
                remaining = float(remaining or 0.0)
            except Exception:
                remaining = 0.0

            requested_days = None
            if number_of_days is not None:
                try:
                    requested_days = float(number_of_days)
                except Exception:
                    return invalid_response("invalid_days", _t("invalid_days"), 400)

            if requires_alloc and not allow_negative:
                check_days = requested_days if requested_days is not None else (
                    0.5 if request_unit_half else float((date_to - date_from).days + 1)
                )
                if remaining < check_days:
                    return invalid_response(
                        "insufficient_balance",
                        "%s — %s: %.2f, %s: %.2f" % (
                            _t("insufficient_balance"),
                            "المتبقي" if _request_lang() == "ar" else "Remaining",
                            remaining,
                            "المطلوب" if _request_lang() == "ar" else "Requested",
                            check_days,
                        ),
                        400,
                    )

            vals = {
                'name': name,
                'employee_id': int(employee.id),
                'holiday_status_id': int(holiday_status_id),
                'request_date_from': date_from,
                'request_date_to': date_to,
                'request_unit_half': request_unit_half,
                'request_date_from_period': request_date_from_period if request_unit_half else False,
                'company_id': company_id,
            }
            if requested_days is not None:
                vals['number_of_days'] = float(requested_days)

            leave = envc['hr.leave'].sudo().with_context(ctx).create(vals)

            # Transition to "confirm" (To Approve) — this also runs the
            # standard onchange-style validation built into hr.leave.action_confirm.
            if leave.state == 'draft' and hasattr(leave, 'action_confirm'):
                try:
                    leave.sudo().action_confirm()
                except UserError as ue:
                    leave.sudo().unlink()
                    return invalid_response("validation_error", str(ue), 400)

            # Re-seed multi-level validators (matches the onchange behaviour
            # so the request shows up in each validator's pending list).
            try:
                leave.sudo().validation_status_ids = [(5, 0, 0)]
                existing = leave.validation_status_ids.mapped("user_id").ids
                rows = []
                for v in leave.holiday_status_id.validator_ids.filtered(lambda x: x.user_id.id not in existing):
                    rows.append((0, 0, {"user_id": v.user_id.id}))
                if rows:
                    leave.sudo().validation_status_ids = rows
            except Exception:
                # Custom approval module not installed or field absent — fine.
                pass

            response_data = self._format_leave(leave, include_employee_name=True)
            response_data["remaining_before_submit"] = remaining
            return valid_response(response_data, status=201)

        except ValidationError as e:
            return invalid_response("validation_error", str(e), 400)
        except UserError as e:
            return invalid_response("user_error", str(e), 400)
        except AccessError as e:
            return invalid_response("access_error", str(e), 403)
        except Exception as e:
            _logger.exception("create_timeoff_request failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/api/employee/timeoff/requests', type='http', auth='public', methods=['GET'], csrf=False)
    def get_timeoff_requests(self, **kwargs):
        """List the current employee's time-off requests across all selected companies.
        Optional ?state= to filter by state."""
        try:
            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids()
            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)

            state = kwargs.get("state")
            all_requests = []
            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)
                if not employee:
                    continue
                domain = [
                    ('employee_id', '=', employee.id),
                    ('employee_id.company_id', '=', company_id),
                ]
                if state:
                    domain.append(('state', '=', state))
                for req in envc['hr.leave'].sudo().search(domain, order='create_date desc'):
                    all_requests.append(self._format_leave(
                        req,
                        include_company=(len(allowed_company_ids) > 1),
                    ))
            return valid_response(all_requests)
        except Exception as e:
            _logger.exception("get_timeoff_requests failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/api/employee/timeoff/requests/pending', type='http', auth='public', methods=['GET'], csrf=False)
    def get_pending_requests(self, **kwargs):
        """Current user's pending requests (confirm + validate1) across selected companies."""
        try:
            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids()
            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)
            all_requests = []
            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)
                if not employee:
                    continue
                domain = [
                    ('employee_id', '=', employee.id),
                    ('employee_id.company_id', '=', company_id),
                    ('state', 'in', ['confirm', 'validate1']),
                ]
                for req in envc['hr.leave'].sudo().search(domain, order='create_date desc'):
                    all_requests.append(self._format_leave(
                        req,
                        include_company=(len(allowed_company_ids) > 1),
                    ))
            return valid_response(all_requests)
        except Exception as e:
            _logger.exception("get_pending_requests failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/api/employee/timeoff/requests/approved', type='http', auth='public', methods=['GET'], csrf=False)
    def get_approved_requests(self, **kwargs):
        """Current user's approved (validate) requests across selected companies."""
        try:
            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids()
            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)
            all_requests = []
            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)
                if not employee:
                    continue
                domain = [
                    ('employee_id', '=', employee.id),
                    ('employee_id.company_id', '=', company_id),
                    ('state', '=', 'validate'),
                ]
                for req in envc['hr.leave'].sudo().search(domain, order='request_date_from desc'):
                    all_requests.append(self._format_leave(
                        req,
                        include_company=(len(allowed_company_ids) > 1),
                    ))
            return valid_response(all_requests)
        except Exception as e:
            _logger.exception("get_approved_requests failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/api/employee/timeoff/requests/refused', type='http', auth='public', methods=['GET'], csrf=False)
    def get_refused_requests(self, **kwargs):
        """Current user's refused requests across selected companies."""
        try:
            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids()
            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)
            all_requests = []
            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)
                if not employee:
                    continue
                domain = [
                    ('employee_id', '=', employee.id),
                    ('employee_id.company_id', '=', company_id),
                    ('state', '=', 'refuse'),
                ]
                for req in envc['hr.leave'].sudo().search(domain, order='create_date desc'):
                    all_requests.append(self._format_leave(
                        req,
                        include_company=(len(allowed_company_ids) > 1),
                    ))
            return valid_response(all_requests)
        except Exception as e:
            _logger.exception("get_refused_requests failed")
            return invalid_response("server_error", str(e), 500)

    def _user_has_pending_validation(self, leave, uid):
        """Return True iff `uid` has a validation_status_ids row on this leave
        whose `validation_status` is falsy (not yet approved). False/NULL in
        the DB both count as "not approved yet"."""
        for vs in leave.validation_status_ids:
            if vs.user_id and vs.user_id.id == uid:
                return not bool(vs.validation_status)
        return False

    def _user_has_approved(self, leave, uid):
        """Return True iff `uid` already approved this leave (their row exists
        and validation_status is true)."""
        for vs in leave.validation_status_ids:
            if vs.user_id and vs.user_id.id == uid and vs.validation_status:
                return True
        return False

    @validate_token
    @http.route('/api/manager/timeoff/requests/pending', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_pending_requests(self, **kwargs):
        """Manager view: requests awaiting the current user's validation,
        across all allowed companies. Paginated.

        Only leaves where the current user is a validator AND has NOT yet
        toggled their validation_status to true are returned. (Earlier
        versions used an ORM domain that allowed false positives because
        Odoo evaluates each one2many sub-condition independently across the
        validation_status_ids rows.)"""
        try:
            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids() or []
            allowed_company_ids = [int(c) for c in allowed_company_ids if c]
            if not allowed_company_ids:
                allowed_company_ids = [int(self._current_company_id() or 0)]
            try:
                page = max(1, int(kwargs.get('page', 1)))
                limit = max(1, min(int(kwargs.get('limit', 10)), 100))
            except Exception:
                page, limit = 1, 10

            Leave = request.env['hr.leave'].sudo().with_context(allowed_company_ids=allowed_company_ids)
            # Pre-filter to leaves the user is at least listed as a validator
            # for. We accept some over-fetching here and filter in Python.
            candidates = Leave.search([
                ('state', 'in', ['confirm', 'validate1']),
                ('employee_id.company_id', 'in', allowed_company_ids),
                ('validation_status_ids.user_id', '=', user.id),
            ], order='create_date desc')

            actually_pending = candidates.filtered(lambda l: self._user_has_pending_validation(l, user.id))
            total_count = len(actually_pending)
            offset = (page - 1) * limit
            page_slice = actually_pending[offset:offset + limit]

            response_data = {
                "data": [self._format_leave(r, include_employee_name=True, include_company=True,
                                            include_validation=True) for r in page_slice],
                "meta": {"pagination": self._serialize_pagination(page, limit, total_count)},
            }
            return valid_response(response_data)
        except Exception as e:
            _logger.exception("get_all_pending_requests failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/api/manager/timeoff/requests/approved', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_approved_requests(self, **kwargs):
        """Manager view: requests this user validated (or has visibility on)
        that are now in 'validate' state, across all allowed companies. Paginated."""
        try:
            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids() or []
            allowed_company_ids = [int(c) for c in allowed_company_ids if c]
            if not allowed_company_ids:
                allowed_company_ids = [int(self._current_company_id() or 0)]
            try:
                page = max(1, int(kwargs.get('page', 1)))
                limit = max(1, min(int(kwargs.get('limit', 10)), 100))
            except Exception:
                page, limit = 1, 10
            offset = (page - 1) * limit

            Leave = request.env['hr.leave'].sudo().with_context(allowed_company_ids=allowed_company_ids)
            domain = [
                ('state', '=', 'validate'),
                ('employee_id.company_id', 'in', allowed_company_ids),
                ('validation_status_ids.user_id', '=', user.id),
            ]
            total_count = Leave.search_count(domain)
            leaves = Leave.search(domain, order='create_date desc', limit=limit, offset=offset)
            response_data = {
                "data": [self._format_leave(r, include_employee_name=True, include_company=True) for r in leaves],
                "meta": {"pagination": self._serialize_pagination(page, limit, total_count)},
            }
            return valid_response(response_data)
        except Exception as e:
            _logger.exception("get_all_approved_requests failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/api/manager/timeoff/requests/refused', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_refused_requests(self, **kwargs):
        """Manager view: refused requests this user has visibility on, across
        all allowed companies. Paginated."""
        try:
            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids() or []
            allowed_company_ids = [int(c) for c in allowed_company_ids if c]
            if not allowed_company_ids:
                allowed_company_ids = [int(self._current_company_id() or 0)]
            try:
                page = max(1, int(kwargs.get('page', 1)))
                limit = max(1, min(int(kwargs.get('limit', 10)), 100))
            except Exception:
                page, limit = 1, 10
            offset = (page - 1) * limit

            Leave = request.env['hr.leave'].sudo().with_context(allowed_company_ids=allowed_company_ids)
            domain = [
                ('state', '=', 'refuse'),
                ('employee_id.company_id', 'in', allowed_company_ids),
                ('validation_status_ids.user_id', '=', user.id),
            ]
            total_count = Leave.search_count(domain)
            leaves = Leave.search(domain, order='create_date desc', limit=limit, offset=offset)
            response_data = {
                "data": [self._format_leave(r, include_employee_name=True, include_company=True) for r in leaves],
                "meta": {"pagination": self._serialize_pagination(page, limit, total_count)},
            }
            return valid_response(response_data)
        except Exception as e:
            _logger.exception("get_all_refused_requests failed")
            return invalid_response("server_error", str(e), 500)

    def _get_color_hex(self, color_index):
        """Convert Odoo color index to hex color."""
        color_map = {
            0: '#FFFFFF', 1: '#CC7B7B', 2: '#CC9999', 3: '#CCAAAA',
            4: '#CCBBBB', 5: '#CCCCCC', 6: '#CCDDCC', 7: '#CCEECC',
            8: '#CCFFCC', 9: '#CCCCFF', 10: '#CCDDFF', 11: '#CCEEFF',
        }
        return color_map.get(color_index, '#CCCCCC')

    @validate_token
    @http.route('/api/employee/timeoff/balance', type='http', auth='public', methods=['GET'], csrf=False)
    def get_timeoff_balance(self, **kwargs):
        """Per-type leave balance for the current user, summed across all
        selected companies.

          - total_allocated: sum of validated allocations
          - total_spent: sum of validated (taken) leaves
          - pending_days: sum of submitted-but-not-yet-validated leaves
          - remaining_days: allocated - spent - pending (so the user sees
                           their *available-to-request* balance honestly)
        """
        try:
            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids()
            if not allowed_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)
            holiday_status_id = kwargs.get("holiday_status_id")

            all_types_balance = []
            grand_total_allocated = 0.0
            grand_total_spent = 0.0
            grand_total_pending = 0.0
            grand_total_remaining = 0.0
            seen_keys = set()

            for company_id, envc in self._iter_company_envs():
                employee = self._get_employee_for_user_in_company(user, company_id)
                if not employee:
                    continue

                lt_domain = []
                if holiday_status_id:
                    lt_domain.append(('id', '=', int(holiday_status_id)))
                holiday_types = envc['hr.leave.type'].sudo().search(lt_domain)

                for ht in holiday_types:
                    allocations = envc['hr.leave.allocation'].sudo().search([
                        ('employee_id', '=', employee.id),
                        ('employee_id.company_id', '=', company_id),
                        ('holiday_status_id', '=', ht.id),
                        ('state', '=', 'validate'),
                    ])
                    total_allocated = sum(allocations.mapped('number_of_days')) or 0.0

                    approved = envc['hr.leave'].sudo().search([
                        ('employee_id', '=', employee.id),
                        ('employee_id.company_id', '=', company_id),
                        ('holiday_status_id', '=', ht.id),
                        ('state', '=', 'validate'),
                    ])
                    total_spent = sum(approved.mapped('number_of_days')) or 0.0

                    pending = envc['hr.leave'].sudo().search([
                        ('employee_id', '=', employee.id),
                        ('employee_id.company_id', '=', company_id),
                        ('holiday_status_id', '=', ht.id),
                        ('state', 'in', ['confirm', 'validate1']),
                    ])
                    pending_days = sum(pending.mapped('number_of_days')) or 0.0
                    remaining = float(total_allocated) - float(total_spent) - float(pending_days)

                    type_key = f"{ht.id}_{company_id}" if len(allowed_company_ids) > 1 else str(ht.id)
                    if type_key in seen_keys:
                        continue
                    seen_keys.add(type_key)

                    item = {
                        "holiday_type_id": ht.id,
                        "holiday_type_name": ht.name or "",
                        "total_allocated": float(total_allocated),
                        "total_spent": float(total_spent),
                        "pending_days": float(pending_days),
                        "remaining_days": float(remaining),
                        "color": self._get_color_hex(ht.color),
                    }
                    if len(allowed_company_ids) > 1:
                        item["company_id"] = company_id
                        item["company_name"] = envc['res.company'].sudo().browse(company_id).name
                    all_types_balance.append(item)

                    grand_total_allocated += total_allocated
                    grand_total_spent += total_spent
                    grand_total_pending += pending_days
                    grand_total_remaining += remaining

            return valid_response({
                "types": all_types_balance,
                "all_allocated": float(grand_total_allocated),
                "all_spent": float(grand_total_spent),
                "all_pending": float(grand_total_pending),
                "all_remaining": float(grand_total_remaining),
            })
        except Exception as e:
            _logger.exception("get_timeoff_balance failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/api/employee/timeoff/types', type='http', auth='public', methods=['GET'], csrf=False)
    def get_timeoff_types(self, **kwargs):
        """Available leave types for the current company scope."""
        try:
            envc = self._force_company_env()
            timeoff_types = envc['hr.leave.type'].sudo().search(
                self._company_scope_domain('company_id', allow_global=True)
            )
            types_data = []
            for tt in timeoff_types:
                types_data.append({
                    "id": tt.id,
                    "name": tt.name or "",
                    "color": self._get_color_hex(tt.color),
                    "requires_allocation": tt.requires_allocation,
                    "active": bool(tt.active),
                })
            return valid_response(types_data)
        except Exception as e:
            _logger.exception("get_timeoff_types failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/api/employee/timeoff/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    def cancel_timeoff_request(self, **kwargs):
        """Cancel one's own time-off request. Only allowed while the request
        is in draft or confirm state. Searches across all allowed companies."""
        try:
            try:
                payload = json.loads(request.httprequest.data.decode() or "{}")
            except Exception:
                return invalid_response("bad_json", _t("bad_json"), 400)
            request_id = payload.get("request_id")
            if not request_id:
                return invalid_response("missing_fields", _t("missing_fields"), 400)
            try:
                req_id = int(request_id)
            except Exception:
                return invalid_response("invalid_id", _t("invalid_id"), 400)

            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids() or [int(self._current_company_id() or 0)]
            allowed_company_ids = [int(c) for c in allowed_company_ids if c]

            leave = None
            found_company_id = None
            for company_id, envc in self._iter_company_envs():
                if int(company_id) not in allowed_company_ids:
                    continue
                employee = self._get_employee_for_user_in_company(user, company_id)
                if not employee:
                    continue
                hit = envc['hr.leave'].sudo().search([
                    ('id', '=', req_id),
                    ('employee_id', '=', employee.id),
                    ('company_id', '=', company_id),
                ], limit=1)
                if hit:
                    leave = hit
                    found_company_id = company_id
                    break

            if not leave or not leave.exists():
                return invalid_response("not_found", _t("request_not_found"), 404)
            if leave.state not in ('draft', 'confirm'):
                return invalid_response("bad_state",
                                        f"{_t('bad_state_cancel')} ({leave.state})", 400)

            try:
                if hasattr(leave, 'action_refuse'):
                    leave.sudo().action_refuse()
                elif hasattr(leave, 'action_cancel'):
                    leave.sudo().action_cancel()
                else:
                    if hasattr(leave, 'action_draft'):
                        leave.sudo().action_draft()
                    leave.sudo().unlink()
            except UserError as ue:
                return invalid_response("user_error", str(ue), 400)

            return valid_response({
                "message": _t("cancel_success"),
                "request_id": req_id,
                "company_id": int(found_company_id) if found_company_id else None,
            })
        except Exception as e:
            _logger.exception("cancel_timeoff_request failed")
            return invalid_response("server_error", str(e), 500)

    def _load_manager_leave(self, request_id, allowed_company_ids):
        """Locate a leave the current user is allowed to act on.
        Returns the (leave, company_id) pair or (None, None)."""
        try:
            req_id = int(request_id)
        except Exception:
            return None, None
        user = self._current_user()
        for company_id, envc in self._iter_company_envs():
            if int(company_id) not in [int(c) for c in allowed_company_ids if c]:
                continue
            leave = envc['hr.leave'].sudo().search([
                ('id', '=', req_id),
                ('employee_id.company_id', '=', company_id),
                ('validation_status_ids.user_id', '=', user.id),
            ], limit=1)
            if leave:
                return leave, company_id
        # Fallback: maybe the user is allowed but not in validation_status_ids
        # (e.g. global hr_holidays manager). Allow if has the group.
        if user.has_group('hr_holidays.group_hr_holidays_manager'):
            leave = request.env['hr.leave'].sudo().search([
                ('id', '=', req_id),
                ('employee_id.company_id', 'in', [int(c) for c in allowed_company_ids if c]),
            ], limit=1)
            if leave:
                return leave, leave.employee_id.company_id.id
        return None, None

    @validate_token
    @http.route('/api/manager/timeoff/approve', type='http', auth='public', methods=['POST'], csrf=False)
    def approve_timeoff_request(self, **kwargs):
        """Approve a time-off request (first or final stage, depending on
        multi-level setup). The action is run AS the current user, so the
        per-validator approval row is properly toggled."""
        try:
            try:
                payload = json.loads(request.httprequest.data.decode() or "{}")
            except Exception:
                return invalid_response("bad_json", _t("bad_json"), 400)
            request_id = payload.get("request_id")
            if not request_id:
                return invalid_response("missing_fields", _t("missing_fields"), 400)

            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids() or [int(self._current_company_id() or 0)]
            leave, _company_id = self._load_manager_leave(request_id, allowed_company_ids)
            if not leave:
                return invalid_response("not_found",
                                        _t("request_not_found_or_not_validator"), 404)

            # Guard: this user already approved this leave (their per-validator
            # row is already true). Return 400 with a clear, actionable message
            # rather than silently calling action_approve() again (which is a
            # no-op and confuses the mobile UI).
            if self._user_has_approved(leave, user.id):
                return invalid_response("already_approved", _t("already_approved"), 400)

            # Run as the actual user (NOT sudo) so per-validator row matching
            # works inside the custom approval module.
            try:
                leave_as_user = leave.with_user(user.id)
                if leave.state == 'confirm':
                    leave_as_user.action_approve()
                elif leave.state == 'validate1':
                    leave_as_user.action_validate()
                else:
                    return invalid_response("bad_state",
                                            f"{_t('bad_state_approve')} ({leave.state})", 400)
            except UserError as ue:
                return invalid_response("user_error", str(ue), 400)
            except AccessError as ae:
                return invalid_response("access_error", str(ae), 403)

            # Refresh to capture state change
            leave.invalidate_recordset()

            # Build a message that reflects whether the leave is fully
            # approved or still waiting on other validators.
            approved_count = sum(1 for vs in leave.validation_status_ids if vs.validation_status)
            total_count = len(leave.validation_status_ids)
            fully_approved = (leave.state == 'validate')
            if fully_approved:
                msg = _t("fully_approved")
            elif total_count > 1 and approved_count < total_count:
                msg = _t("partial_approval", n=total_count - approved_count)
            else:
                msg = _t("approve_success")

            return valid_response({
                "message": msg,
                "request_id": leave.id,
                "state": leave.state,
                "state_display": dict(leave._fields['state'].selection).get(leave.state, leave.state),
                "fully_approved": fully_approved,
                "validators_approved": approved_count,
                "validators_total": total_count,
            })
        except Exception as e:
            _logger.exception("approve_timeoff_request failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/api/manager/timeoff/refuse', type='http', auth='public', methods=['POST'], csrf=False)
    def refuse_timeoff_request(self, **kwargs):
        """Refuse a time-off request. Runs as the current user."""
        try:
            try:
                payload = json.loads(request.httprequest.data.decode() or "{}")
            except Exception:
                return invalid_response("bad_json", _t("bad_json"), 400)
            request_id = payload.get("request_id")
            if not request_id:
                return invalid_response("missing_fields", _t("missing_fields"), 400)

            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids() or [int(self._current_company_id() or 0)]
            leave, _company_id = self._load_manager_leave(request_id, allowed_company_ids)
            if not leave:
                return invalid_response("not_found",
                                        _t("request_not_found_or_not_validator"), 404)

            if leave.state == 'refuse':
                return invalid_response("already_refused", _t("already_refused"), 400)

            try:
                leave.with_user(user.id).action_refuse()
            except UserError as ue:
                return invalid_response("user_error", str(ue), 400)
            except AccessError as ae:
                return invalid_response("access_error", str(ae), 403)

            leave.invalidate_recordset()
            return valid_response({
                "message": _t("refuse_success"),
                "request_id": leave.id,
                "state": leave.state,
                "state_display": dict(leave._fields['state'].selection).get(leave.state, leave.state),
            })
        except Exception as e:
            _logger.exception("refuse_timeoff_request failed")
            return invalid_response("server_error", str(e), 500)

    @validate_token
    @http.route('/api/manager/timeoff/validate', type='http', auth='public', methods=['POST'], csrf=False)
    def validate_timeoff_request(self, **kwargs):
        """Final-stage validation for multi-level approvals. Runs as the current user."""
        try:
            try:
                payload = json.loads(request.httprequest.data.decode() or "{}")
            except Exception:
                return invalid_response("bad_json", _t("bad_json"), 400)
            request_id = payload.get("request_id")
            if not request_id:
                return invalid_response("missing_fields", _t("missing_fields"), 400)

            user = self._current_user()
            allowed_company_ids = self._allowed_company_ids() or [int(self._current_company_id() or 0)]
            leave, _company_id = self._load_manager_leave(request_id, allowed_company_ids)
            if not leave:
                return invalid_response("not_found",
                                        _t("request_not_found_or_not_validator"), 404)

            if self._user_has_approved(leave, user.id):
                return invalid_response("already_validated", _t("already_validated"), 400)

            try:
                leave_as_user = leave.with_user(user.id)
                if leave.state == 'confirm':
                    leave_as_user.action_approve()
                elif leave.state == 'validate1':
                    leave_as_user.action_validate()
                else:
                    return invalid_response("bad_state",
                                            f"{_t('bad_state_validate')} ({leave.state})", 400)
            except UserError as ue:
                return invalid_response("user_error", str(ue), 400)
            except AccessError as ae:
                return invalid_response("access_error", str(ae), 403)

            leave.invalidate_recordset()
            approved_count = sum(1 for vs in leave.validation_status_ids if vs.validation_status)
            total_count = len(leave.validation_status_ids)
            fully_approved = (leave.state == 'validate')
            if fully_approved:
                msg = _t("fully_validated")
            elif total_count > 1 and approved_count < total_count:
                msg = _t("partial_validation", n=total_count - approved_count)
            else:
                msg = _t("validate_success")

            return valid_response({
                "message": msg,
                "request_id": leave.id,
                "state": leave.state,
                "state_display": dict(leave._fields['state'].selection).get(leave.state, leave.state),
                "fully_approved": fully_approved,
                "validators_approved": approved_count,
                "validators_total": total_count,
            })
        except Exception as e:
            _logger.exception("validate_timeoff_request failed")
            return invalid_response("server_error", str(e), 500)



    ##########################Developed by Mohamed Adel#####################################

    @validate_token
    @http.route('/api/attendance/edit_attendance', type='http', auth='none', methods=['POST'], csrf=False)
    def create_attendance_edit_request(self):
        try:
            raw_data = request.httprequest.data.decode('utf-8').strip()
            data = json.loads(raw_data) if raw_data else {}

            attendance_id = data.get('attendance_id')
            if not attendance_id:
                return Response(
                    json.dumps({"success": False, "error": "Missing required field: attendance_id."}),
                    status=400,
                    content_type='application/json'
                )

            company_id = self._current_company_id()
            employee = self._get_employee_for_user_in_company(request.env.user, company_id)
            if not employee:
                return invalid_response("no_employee", _t("no_employee"), 404)

            envc = self._force_company_env()

            attendance = envc['hr.attendance'].sudo().browse(int(attendance_id))
            if not attendance.exists():
                return Response(
                    json.dumps({"success": False, "error": "Attendance not found."}),
                    status=404,
                    content_type='application/json'
                )

            if attendance.employee_id.id != employee.id:
                return Response(
                    json.dumps({"success": False, "error": "Attendance not found or not yours."}),
                    status=404,
                    content_type='application/json'
                )

            if attendance.employee_id.company_id.id != int(company_id):
                return Response(
                    json.dumps({"success": False, "error": "Attendance is not in your selected company."}),
                    status=403,
                    content_type='application/json'
                )

            vals = {
                'employee_id': employee.id,
                'attendance_id': attendance.id,
            }

            edit_request = envc['hr.attendance.edit.request'].sudo().create(vals)

            return Response(
                json.dumps({
                    "success": True,
                    "message": "Attendance edit request created successfully (pending manager update).",
                    "request_id": edit_request.id,
                    "attendance_id": attendance.id,
                    "status": edit_request.state
                }),
                status=201,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error creating edit request: {str(e)}", exc_info=True)
            return Response(
                json.dumps({"success": False, "error": "Internal server error."}),
                status=500,
                content_type='application/json'
            )

    @validate_token
    @http.route('/api/attendance/get_requests', type='http', auth='none', methods=['GET'], csrf=False)
    def get_employee_edit_requests(self):
        try:
            user = request.env.user

            selected_company_ids = self._allowed_company_ids()
            if not selected_company_ids:
                return invalid_response("no_companies", _t("no_companies"), 400)

            result = []

            for company_id in [int(x) for x in selected_company_ids if x]:
                envc = self._force_company_env(company_id=company_id, allowed_company_ids=selected_company_ids)

                employee = self._get_employee_for_user_in_company(user, company_id)
                if not employee:
                    continue

                domain = [
                    ('employee_id', '=', employee.id),
                    ('employee_id.company_id', '=', company_id),
                ]

                edit_requests = envc['hr.attendance.edit.request'].sudo().search(domain, order="create_date desc")

                for req in edit_requests:
                    att = req.attendance_id
                    result.append({
                        "id": req.id,
                        "company_id": company_id,
                        "company_name": employee.company_id.name if employee.company_id else "",
                        "employee_id": employee.id,
                        "attendance_id": att.id if att else None,
                        "check_in_old": str(att.check_in) if att and att.check_in else None,
                        "check_out_old": str(att.check_out) if att and att.check_out else None,
                        "check_in_new": str(req.check_in_new) if req.check_in_new else None,
                        "check_out_new": str(req.check_out_new) if req.check_out_new else None,
                        "state": req.state or "",
                        "created_on": str(req.create_date) if req.create_date else None,
                    })

            result.sort(key=lambda x: x.get("created_on") or "", reverse=True)

            return Response(
                json.dumps({
                    "success": True,
                    "count": len(result),
                    "requests": result,
                    "meta": {
                        "selected_company_ids": selected_company_ids,
                        "current_company_id": self._current_company_id(),
                    }
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error fetching attendance edit requests: {str(e)}", exc_info=True)
            return Response(
                json.dumps({"success": False, "error": "Internal server error.", "debug": str(e)}),
                status=500,
                content_type='application/json'
            )

    @validate_token
    @http.route('/api/attendance/get_all_requests', type='http', auth='none', methods=['GET'], csrf=False)
    def get_all_edit_requests(self, **kwargs):
        """
        Retrieves all attendance edit requests across allowed companies.
        Admin/System or HR Manager only.
        """
        try:
            user = request.env.user

            if not (user.has_group('base.group_system') or user.has_group('hr.group_hr_manager')):
                return Response(json.dumps({
                    "success": False,
                    "error": "Access denied. Only Admin or HR Manager can access this endpoint."
                }), status=403, content_type='application/json')

            envc = self._force_company_env()
            allowed_company_ids = envc.context.get("allowed_company_ids") or []

            page = int(kwargs.get("page", 1) or 1)
            limit = int(kwargs.get("limit", 50) or 50)
            offset = (page - 1) * limit

            Model = envc['hr.attendance.edit.request'].sudo()

            domain = []
            if allowed_company_ids:
                domain += [('employee_id.company_id', 'in', [int(x) for x in allowed_company_ids if x])]

            total_count = Model.search_count(domain)
            edit_requests = Model.search(domain, order="create_date desc", limit=limit, offset=offset)

            result = []
            for req in edit_requests:
                employee = req.employee_id
                attendance = req.attendance_id

                result.append({
                    "id": req.id,
                    "employee_id": employee.id if employee else None,
                    "employee_name": employee.name if employee else "",
                    "employee_company_id": employee.company_id.id if employee and employee.company_id else None,

                    "attendance_id": attendance.id if attendance else None,
                    "check_in_old": str(attendance.check_in) if attendance and attendance.check_in else None,
                    "check_out_old": str(attendance.check_out) if attendance and attendance.check_out else None,

                    "check_in_new": str(req.check_in_new) if req.check_in_new else None,
                    "check_out_new": str(req.check_out_new) if req.check_out_new else None,

                    "state": req.state or "",
                    "created_on": str(req.create_date) if req.create_date else None
                })

            total_pages = (total_count + limit - 1) // limit if limit else 1

            return Response(json.dumps({
                "success": True,
                "count": len(result),
                "requests": result,
                "meta": {
                    "pagination": {
                        "current_page": page,
                        "per_page": limit,
                        "total_items": total_count,
                        "total_pages": total_pages,
                        "has_next": page < total_pages,
                        "has_prev": page > 1
                    },
                    "allowed_company_ids": allowed_company_ids,
                    "current_company_id": envc.context.get("company_id") or envc.context.get("force_company"),
                }
            }), status=200, content_type='application/json')

        except Exception as e:
            _logger.exception("Error fetching all attendance edit requests")
            return Response(json.dumps({
                "success": False,
                "error": str(e),
            }), status=500, content_type='application/json')

    # @http.route('/api/attendance/approve_request', type='http', auth='user', methods=['POST'], csrf=False)
    # def approve_attendance_edit_request(self, **kwargs):
    #     """
    #        Approves a specific attendance edit request.
    #        This endpoint allows admin users to approve a submitted attendance edit request by its ID.
    #        Upon approval, the request status is updated accordingly.
    #        Access: Admin users only.
    #        Parameters:
    #            - request_id (int): The ID of the attendance edit request to approve (passed in POST data).
    #        Returns:
    #            JSON response indicating success or failure of the approval operation.
    #        Developed by Mohamed Adel, Odoo Developer.
    #        """
    #     try:
    #         user = request.env.user
    #
    #         if not user.has_group('base.group_system'):
    #             return json.dumps({
    #                 "success": False,
    #                 "error": "Access denied. You must be an admin."
    #             })
    #
    #         import json
    #         data = json.loads(request.httprequest.data.decode('utf-8'))
    #         request_id = data.get('request_id')
    #
    #         if not request_id:
    #             return json.dumps({
    #                 "success": False,
    #                 "error": "Missing request_id."
    #             })
    #
    #         edit_request = request.env['hr.attendance.edit.request'].browse(int(request_id))
    #         if not edit_request.exists():
    #             return json.dumps({
    #                 "success": False,
    #                 "error": "Edit request not found."
    #             })
    #
    #         edit_request.state = 'approved'
    #
    #         return json.dumps({
    #             "success": True,
    #             "message": "Request approved successfully."
    #         })
    #
    #     except Exception as e:
    #         _logger.error(f"Error in approve_attendance_edit_request: {str(e)}", exc_info=True)
    #         return json.dumps({
    #             "success": False,
    #             "error": "Internal server error."
    #         })
    @validate_token
    @http.route('/api/attendance/approve_request', type='http', auth='public', methods=['POST'], csrf=False)
    def approve_attendance_edit_request(self, **kwargs):
        try:
            user = request.env.user
            if not user.has_group('base.group_system'):
                return request.make_json_response(
                    {"success": False, "error": "Access denied. You must be an admin."},
                    status=403,
                )

            raw = (request.httprequest.data or b"").decode("utf-8", errors="ignore").strip()
            try:
                data = json.loads(raw or "{}")
            except Exception:
                return request.make_json_response(
                    {"success": False, "error": "Invalid JSON body."},
                    status=400,
                )

            request_id = data.get("request_id")
            if not request_id:
                return request.make_json_response(
                    {"success": False, "error": "Missing request_id."},
                    status=400,
                )

            EditReq = request.env["hr.attendance.edit.request"].sudo().with_context(tracking_disable=True)
            edit_request = EditReq.browse(int(request_id))
            if not edit_request.exists():
                return request.make_json_response(
                    {"success": False, "error": "Edit request not found."},
                    status=404,
                )

            if hasattr(edit_request, "attendance_id") and not edit_request.attendance_id:
                return request.make_json_response(
                    {"success": False, "error": "Edit request has no linked attendance."},
                    status=400,
                )

            if not request.env.user.employee_id:
                return request.make_json_response(
                    {"success": False, "error": "Admin user is not linked to an employee."},
                    status=400,
                )

            # ---------- Timezone parsing ----------
            user_tz_name = request.env.context.get("tz") or request.env.user.tz or "UTC"
            try:
                user_tz = pytz.timezone(user_tz_name)
            except Exception:
                user_tz = pytz.UTC

            def parse_any_dt_to_utc_naive(dt_str: str) -> datetime:
                s = (dt_str or "").strip()
                if not s:
                    raise ValueError("empty datetime")

                s = s.replace("T", " ")
                s = re.sub(r"\s+", " ", s)

                tzinfo = None
                if s.endswith("Z"):
                    tzinfo = pytz.UTC
                    s = s[:-1].strip()
                else:
                    m = re.search(r"([+-])(\d{2}):?(\d{2})$", s)
                    if m:
                        sign, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
                        offset_minutes = hh * 60 + mm
                        if sign == "-":
                            offset_minutes = -offset_minutes
                        tzinfo = pytz.FixedOffset(offset_minutes)
                        s = s[: m.start()].strip()

                if " " not in s:
                    raise ValueError("missing space between date and time")

                date_part, time_part = s.split(" ", 1)
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_part):
                    raise ValueError("invalid date part")

                m = re.match(r"^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?(?:\.(\d+))?$", time_part)
                if not m:
                    raise ValueError("invalid time part")

                hh = int(m.group(1))
                mi = int(m.group(2))
                ss = int(m.group(3) or 0)
                frac = m.group(4)

                micro = 0
                if frac:
                    frac = frac[:6].ljust(6, "0")
                    micro = int(frac)

                naive = datetime(
                    int(date_part[0:4]),
                    int(date_part[5:7]),
                    int(date_part[8:10]),
                    hh,
                    mi,
                    ss,
                    micro,
                )

                if tzinfo is not None:
                    aware = tzinfo.localize(naive) if hasattr(tzinfo, "localize") else naive.replace(tzinfo=tzinfo)
                    return aware.astimezone(pytz.UTC).replace(tzinfo=None)

                local = user_tz.localize(naive, is_dst=None)
                return local.astimezone(pytz.UTC).replace(tzinfo=None)

            vals = {}

            if data.get("check_in_new"):
                try:
                    vals["check_in_new"] = parse_any_dt_to_utc_naive(data["check_in_new"])
                except Exception as ex:
                    return request.make_json_response(
                        {
                            "success": False,
                            "error": f"Invalid check_in_new format: {data.get('check_in_new')} ({ex})",
                        },
                        status=400,
                    )

            if data.get("check_out_new"):
                try:
                    vals["check_out_new"] = parse_any_dt_to_utc_naive(data["check_out_new"])
                except Exception as ex:
                    return request.make_json_response(
                        {
                            "success": False,
                            "error": f"Invalid check_out_new format: {data.get('check_out_new')} ({ex})",
                        },
                        status=400,
                    )

            if vals:
                if vals.get("check_in_new") and vals.get("check_out_new") and vals["check_in_new"] >= vals[
                    "check_out_new"]:
                    return request.make_json_response(
                        {"success": False, "error": "\"Check In\" time cannot be >= \"Check Out\" time."},
                        status=400,
                    )

                safe_vals = {k: v for k, v in vals.items() if k in edit_request._fields}
                if safe_vals:
                    edit_request.write(safe_vals)

            methods_to_try = ["action_approve", "button_approve", "approve", "action_confirm", "action_done"]

            last_err = None
            done = False
            for mname in methods_to_try:
                if hasattr(edit_request, mname):
                    try:
                        getattr(edit_request, mname)()
                        done = True
                        break
                    except Exception as ex:
                        last_err = str(ex)

            if not done:
                if last_err:
                    return request.make_json_response(
                        {"success": False, "error": f"Approve failed: {last_err}"},
                        status=400,
                    )
                return request.make_json_response(
                    {"success": False, "error": "Approve method not found on edit request model."},
                    status=400,
                )

            return request.make_json_response(
                {"success": True, "message": "Request approved successfully."},
                status=200,
            )

        except Exception as e:
            _logger.error("Error in approve_attendance_edit_request: %s", str(e), exc_info=True)
            return request.make_json_response(
                {"success": False, "error": "Internal server error."},
                status=500,
            )

    @validate_token
    @http.route('/api/attendance/update', type='http', auth='none', methods=['POST'], csrf=False)
    def admin_update_attendance(self, **post):
        try:
            import pytz

            user = request.env.user

            if not (user.has_group('base.group_system') or user.has_group('hr.group_hr_manager')):
                return Response(json.dumps({"success": False, "error": "Access denied."}),
                                status=403, content_type='application/json')

            raw_data = request.httprequest.data.decode('utf-8').strip()
            if not raw_data:
                return Response(json.dumps({"success": False, "error": "Empty request body."}),
                                status=400, content_type='application/json')

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                return Response(json.dumps({"success": False, "error": "Invalid JSON format."}),
                                status=400, content_type='application/json')

            attendance_id = data.get('attendance_id')
            check_in = data.get('check_in')
            check_out = data.get('check_out')

            if not attendance_id:
                return Response(json.dumps({"success": False, "error": "Missing required field: attendance_id."}),
                                status=400, content_type='application/json')

            input_tz = (user.tz or "Asia/Riyadh").strip()
            tz = pytz.timezone(input_tz)

            att = request.env['hr.attendance'].sudo().browse(int(attendance_id))
            if not att.exists():
                return Response(json.dumps({"success": False, "error": "Attendance record not found."}),
                                status=404, content_type='application/json')

            att_company_id = None
            if "company_id" in att._fields and att.company_id:
                att_company_id = att.company_id.id
            elif att.employee_id and att.employee_id.company_id:
                att_company_id = att.employee_id.company_id.id

            envc = request.env
            if att_company_id:
                envc = self._force_company_env(att_company_id) if hasattr(self, "_force_company_env") \
                    else request.env.with_company(att_company_id)

            ctx = dict(getattr(envc, "context", {}) or {})
            ctx["tz"] = input_tz
            envc = envc(context=ctx)

            attendance = envc['hr.attendance'].sudo().browse(int(attendance_id))
            if not attendance.exists():
                return Response(
                    json.dumps({"success": False, "error": "Attendance record not found in company context."}),
                    status=404,
                    content_type='application/json'
                )

            def local_str_to_utc_naive(dt_str):
                if not dt_str:
                    return None
                dt_local_naive = fields.Datetime.to_datetime(dt_str)
                dt_local = tz.localize(dt_local_naive)
                return dt_local.astimezone(pytz.UTC).replace(tzinfo=None)

            def utc_naive_to_local_str(dt_utc_naive):
                if not dt_utc_naive:
                    return None
                dt_utc_aware = pytz.UTC.localize(dt_utc_naive)
                dt_local = dt_utc_aware.astimezone(tz)
                return dt_local.strftime("%Y-%m-%d %H:%M:%S")

            try:
                dt_in = local_str_to_utc_naive(check_in) if check_in is not None and str(check_in).strip() else None
                dt_out = local_str_to_utc_naive(check_out) if check_out is not None and str(check_out).strip() else None
            except Exception as e:
                return Response(json.dumps({"success": False, "error": f"Invalid datetime format: {str(e)}"}),
                                status=400, content_type='application/json')

            if dt_in and dt_out and dt_out < dt_in:
                return Response(json.dumps({"success": False, "error": "check_out must be >= check_in."}),
                                status=400, content_type='application/json')

            update_vals = {}

            if check_in is not None:
                if str(check_in).strip() != "":
                    update_vals['check_in'] = dt_in
            if check_out is not None:
                if str(check_out).strip() != "":
                    update_vals['check_out'] = dt_out

            if not update_vals:
                return Response(json.dumps({"success": False, "error": "No fields to update."}),
                                status=400, content_type='application/json')

            update_vals['x_api_updated'] = True

            attendance.sudo().write(update_vals)

            return Response(
                json.dumps({
                    "success": True,
                    "message": "Attendance updated successfully.",
                    "attendance_id": attendance.id,
                    "employee_id": attendance.employee_id.id if attendance.employee_id else None,
                    "check_in": utc_naive_to_local_str(attendance.check_in),
                    "check_out": utc_naive_to_local_str(attendance.check_out) if attendance.check_out else None,
                    "has_request": True,
                }, default=str),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error("Error in admin_update_attendance:", exc_info=True)
            return Response(json.dumps({"success": False, "error": "Internal server error.", "debug": str(e)}),
                            status=500, content_type='application/json')