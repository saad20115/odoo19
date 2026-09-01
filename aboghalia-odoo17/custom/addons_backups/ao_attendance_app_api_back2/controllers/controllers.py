# -*- coding: utf-8 -*-
import os
import json
import logging
import functools
import werkzeug.wrappers
import pytz
import base64
from datetime import datetime
import calendar
from odoo import fields, http
from odoo.http import request, Response
from odoo.exceptions import AccessDenied, AccessError, ValidationError, UserError
from dotenv import load_dotenv
from odoo.modules.module import get_module_resource
from bs4 import BeautifulSoup
# from odoo.custom_addons.ao_attendance_app_api.models.common import invalid_response, valid_response


env_file = get_module_resource('ao_attendance_app_api', 'config', '.env')
load_dotenv(dotenv_path=env_file)
HOST = os.getenv('HOST')
_logger = logging.getLogger(__name__)

def default(o):
    if isinstance(o, (datetime.date, datetime)):
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

def validate_token(func):
    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        access_token = request.httprequest.headers.get("access-token")
        if not access_token:
            return invalid_response("access_token_not_found", "missing access token in request header", 401)
        access_token_data = request.env["api.access_token"].sudo().search(
            [("token", "=", access_token)],
            order="id DESC",
            limit=1
        )

        if access_token_data.find_or_create_token(user_id=access_token_data.user_id.id) != access_token:
            return invalid_response("access_token", "token seems to have expired or invalid", 401)

        request.session.uid = access_token_data.user_id.id
        request.env.uid = access_token_data.user_id.id
        return func(self, *args, **kwargs)

    return wrap


class AppLogin(http.Controller):

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


        #Check Timeoff Access
        has_timeoff_access = request.env.user.has_group('hr_holidays.group_hr_holidays_user') or \
                           request.env.user.has_group('hr_holidays.group_hr_holidays_manager')
        has_attendance_access = request.env.user.has_group('hr_attendance.group_hr_attendance_manager')

        # Successful response:
        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps(
                {
                    "uid": uid,
                    "company_id": request.env.user.company_id.id if uid else None,
                    "company_ids": request.env.user.company_ids.ids if uid else None,
                    "partner_id": request.env.user.partner_id.id,
                    "access_token": access_token,
                    "company_name": request.env.user.company_name,
                    "country": request.env.user.country_id.name,
                    "contact_address": request.env.user.contact_address,
                    "access": {
                        "attendance": "manager" if has_attendance_access else "user",
                        "expenses": "user",
                         "payroll":"user",
                         "timeoff": "manager" if has_timeoff_access else "user",
                         "skip_biometric": request.env.user.employee_id.skip_biometric or False
                    },
                }
            )
        )

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
            employee = user_obj.sudo().employee_id

            payload = request.httprequest.data.decode()
            payload = json.loads(payload)

            longitude = payload.get("longitude")
            latitude = payload.get("latitude")
            ip_address = payload.get("ip_address")
            uuid = payload.get("uuid")
            action_date = fields.Datetime.now()

            with request.env.cr.savepoint():
                if employee.sudo().last_attendance_id and not employee.sudo().last_attendance_id.check_out:
                    # Check out
                    att = employee.sudo().last_attendance_id
                    att.write({
                        'check_out': action_date,
                        'out_longitude': longitude,
                        'out_latitude': latitude,
                        'out_ip_address': ip_address,
                        'out_mode': 'systray'
                    })

                    uuid_record = request.env['uuid.model'].sudo().check_and_update_uuid(uuid, employee.sudo().id)
                    return valid_response([{
                        "attendance_state": "checked out",
                        "message": "Checked out successfully",
                        "uuid": uuid_record["message"]
                    }], status=200)
                else:
                    temp_att = request.env['hr.attendance'].new({
                        'employee_id': employee.sudo().id,
                        'check_in': action_date
                    })
                    temp_att._check_checkin_time_limit()

                    # Check in
                    new_att = request.env['hr.attendance'].with_user(user_obj).create({
                        'employee_id': employee.sudo().id,
                        'check_in': action_date,
                        'in_longitude': longitude,
                        'in_latitude': latitude,
                        'in_ip_address': ip_address,
                        'in_mode': 'systray'
                    })

                    employee.sudo().write({'last_attendance_id': new_att.id})
                    uuid_record = request.env['uuid.model'].sudo().check_and_update_uuid(uuid, employee.sudo().id)

                    return valid_response([{
                        "attendance_state": "checked in",
                        "message": "Checked in successfully",
                        "uuid": uuid_record["message"]
                    }], status=200)

        except ValidationError as ve:
            return invalid_response("validation_error", str(ve), 400)
        except Exception as e:
            _logger.error(f"Check-in/out error: {str(e)}")
            return invalid_response("error", str(e), 400)

    @validate_token
    @http.route("/api/user/attendance-state", methods=["GET"], type="http", auth="none", csrf=False)
    def get_attendance_state(self, **kwargs):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
    
        if employee.last_attendance_id:
            try:
                if employee.last_attendance_id.check_out:
                    return werkzeug.wrappers.Response(
                        status=200,
                        content_type="application/json; charset=utf-8",
                        headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                        response=json.dumps({"attendance_state": "checked_out"}),
                    )
                else:
                    return werkzeug.wrappers.Response(
                        status=200,
                        content_type="application/json; charset=utf-8",
                        headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                        response=json.dumps({"attendance_state": "checked_in"}),
                    )
            except Exception as e:
                return invalid_response("error", str(e), 400)
        else:
            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"attendance_state": "checked_out"}),
            )

    @validate_token
    @http.route("/api/user/total-hours", methods=["GET"], type="http", auth="none", csrf=False)
    def get_total_hours(self, **kwargs):
        try:
            user = request.env['res.users'].sudo().browse(request.uid)
            employee = user.sudo().employee_id

            if not employee:
                return valid_response([{"error": "No employee associated with this user"}], status=400)

            today = fields.Date.today()
            attendances = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.sudo().id),
                ('check_in', '>=', today),
                ('check_in', '<', fields.Date.add(today, days=1)),
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
            employee = user.sudo().employee_id 
            
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
            last_day_of_month = today.replace(day=calendar.monthrange(today.year, today.month)[1], hour=23, minute=59, second=59, microsecond=999999)

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
                    "company_name": user_obj.employee_id.company_id.name,
                    "department": user_obj.employee_id.department_id.name,
                    "job_title": user_obj.employee_id.job_id.name
                }
            ),
        )

    @validate_token
    @http.route("/api/user/today-att", methods=["GET"], type="http", auth="none", csrf=False)
    def get_user_info2(self, **post):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
        response = []
        
        # Use Asia/Riyadh timezone
        user_timezone = 'Asia/Riyadh'
        
        # Get current date in Asia/Riyadh timezone
        current_dt_riyadh = self.get_user_timezone_now(user_timezone)
        today_riyadh = current_dt_riyadh.date()
        
        # Get day boundaries in UTC for database query
        start_utc, end_utc = self.get_day_boundaries_utc(today_riyadh, user_timezone)
        
        # Create domain with proper UTC boundaries
        domain = [
            ('check_in', '>=', start_utc),
            ('check_in', '<', end_utc),
            ('employee_id', '=', employee.sudo().id)
        ]
        
        attendances = request.env['hr.attendance'].sudo().search(domain, order='check_in desc')
        
        for attendance in attendances:
            # Convert check_in and check_out to Asia/Riyadh timezone
            check_in_riyadh = self.convert_to_user_timezone(attendance.check_in, user_timezone)
            check_out_riyadh = self.convert_to_user_timezone(attendance.check_out, user_timezone) if attendance.check_out else None
            
            user_check_in = check_in_riyadh.strftime('%I:%M %p') if check_in_riyadh else None
            user_check_out = check_out_riyadh.strftime('%I:%M %p') if check_out_riyadh else None
            
            edit_request_count = request.env['hr.attendance.edit.request'].search_count([
                ('attendance_id', '=', attendance.id)
            ])
            has_request = False
            if edit_request_count > 0:
                has_request = True


            response.append({
                'id': attendance.id,
                'check_in': user_check_in,
                'check_out': user_check_out,
                'worked_hours': self.convert_float_to_hours_and_minutes(attendance.worked_hours),
                'in_longitude': attendance.in_longitude,
                'in_latitude': attendance.in_latitude,
                'out_longitude': attendance.out_longitude,
                'out_latitude': attendance.out_latitude,
                'has_request': has_request
            })
        
        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps(response),
        )

    @validate_token
    @http.route("/api/user/month-att", methods=["GET"], type="http", auth="none", csrf=False)
    def get_user_info3(self, **post):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
        response = []
        
        # Use Asia/Riyadh timezone
        user_timezone = 'Asia/Riyadh'
        
        # Get current date in Asia/Riyadh timezone
        current_dt_riyadh = self.get_user_timezone_now(user_timezone)
        current_month = current_dt_riyadh.month
        current_year = current_dt_riyadh.year
        
        # Get month boundaries in UTC for database query
        start_utc, end_utc = self.get_month_boundaries_utc(current_year, current_month, user_timezone)
        
        # Create domain with proper UTC boundaries
        domain = [
            ('employee_id', '=', employee.sudo().id),
            ('check_in', '>=', start_utc),
            ('check_in', '<', end_utc)
        ]
        
        attendances = request.env['hr.attendance'].search(domain, order='check_in desc')
        
        for attendance in attendances:
            # Convert check_in and check_out to Asia/Riyadh timezone
            check_in_riyadh = self.convert_to_user_timezone(attendance.check_in, user_timezone)
            check_out_riyadh = self.convert_to_user_timezone(attendance.check_out, user_timezone) if attendance.check_out else None
            
            user_check_in = check_in_riyadh.strftime('%I:%M %p') if check_in_riyadh else None
            user_check_out = check_out_riyadh.strftime('%I:%M %p') if check_out_riyadh else None
            
            # Format date in Asia/Riyadh timezone
            day_date = check_in_riyadh.strftime('%d %B %Y') if check_in_riyadh else None
            
            response.append({
                'date': day_date,
                'check_in': user_check_in,
                'check_out': user_check_out,
                'worked_hours': self.convert_float_to_hours_and_minutes(attendance.worked_hours),
                'in_longitude': attendance.in_longitude,
                'in_latitude': attendance.in_latitude,
                'out_longitude': attendance.out_longitude,
                'out_latitude': attendance.out_latitude,
            })
        
        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps(response),
        )


class ExpensesController(http.Controller):

    @validate_token
    @http.route('/api/employee/expenses', type='http', auth='public', methods=['POST'], csrf=False)
    def create_expense(self, **kwargs):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
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
                # expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    json.dumps({'success': False, 'error': 'Invalid data format'}),
                    content_type='application/json',
                    status=400
                )

            product = request.env['product.product'].sudo().search([('id', '=', product_id)], limit=1)
            if not product:
                return Response(
                    json.dumps({'success': False, 'error': f'Product with ID {product_id} not found'}),
                    content_type='application/json',
                    status=404
                )

            currency = request.env.company.currency_id or request.env['res.currency'].sudo().search([], limit=1)
            if not currency:
                return Response(
                    json.dumps({'success': False, 'error': 'No valid currency found'}),
                    content_type='application/json',
                    status=400
                )

            expense = request.env['hr.expense'].sudo().create({
                'name': description,
                'product_id': product.id,
                'total_amount_currency': total_amount,
                'employee_id': employee.sudo().id,
                'currency_id': currency.id,
                # 'date': expense_date
                'date': fields.Date.today(),
                'x_request_type': request_type_id
            })

            #Handle file attachment
            # attachment_id = None
            if uploaded_files:
                files = uploaded_files.to_dict(flat=False)
                for file in files["file"]:
                    file_content = file.read()
                    file_name = file.filename
                    file_data = base64.b64encode(file_content)  # Convert file to base64

                    attachment = request.env['ir.attachment'].sudo().create({
                        'name': file_name,
                        'type': 'binary',
                        'datas': file_data,
                        'res_model': 'hr.expense',
                        'res_id': expense.id,
                    })
                    # attachment_id = attachment.id

            return Response(
                json.dumps({
                'success': True,
                'record_id': expense.id,
                # 'date': str(expense_date),
                # 'attachment_id': attachment_id
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
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
        expenses = request.env['hr.expense'].sudo().search(
            [('employee_id', '=', employee.sudo().id), ('state', '=', "draft")]
        )
        new_expenses = request.env['hr.expense'].sudo().search_count(
            [('employee_id', '=', employee.sudo().id), ('state', '=', "draft")]
        )
        new_expenses_count = new_expenses

        expense_list = [
            {
                "id": expense.id,
                "name": expense.name,
                "date": expense.date.strftime('%Y-%m-%d') if expense.date else "",
                "total_amount": expense.total_amount
            }
            for expense in sorted(expenses, key=lambda c: c.id)
        ]

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps({"results": new_expenses_count, "data": expense_list}),
        )

    @validate_token
    @http.route("/api/employee/expenses/pending", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_pending_expenses(self, **post):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
        expenses = request.env['hr.expense'].sudo().search(
            [('employee_id', '=', employee.sudo().id), ('state', '=', ["reported", "submitted"])]
        )
        pending_expenses = request.env['hr.expense'].sudo().search_count(
            [('employee_id', '=', employee.sudo().id), ('state', '=', ["reported", "submitted"])]
        )
        pending_expenses_count = pending_expenses
        expense_list = [
            {
                "id": expense.id,
                "name": expense.name,
                "date": expense.date.strftime('%Y-%m-%d') if expense.date else "",
                "total_amount": expense.total_amount
            }
            for expense in sorted(expenses, key=lambda c: c.id)
        ]

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps({"results": pending_expenses_count, "data": expense_list}),
        )

    @validate_token
    @http.route("/api/employee/expenses/done", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_done_expenses(self, **post):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
        done_expenses = request.env['hr.expense'].sudo().search(
            [('employee_id', '=', employee.sudo().id),('state', '=', ["approved", "done"])]
        )
        done_expenses_count = request.env['hr.expense'].sudo().search_count(
            [('employee_id', '=', employee.sudo().id), ('state', '=', ["approved", "done"])]
        )
        rejected_expenses = request.env['hr.expense'].sudo().search(
            [('employee_id', '=', employee.sudo().id), ('state', '=', "refused")]
        )
        refused_expenses_count = request.env['hr.expense'].sudo().search_count(
            [('employee_id', '=', employee.sudo().id), ('state', '=', "refused")]
        )
        rejected_expenses_list = [
            {
                "id": expense.id,
                "name": expense.name,
                "date": expense.date.strftime('%Y-%m-%d') if expense.date else "",
                "state": expense.state,
                "total_amount": expense.total_amount,
                "reject_reason": expense.sheet_id.reject_reason
            }
            for expense in sorted(rejected_expenses, key=lambda c: c.date)
        ]

        done_expenses_list = [
            {
                "id": expense.id,
                "name": expense.name,
                "date": expense.date.strftime('%Y-%m-%d') if expense.date else "",
                "state": expense.state,
                "total_amount": expense.total_amount
            }
            for expense in sorted(done_expenses, key=lambda c: c.date)
        ]

        joined = rejected_expenses_list + done_expenses_list
        joined.sort(key=lambda el: datetime.strptime(el['date'], '%Y-%m-%d'))

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps({
                "results": done_expenses_count + refused_expenses_count,
                "data": joined
            })
        )

    @validate_token
    @http.route("/api/employee/expenses/reviewed/card", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_expenses_reviewed_count(self, **post):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
        reviewed_expenses = request.env['hr.expense'].sudo().search([
            ('employee_id', '=', employee.sudo().id),
            ('state', '=', 'draft')
        ])

        # Sum the total_amount
        total_reviewed_amount = sum(reviewed_expenses.mapped('total_amount'))
        reviewed_expense_card = total_reviewed_amount

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps({"reviewed_expense_card": reviewed_expense_card}),
        )

    @validate_token
    @http.route("/api/employee/expenses/approved/card", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_expenses_approved_count(self, **post):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
        approved_expenses = request.env['hr.expense'].sudo().search(
            [('employee_id', '=', employee.sudo().id), ('state', '=', 'approved')])
        total_reviewed_amount = sum(approved_expenses.mapped('total_amount'))
        approved_expense_card = total_reviewed_amount

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps({"approved_expense_card": approved_expense_card}),
        )

    @validate_token
    @http.route("/api/employee/expenses/total/card", methods=["GET"], type="http", auth="none", csrf=False)
    def get_employee_expenses_total_count(self, **post):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
        Expense = request.env['hr.expense'].sudo()

        # Fetch expenses by state
        draft_expenses = Expense.sudo().search([
            ('employee_id', '=', employee.sudo().id),
            ('state', '=', 'draft')
        ])
        approved_expenses = Expense.sudo().search([
            ('employee_id', '=', employee.sudo().id),
            ('state', '=', 'approved')
        ])

        # Use mapped to sum total_amounts
        total_draft = sum(draft_expenses.mapped('total_amount'))
        total_approved = sum(approved_expenses.mapped('total_amount'))
        total_all = total_draft + total_approved

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps({"total_expense_card": total_all}),
        )

    @validate_token
    @http.route("/api/expenses/categories", methods=["GET"], type="http", auth="none", csrf=False)
    def get_category_expenses(self, **post):
        # user_id = request.uid
        # user_obj = request.env['res.users'].browse(user_id)
        categories = request.env['product.product'].sudo().search([('can_be_expensed', '=', True)])
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
    def get_request_types(self, **post):
        # user_id = request.uid
        # user_obj = request.env['res.users'].browse(user_id)
        request_types = request.env['ao.request.samir'].sudo().search([])
        request_types_list = {
            request_type.id: request_type.name for request_type in sorted(request_types, key=lambda r: r.id)
        }

        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps({"request_types": request_types_list}),
        )

    @validate_token
    @http.route('/api/employee/expenses/expense-details', type='http', auth='public', methods=['GET'], csrf=False)
    def get_expense_details(self, **kwargs):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
        expense_id = kwargs.get("expense_id")

        try:
            record = request.env['hr.expense'].sudo().search(
                [('employee_id', '=', employee.sudo().id), ('id', '=', expense_id)],
                limit=1
            )
            # print("////////// record")
            # print(record.message_main_attachment_id.datas)

            if not record:
                return request.make_json_response(({
                    "status": "error",
                    "message": "Record not found!"
                }), status=404)

            messages = []
            for message in record.message_ids:
                if message.message_type != "notification":
                    html_content = message.body
                    soup = BeautifulSoup(html_content, 'html.parser')
                    text = soup.get_text(separator=' ', strip=True)
                    messages.append(text)

            # attachments = request.env['ir.attachment'].sudo().search([('res_id', '=', expense_id)])
            # sent_attachments = []
            # if attachments:
            #     for attachment in attachments:
            #         sent_attachments.append(f'{HOST}/web/content/{attachment.id}')
            attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'hr.expense'),
            ('res_id', '=', expense_id)
            ])

            sent_attachments = []

            for attachment in attachments:
                sent_attachments.append({
                    'name': attachment.name,
                    'mimetype': attachment.mimetype,
                    'base64': attachment.datas.decode() if attachment.datas else '',  # already base64 in Odoo
                    # optional: include file extension
                    'extension': attachment.name.split('.')[-1] if '.' in attachment.name else '',
                })
                    # filecontent = base64.b64decode(attachment.datas)
                    # print("////////// filecontent")
                    # print(filecontent)

            vals = {
                "id": record.id,
                "description": record.name or '',
                "category_id": record.product_id.id or -1,
                "category_name": record.product_id.name or '',
                "request_type_id": record.x_request_type.id or -1,
                "request_type_name": record.x_request_type.name or '',
                "state": record.state or '',
                "reject_reason": record.sheet_id.reject_reason if record.sheet_id.reject_reason else '',
                "date": record.date.isoformat(),
                "total_amount": record.total_amount_currency,
                "attachments": sent_attachments,
                "messages": messages
            }

            return werkzeug.wrappers.Response(
                status=200,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({ "data": vals }),
            )
        except Exception as e:
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
        employee = user_obj.employee_id
        expense_id = kwargs.get("expense_id")
        product_id = kwargs.get('category_id')
        description = kwargs.get('description')
        total_amount = kwargs.get('total_amount')
        request_type_id = kwargs.get('request_type_id')
        uploaded_files = request.httprequest.files

        try:
            record = request.env['hr.expense'].sudo().search(
                [('employee_id', '=', employee.sudo().id), ('id', '=', expense_id)],
                limit=1
            )

            if not record:
                return request.make_json_response(({
                    "status": "error",
                    "message": "Record not found!"
                }), status=404)

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
                    # expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    json.dumps({'success': False, 'error': 'Invalid data format'}),
                    content_type='application/json',
                    status=400
                )

            product = request.env['product.product'].sudo().search([('id', '=', product_id)], limit=1)
            if not product:
                return Response(
                 json.dumps({'success': False, 'error': f'Product with ID {product_id} not found'}),
                    content_type='application/json',
                    status=404
                )

            currency = request.env.company.currency_id or request.env['res.currency'].sudo().search([], limit=1)
            if not currency:
                return Response(
                    json.dumps({'success': False, 'error': 'No valid currency found'}),
                    content_type='application/json',
                    status=400
                )
            request_type = request.env['ao.request.samir'].sudo().search([('id', '=', int(request_type_id) )], limit=1)
            if not request_type:
                return Response(
                    json.dumps({'success': False, 'error': 'No valid request type found'}),
                    content_type='application/json',
                    status=400
                )

            record.sudo().write({
                'name': description,
                'product_id': product.id,
                'total_amount_currency': total_amount,
                'employee_id': employee.sudo().id,
                'currency_id': currency.id,
                # 'date': expense_date
                'date': fields.Date.today(),
                'x_request_type': request_type.id
            })

            # Handle file attachment
            # attachment_id = None
            if uploaded_files:
                files = uploaded_files.to_dict(flat=False)
                for file in files["file"]:
                    file_content = file.read()
                    file_name = file.filename
                    file_data = base64.b64encode(file_content)  # Convert file to base64

                    attachment = request.env['ir.attachment'].sudo().create({
                        'name': file_name,
                        'type': 'binary',
                        'datas': file_data,
                        'res_model': 'hr.expense',
                        'res_id': record.id,
                    })
                    # attachment_id = attachment.id

            return Response(
                json.dumps({
                    'success': True,
                    'record_id': record.id,
                    # 'date': str(expense_date),
                    # 'attachment_id': attachment_id
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


class FaceRecognitionController(http.Controller):

    @validate_token
    @http.route('/api/employee/test', type='http', auth='none', methods=['POST'], csrf=False)
    def test(self, **kwargs):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id
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
            employee = user_obj.employee_id
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
            employee_id = user_obj.employee_id
            if not employee_id:
                return json.dumps({'success': False, 'error': 'employee ID is required'})

            employee = request.env['hr.employee'].sudo().search([('id', '=', employee_id.id)], limit=1)
            if not employee:
                return json.dumps({'success': False, 'error': f'employee with ID {employee_id} not found'})

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


class PayrollController(http.Controller):

    @validate_token
    @http.route('/api/employee/payslip', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_details(self, **kwargs):
        try:
            payslip_id = kwargs.get("payslip_id")
            payslip = request.env['hr.payslip'].sudo().browse(int(payslip_id))

            if not payslip.exists():
                return valid_response({"error": f'Payslip with ID {payslip_id} not found.'}, status=500)


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

            return request.make_json_response(({
                "status": "success",
                "data": {
                'status': 'success',
                'period': f"{payslip.date_from.strftime('%d %b')} to {payslip.date_to.strftime('%d %b')}",
                'lines': lines_data,
                'net_salary': payslip.line_ids.filtered(lambda l: l.code == 'NET').total,
                'state': payslip.state
            }
            }), status=200)

        except Exception as e:
            return valid_response({"error": str(e)}, status=500)
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
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            employee = user_obj.employee_id
            if not employee.exists():
                return {
                    'status': 'error',
                    'message': f'Employee not found.'
                }

            payslips = request.env['hr.payslip'].sudo().search([
                ('employee_id', '=', employee.sudo().id)
            ], order='date_from asc')

            payslip_data = []
            for slip in payslips:
                month_name = slip.date_from.strftime('%B %Y')  # e.g., "May 2025"
                period = f"{slip.date_from.strftime('%d %b')} to {slip.date_to.strftime('%d %b')}"
                net_salary = slip.line_ids.filtered(lambda l: l.code == 'NET').total

                payslip_data.append({
                    'payslip_id': slip.id,
                    'month': month_name,
                    'period': period,
                    'net_salary': net_salary,
                    'status': slip.state,
                })

            return valid_response(payslip_data)

        except Exception as e:
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

class TimeoffController(http.Controller):

    @validate_token
    @http.route('/api/employee/timeoff/create', type='http', auth='public', methods=['POST'], csrf=False)
    def create_timeoff_request(self, **kwargs):
        """Create a new time-off request"""
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            payload = request.httprequest.data.decode()
            payload = json.loads(payload)
            holiday_status_id = payload.get("holiday_status_id")  # Time-off type ID
            request_date_from = payload.get("request_date_from")
            request_date_to = payload.get("request_date_to")
            name = payload.get("name", "Time Off Request")  # Description
            number_of_days = payload.get("number_of_days")
            request_unit_half = payload.get("request_unit_half")
            request_date_from_period = payload.get("request_date_from_period")
            


            if not employee:
                return valid_response({"error": "No employee associated with this ID"}, status=404)
            required_fields = [holiday_status_id, request_date_from, request_date_to]
            if request_unit_half == True:
                required_fields.append(request_date_from_period)
            if not all(required_fields):
                return valid_response({"error": "Missing required parameters"}, status=400)


            # Convert string dates to date objects
            date_from = datetime.strptime(request_date_from, '%Y-%m-%d').date()
            date_to = datetime.strptime(request_date_to, '%Y-%m-%d').date()

            # Create time-off request
            vals = {
                'name': name,
                'employee_id': int(employee_id),
                'holiday_status_id': int(holiday_status_id),
                'request_date_from': date_from,
                'request_date_to': date_to,
                'state': 'confirm',  # Set to confirm state (pending approval)
                'request_unit_half': request_unit_half or False,
                'request_date_from_period': request_date_from_period or ''
            }
            
            if number_of_days:
                vals['number_of_days'] = float(number_of_days)

            
            timeoff_request = request.env['hr.leave'].sudo().create(vals)
            
            response_data = {
                "id": timeoff_request.id,
                "name": timeoff_request.name,
                "employee_name": timeoff_request.employee_id.name,
                "holiday_type": timeoff_request.holiday_status_id.name,
                "request_date_from": timeoff_request.request_date_from.strftime('%Y-%m-%d'),
                "request_date_to": timeoff_request.request_date_to.strftime('%Y-%m-%d'),
                "number_of_days": timeoff_request.number_of_days,
                "state": timeoff_request.state,
                "state_display": dict(timeoff_request._fields['state'].selection)[timeoff_request.state]
            }
            
            return valid_response(response_data, status=201)
            
        except ValidationError as e:
            return werkzeug.wrappers.Response(
                status=400,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"error": str(e)}),
            )
        except AccessError as e:
            return werkzeug.wrappers.Response(
                status=403,  # CHANGED FROM 400 TO 403 for access errors
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"error": str(e)}),
            )
        except UserError as e:
            return werkzeug.wrappers.Response(
                status=400,
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"error": str(e)}),
            )
        except Exception as e:
            return werkzeug.wrappers.Response(
                status=500,  # CHANGED FROM 400 TO 500 for general exceptions
                content_type="application/json; charset=utf-8",
                headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                response=json.dumps({"error": str(e)}),
            )


    @validate_token
    @http.route('/api/employee/timeoff/requests', type='http', auth='public', methods=['GET'], csrf=False)
    def get_timeoff_requests(self, **kwargs):
        """Get all time-off requests for an employee with different states"""
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            state = kwargs.get("state")  # Optional filter by state
            
            if not employee_id:
                return valid_response({"error": "Employee ID is required"}, status=400)

            employee_obj = request.env['hr.employee'].browse(int(employee_id))
            if not employee_obj:
                return valid_response({"error": "No employee associated with this ID"}, status=404)

            # Build domain for search
            domain = [('employee_id', '=', int(employee_id))]
            if state:
                domain.append(('state', '=', state))

            timeoff_requests = request.env['hr.leave'].sudo().search(domain, order='create_date desc')
            
            requests_data = []
            for req in timeoff_requests:
                vals = {
                    "id": req.id,
                    "name": req.name or "",
                    "holiday_type": req.holiday_status_id.name or "",
                    "request_date_from": req.request_date_from.strftime('%Y-%m-%d') if req.request_date_from else None,
                    "request_date_to": req.request_date_to.strftime('%Y-%m-%d') if req.request_date_to else None,
                    "number_of_days": req.number_of_days,
                    "state": req.state,
                    "state_display": dict(req._fields['state'].selection)[req.state],
                    "create_date": req.create_date.strftime('%Y-%m-%d %H:%M:%S') if req.create_date else None,
                    # "approved_date": req.date_approve.strftime('%Y-%m-%d %H:%M:%S') if req.date_approve else None
                }
                requests_data.append(vals)
            
            return valid_response(requests_data)
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)

    @validate_token
    @http.route('/api/employee/timeoff/requests/pending', type='http', auth='public', methods=['GET'], csrf=False)
    def get_pending_requests(self, **kwargs):
        """Get pending time-off requests for an employee"""
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            
            if not employee_id:
                return valid_response({"error": "Employee ID is required"}, status=400)

            employee_obj = request.env['hr.employee'].browse(int(employee_id))
            if not employee_obj:
                return valid_response({"error": "No employee associated with this ID"}, status=404)

            pending_requests = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', int(employee_id)),
                ('state', 'in', ['confirm', 'validate1'])  # Pending states
            ], order='create_date desc')
            
            requests_data = []
            for req in pending_requests:
                vals = {
                    "id": req.id,
                    "name": req.name or "",
                    "holiday_type": req.holiday_status_id.name or "",
                    "request_date_from": req.request_date_from.strftime('%Y-%m-%d') if req.request_date_from else None,
                    "request_date_to": req.request_date_to.strftime('%Y-%m-%d') if req.request_date_to else None,
                    "number_of_days": req.number_of_days,
                    "state": req.state,
                    "state_display": dict(req._fields['state'].selection)[req.state],
                    "create_date": req.create_date.strftime('%Y-%m-%d %H:%M:%S') if req.create_date else None
                }
                requests_data.append(vals)
            
            return valid_response(requests_data)
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)

    @validate_token
    @http.route('/api/manager/timeoff/requests/pending', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_pending_requests(self, **kwargs):
        """Get pending time-off requests for an employee"""
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)


            # has_timeoff_access = user_obj.has_group('hr_holidays.group_hr_holidays_user') or \
            #                user_obj.has_group('hr_holidays.group_hr_holidays_manager')
        
            # if not has_timeoff_access:
            #     return valid_response({"error": "Unauthorized access"}, status=401)


            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            
            if not employee_id:
                return valid_response({"error": "Employee ID is required"}, status=400)

            employee_obj = request.env['hr.employee'].browse(int(employee_id))
            if not employee_obj:
                return valid_response({"error": "No employee associated with this ID"}, status=404)

            # Pagination parameters
            page = int(kwargs.get('page', 1))
            limit = int(kwargs.get('limit', 10))
            offset = (page - 1) * limit

            # Get total count
            total_count = request.env['hr.leave'].sudo().search_count([
                ('state', 'in', ['confirm', 'validate1'])  # Pending states
            ])

            pending_requests = request.env['hr.leave'].sudo().search([
                ('state', 'in', ['confirm', 'validate1'])  # Pending states
            ], order='create_date desc', limit=limit, offset=offset)
            
            requests_data = []
            for req in pending_requests:
                vals = {
                    "id": req.id,
                    "employee_name": req.employee_id.name if req.employee_id else "",
                    "name": req.name or "",
                    "holiday_type": req.holiday_status_id.name or "",
                    "request_date_from": req.request_date_from.strftime('%Y-%m-%d') if req.request_date_from else None,
                    "request_date_to": req.request_date_to.strftime('%Y-%m-%d') if req.request_date_to else None,
                    "number_of_days": req.number_of_days,
                    "state": req.state,
                    "state_display": dict(req._fields['state'].selection)[req.state],
                    "create_date": req.create_date.strftime('%Y-%m-%d %H:%M:%S') if req.create_date else None
                }
                requests_data.append(vals)

            # Pagination metadata
            total_pages = (total_count + limit - 1) // limit
            
            response_data = {
                "data": requests_data,
                "meta": {
                    "pagination": {
                        "current_page": page,
                        "per_page": limit,
                        "total_items": total_count,
                        "total_pages": total_pages,
                        "has_next": page < total_pages,
                        "has_prev": page > 1
                    }
                }
            }
            
            return valid_response(response_data)
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)
        
    @validate_token
    @http.route('/api/manager/timeoff/requests/approved', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_approved_requests(self, **kwargs):
        """Get pending time-off requests for an employee"""
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)


            # has_timeoff_access = user_obj.has_group('hr_holidays.group_hr_holidays_user') or \
            #                user_obj.has_group('hr_holidays.group_hr_holidays_manager')
        
            # if not has_timeoff_access:
            #     return valid_response({"error": "Unauthorized access"}, status=401)


            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            
            if not employee_id:
                return valid_response({"error": "Employee ID is required"}, status=400)

            employee_obj = request.env['hr.employee'].browse(int(employee_id))
            if not employee_obj:
                return valid_response({"error": "No employee associated with this ID"}, status=404)

            # Pagination parameters
            page = int(kwargs.get('page', 1))
            limit = int(kwargs.get('limit', 10))
            offset = (page - 1) * limit

            # Get total count
            total_count = request.env['hr.leave'].sudo().search_count([
                ('state', 'in', ['validate'])  # Pending states
            ])

            pending_requests = request.env['hr.leave'].sudo().search([
                ('state', 'in', ['validate'])  # Pending states
            ], order='create_date desc', limit=limit, offset=offset)
            
            requests_data = []
            for req in pending_requests:
                vals = {
                    "id": req.id,
                    "employee_name": req.employee_id.name if req.employee_id else "",
                    "name": req.name or "",
                    "holiday_type": req.holiday_status_id.name or "",
                    "request_date_from": req.request_date_from.strftime('%Y-%m-%d') if req.request_date_from else None,
                    "request_date_to": req.request_date_to.strftime('%Y-%m-%d') if req.request_date_to else None,
                    "number_of_days": req.number_of_days,
                    "state": req.state,
                    "state_display": dict(req._fields['state'].selection)[req.state],
                    "create_date": req.create_date.strftime('%Y-%m-%d %H:%M:%S') if req.create_date else None
                }
                requests_data.append(vals)

            # Pagination metadata
            total_pages = (total_count + limit - 1) // limit
            
            response_data = {
                "data": requests_data,
                "meta": {
                    "pagination": {
                        "current_page": page,
                        "per_page": limit,
                        "total_items": total_count,
                        "total_pages": total_pages,
                        "has_next": page < total_pages,
                        "has_prev": page > 1
                    }
                }
            }
            
            return valid_response(response_data)
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)
        
    @validate_token
    @http.route('/api/manager/timeoff/requests/refused', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_refused_requests(self, **kwargs):
        """Get pending time-off requests for an employee"""
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)


            # has_timeoff_access = user_obj.has_group('hr_holidays.group_hr_holidays_user') or \
            #                user_obj.has_group('hr_holidays.group_hr_holidays_manager')
        
            # if not has_timeoff_access:
            #     return valid_response({"error": "Unauthorized access"}, status=401)


            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            
            if not employee_id:
                return valid_response({"error": "Employee ID is required"}, status=400)

            employee_obj = request.env['hr.employee'].browse(int(employee_id))
            if not employee_obj:
                return valid_response({"error": "No employee associated with this ID"}, status=404)

            # Pagination parameters
            page = int(kwargs.get('page', 1))
            limit = int(kwargs.get('limit', 10))
            offset = (page - 1) * limit

            # Get total count
            total_count = request.env['hr.leave'].sudo().search_count([
                ('state', 'in', ['refuse'])  # Pending states
            ])

            pending_requests = request.env['hr.leave'].sudo().search([
                ('state', 'in', ['refuse'])  # Pending states
            ], order='create_date desc', limit=limit, offset=offset)
            
            requests_data = []
            for req in pending_requests:
                vals = {
                    "id": req.id,
                    "employee_name": req.employee_id.name if req.employee_id else "",
                    "name": req.name or "",
                    "holiday_type": req.holiday_status_id.name or "",
                    "request_date_from": req.request_date_from.strftime('%Y-%m-%d') if req.request_date_from else None,
                    "request_date_to": req.request_date_to.strftime('%Y-%m-%d') if req.request_date_to else None,
                    "number_of_days": req.number_of_days,
                    "state": req.state,
                    "state_display": dict(req._fields['state'].selection)[req.state],
                    "create_date": req.create_date.strftime('%Y-%m-%d %H:%M:%S') if req.create_date else None
                }
                requests_data.append(vals)

            # Pagination metadata
            total_pages = (total_count + limit - 1) // limit
            
            response_data = {
                "data": requests_data,
                "meta": {
                    "pagination": {
                        "current_page": page,
                        "per_page": limit,
                        "total_items": total_count,
                        "total_pages": total_pages,
                        "has_next": page < total_pages,
                        "has_prev": page > 1
                    }
                }
            }
            
            return valid_response(response_data)
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)
        

    @validate_token
    @http.route('/api/employee/timeoff/requests/approved', type='http', auth='public', methods=['GET'], csrf=False)
    def get_approved_requests(self, **kwargs):
        """Get approved time-off requests for an employee"""
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            employee = user_obj.employee_id
            employee_id = employee.sudo().id

            if not employee_id:
                return valid_response({"error": "Employee ID is required"}, status=400)

            employee_obj = request.env['hr.employee'].browse(int(employee_id))
            if not employee_obj:
                return valid_response({"error": "No employee associated with this ID"}, status=404)

            approved_requests = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', int(employee_id)),
                ('state', 'in', ['validate'])  # Approved state
            ], order='request_date_from desc')
            
            requests_data = []
            for req in approved_requests:
                vals = {
                    "id": req.id,
                    "name": req.name or "",
                    "holiday_type": req.holiday_status_id.name or "",
                    "request_date_from": req.request_date_from.strftime('%Y-%m-%d') if req.request_date_from else None,
                    "request_date_to": req.request_date_to.strftime('%Y-%m-%d') if req.request_date_to else None,
                    "number_of_days": req.number_of_days,
                    "state": req.state,
                    "state_display": dict(req._fields['state'].selection)[req.state],
                    "create_date": req.create_date.strftime('%Y-%m-%d %H:%M:%S') if req.create_date else None
                    # "approved_date": req.date_approve.strftime('%Y-%m-%d %H:%M:%S') if req.date_approve else None
                }
                requests_data.append(vals)
            
            return valid_response(requests_data)
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)

    @validate_token
    @http.route('/api/employee/timeoff/requests/refused', type='http', auth='public', methods=['GET'], csrf=False)
    def get_refused_requests(self, **kwargs):
        """Get refused time-off requests for an employee"""
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            
            if not employee_id:
                return valid_response({"error": "Employee ID is required"}, status=400)

            employee_obj = request.env['hr.employee'].browse(int(employee_id))
            if not employee_obj:
                return valid_response({"error": "No employee associated with this ID"}, status=404)

            refused_requests = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', int(employee_id)),
                ('state', '=', 'refuse')  # Refused state
            ], order='create_date desc')
            
            requests_data = []
            for req in refused_requests:
                vals = {
                    "id": req.id,
                    "name": req.name or "",
                    "holiday_type": req.holiday_status_id.name or "",
                    "request_date_from": req.request_date_from.strftime('%Y-%m-%d') if req.request_date_from else None,
                    "request_date_to": req.request_date_to.strftime('%Y-%m-%d') if req.request_date_to else None,
                    "number_of_days": req.number_of_days,
                    "state": req.state,
                    "state_display": dict(req._fields['state'].selection)[req.state],
                    # "refused_date": req.date_refuse.strftime('%Y-%m-%d %H:%M:%S') if req.date_refuse else None
                    "create_date": req.create_date.strftime('%Y-%m-%d %H:%M:%S') if req.create_date else None

                }
                requests_data.append(vals)
            
            return valid_response(requests_data)
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)



    def _get_color_hex(self, color_index):
        """Convert Odoo color index to hex color"""
        # Odoo default colors (commonly used in kanban views)
        color_map = {
            0: '#FFFFFF',  # White
            1: '#CC7B7B',  # Light Red
            2: '#CC9999',  # Light Pink
            3: '#CCAAAA',  # Light Brown
            4: '#CCBBBB',  # Light Gray
            5: '#CCCCCC',  # Gray
            6: '#CCDDCC',  # Light Green
            7: '#CCEECC',  # Pale Green
            8: '#CCFFCC',  # Light Mint
            9: '#CCCCFF',  # Light Blue
            10: '#CCDDFF', # Pale Blue
            11: '#CCEEFF', # Light Cyan
        }
        return color_map.get(color_index, '#CCCCCC')
    
    @validate_token
    @http.route('/api/employee/timeoff/balance', type='http', auth='public', methods=['GET'], csrf=False)
    def get_timeoff_balance(self, **kwargs):
        """Get employee's time-off balance (remaining and spent days)"""
        try:
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            holiday_status_id = kwargs.get("holiday_status_id")  # Optional: specific time-off type
            
            if not employee_id:
                return valid_response({"error": "Employee ID is required"}, status=400)

            employee_obj = request.env['hr.employee'].browse(int(employee_id))
            if not employee_obj:
                return valid_response({"error": "No employee associated with this ID"}, status=404)

            # Get time-off types
            domain = []
            if holiday_status_id:
                domain.append(('id', '=', int(holiday_status_id)))
            
            holiday_types = request.env['hr.leave.type'].sudo().search(domain)
            
            balance_data = []
            all_allocated = 0
            all_spent = 0
            all_remaining = 0
            for holiday_type in holiday_types:
                # Get allocations for this employee and leave type
                allocations = request.env['hr.leave.allocation'].sudo().search([
                    ('employee_id', '=', int(employee_id)),
                    ('holiday_status_id', '=', holiday_type.id),
                    ('state', '=', 'validate')
                ])
                
                total_allocated = sum(allocations.mapped('number_of_days'))
                all_allocated += total_allocated
                # Get approved leaves for this employee and leave type
                approved_leaves = request.env['hr.leave'].sudo().search([
                    ('employee_id', '=', int(employee_id)),
                    ('holiday_status_id', '=', holiday_type.id),
                    ('state', '=', 'validate')
                ])
                
                total_spent = sum(approved_leaves.mapped('number_of_days'))
                remaining_days = total_allocated - total_spent
                
                all_spent += total_spent
                all_remaining += remaining_days

                balance_info = {
                    "holiday_type_id": holiday_type.id,
                    "holiday_type_name": holiday_type.name or "",
                    "total_allocated": total_allocated,
                    "total_spent": total_spent,
                    "remaining_days": remaining_days,
                    "color": self._get_color_hex(holiday_type.color)
                }
                balance_data.append(balance_info)
            
            return valid_response({
                                    'types': balance_data,
                                    'all_allocated': all_allocated,
                                    'all_spent': all_spent,
                                    'all_remaining': all_remaining,
                                 })
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)

    @validate_token
    @http.route('/api/employee/timeoff/types', type='http', auth='public', methods=['GET'], csrf=False)
    def get_timeoff_types(self, **kwargs):
        """Get available time-off types"""
        try:
            timeoff_types = request.env['hr.leave.type'].sudo().search([])
            
            types_data = []
            for timeoff_type in timeoff_types:
                vals = {
                    "id": timeoff_type.id,
                    "name": timeoff_type.name or "",
                    "color": self._get_color_hex(timeoff_type.color),
                    "requires_allocation": timeoff_type.requires_allocation,
                    "active": timeoff_type.active
                }
                types_data.append(vals)
            
            return valid_response(types_data)
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)

    @validate_token
    @http.route('/api/employee/timeoff/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    def cancel_timeoff_request(self, **kwargs):
        """Cancel a time-off request (only if it's in draft or confirm state)"""
        try:
            payload = request.httprequest.data.decode()
            payload = json.loads(payload)
            request_id = payload.get("request_id")
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            
            if not all([request_id, employee_id]):
                return valid_response({"error": "Request ID and Employee ID are required"}, status=400)

            timeoff_request = request.env['hr.leave'].sudo().search([
                ('id', '=', int(request_id)),
                ('employee_id', '=', int(employee_id))
            ], limit=1)
            
            if not timeoff_request:
                return valid_response({"error": "Time-off request not found"}, status=404)
            
            if timeoff_request.state not in ['draft', 'confirm']:
                return valid_response({"error": "Cannot cancel request in current state"}, status=400)
            
            timeoff_request.sudo().action_draft()
            timeoff_request.sudo().unlink()
            
            return valid_response({"message": "Time-off request cancelled successfully"})
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)
        




    @validate_token
    @http.route('/api/manager/timeoff/approve', type='http', auth='public', methods=['POST'], csrf=False)
    def approve_timeoff_request(self, **kwargs):
        """Approve a time-off request"""
        try:
            payload = request.httprequest.data.decode()
            payload = json.loads(payload)
            request_id = payload.get("request_id")
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            
            # Check if user has timeoff security groups
            # has_timeoff_access = user_obj.has_group('hr_holidays.group_hr_holidays_user') or \
            #                 user_obj.has_group('hr_holidays.group_hr_holidays_manager')
            
            # if not has_timeoff_access:
            #     return valid_response({"error": "Unauthorized access"}, status=401)
            
            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            
            if not all([request_id, employee_id]):
                return valid_response({"error": "Request ID and Employee ID are required"}, status=400)

            timeoff_request = request.env['hr.leave'].sudo().search([
                ('id', '=', int(request_id))
            ], limit=1)
            
            if not timeoff_request:
                return valid_response({"error": "Time-off request not found"}, status=404)
            
            timeoff_request.sudo().action_approve()
            
            return valid_response({"message": "Time-off request approved successfully"})
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)


    @validate_token
    @http.route('/api/manager/timeoff/refuse', type='http', auth='public', methods=['POST'], csrf=False)
    def refuse_timeoff_request(self, **kwargs):
        """Refuse a time-off request"""
        try:
            payload = request.httprequest.data.decode()
            payload = json.loads(payload)
            request_id = payload.get("request_id")
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            
            # Check if user has timeoff security groups
            # has_timeoff_access = user_obj.has_group('hr_holidays.group_hr_holidays_user') or \
            #                 user_obj.has_group('hr_holidays.group_hr_holidays_manager')
            
            # if not has_timeoff_access:
            #     return valid_response({"error": "Unauthorized access"}, status=401)
            
            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            
            if not all([request_id, employee_id]):
                return valid_response({"error": "Request ID and Employee ID are required"}, status=400)

            timeoff_request = request.env['hr.leave'].sudo().search([
                ('id', '=', int(request_id))
            ], limit=1)
            
            if not timeoff_request:
                return valid_response({"error": "Time-off request not found"}, status=404)
            
            timeoff_request.sudo().action_refuse()
            
            return valid_response({"message": "Time-off request refused successfully"})
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)


    @validate_token
    @http.route('/api/manager/timeoff/validate', type='http', auth='public', methods=['POST'], csrf=False)
    def validate_timeoff_request(self, **kwargs):
        """Validate a time-off request"""
        try:
            payload = request.httprequest.data.decode()
            payload = json.loads(payload)
            request_id = payload.get("request_id")
            user_id = request.uid
            user_obj = request.env['res.users'].browse(user_id)
            
            # Check if user has timeoff security groups
            # has_timeoff_access = user_obj.has_group('hr_holidays.group_hr_holidays_user') or \
            #                 user_obj.has_group('hr_holidays.group_hr_holidays_manager')
            
            # if not has_timeoff_access:
            #     return valid_response({"error": "Unauthorized access"}, status=401)
            
            employee = user_obj.employee_id
            employee_id = employee.sudo().id
            
            if not all([request_id, employee_id]):
                return valid_response({"error": "Request ID and Employee ID are required"}, status=400)

            timeoff_request = request.env['hr.leave'].sudo().search([
                ('id', '=', int(request_id))
            ], limit=1)
            
            if not timeoff_request:
                return valid_response({"error": "Time-off request not found"}, status=404)
            
            timeoff_request.sudo().action_validate()
            
            return valid_response({"message": "Time-off request validated successfully"})
            
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)



##########################Developed by Mohamed Adel#####################################

    @validate_token
    @http.route('/api/attendance/edit_attendance', type='http', auth='none', methods=['POST'], csrf=False)
    def create_attendance_edit_request(self):
        """
        Creates a new attendance edit request for the logged-in employee.
        This endpoint allows an authenticated user to submit a request to modify their attendance record,
        specifying the type of check (sign_in or sign_out) and the desired new timestamp.
        Access: Authenticated users with a valid token.
        Returns:
            JSON response indicating success or failure, including the created request ID and status.
        Developed by Mohamed Adel, Odoo Developer.
        """
        try:
            raw_data = request.httprequest.data.decode('utf-8').strip()
            if raw_data:
                data = json.loads(raw_data)
            else:
                data = {}

            attendance_id = data.get('attendance_id')

            if not attendance_id:
                return Response(
                    json.dumps({"success": False, "error": "Missing required field: attendance_id."}),
                    status=400,
                    content_type='application/json'
                )

            user = request.env.user
            employee = user.employee_id

            if not employee:
                return Response(
                    json.dumps({"success": False, "error": "No employee linked to your user account."}),
                    status=400,
                    content_type='application/json'
                )

            attendance = request.env['hr.attendance'].browse(attendance_id)
            if not attendance.exists() or attendance.employee_id.id != employee.id:
                return Response(
                    json.dumps({"success": False, "error": "Attendance not found or not yours."}),
                    status=404,
                    content_type='application/json'
                )

            vals = {
                'employee_id': employee.id,
                'attendance_id': attendance.id,
            }

            edit_request = request.env['hr.attendance.edit.request'].create(vals)

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
        """
           Retrieves all attendance edit requests made by the logged-in employee.
           This endpoint fetches the list of attendance edit requests submitted by the current user,
           including the original and requested check-in/out times and the status of each request.
           Access: Authenticated users with a valid token.
           Returns:
               JSON response with the list of attendance edit requests.
           Developed by Mohamed Adel, Odoo Developer.
           """
        try:
            user = request.env.user
            employee = user.employee_id

            if not employee:
                return Response(
                    json.dumps({"success": False, "error": "No employee linked to your user account."}),
                    status=400,
                    content_type='application/json'
                )

            edit_requests = request.env['hr.attendance.edit.request'].search([
                ('employee_id', '=', employee.id)
            ], order="create_date desc")

            result = []
            for req in edit_requests:
                result.append({
                    "id": req.id,
                    "attendance_id": req.attendance_id.id,
                    "check_in_old": str(req.attendance_id.check_in) if req.attendance_id.check_in else None,
                    "check_out_old": str(req.attendance_id.check_out) if req.attendance_id.check_out else None,
                    "check_in_new": str(req.check_in_new) if req.check_in_new else None,
                    "check_out_new": str(req.check_out_new) if req.check_out_new else None,
                    "state": req.state,
                    "created_on": str(req.create_date)
                })

            return Response(
                json.dumps({
                    "success": True,
                    "count": len(result),
                    "requests": result
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error fetching attendance edit requests: {str(e)}", exc_info=True)
            return Response(
                json.dumps({"success": False, "error": "Internal server error."}),
                status=500,
                content_type='application/json'
            )

    @validate_token
    @http.route('/api/attendance/get_all_requests', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_edit_requests(self):
        """
            Retrieves all attendance edit requests across all employees.
            This endpoint is restricted to admin users. It returns a comprehensive list of all edit requests,
            including employee information, attendance details, and request statuses.
            Access: Admin users only.
            Returns:
                JSON response with all attendance edit requests.
            Developed by Mohamed Adel, Odoo Developer.
            """
        try:
            user = request.env.user

            if not user.has_group('base.group_system'):
                return Response(json.dumps({
                    "success": False,
                    "error": "Access denied. You must be an admin."
                }), status=403, content_type='application/json')

            edit_requests = request.env['hr.attendance.edit.request'].search([], order="create_date desc")

            result = []
            for req in edit_requests:
                result.append({
                    "id": req.id,
                    "employee_id": req.employee_id.id,
                    "employee_name": req.employee_id.name,
                    "attendance_id": req.attendance_id.id,
                    "check_in_old": str(req.attendance_id.check_in) if req.attendance_id.check_in else None,
                    "check_out_old": str(req.attendance_id.check_out) if req.attendance_id.check_out else None,
                    "check_in_new": str(req.check_in_new) if req.check_in_new else None,
                    "check_out_new": str(req.check_out_new) if req.check_out_new else None,
                    "state": req.state,
                    "created_on": str(req.create_date)
                })

            return Response(json.dumps({
                "success": True,
                "count": len(result),
                "requests": result
            }), status=200, content_type='application/json')

        except Exception as e:
            _logger.error(f"Error fetching all attendance edit requests: {str(e)}", exc_info=True)
            return Response(json.dumps({
                "success": False,
                "error": "Internal server error."
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
        """
        Approves a specific attendance edit request.
        This endpoint allows admin users to approve a submitted attendance edit request by its ID.
        Upon approval, the request status is updated accordingly.
        Access: Admin users only.
        Parameters:
            - request_id (int): The ID of the attendance edit request to approve (passed in POST data).
            - check_in_new (str): New check-in datetime string (optional).
            - check_out_new (str): New check-out datetime string (optional).
        Returns:
            JSON response indicating success or failure of the approval operation.
        Developed by Mohamed Adel, Odoo Developer.
        """
        try:
            user = request.env.user

            if not user.has_group('base.group_system'):
                return json.dumps({
                    "success": False,
                    "error": "Access denied. You must be an admin."
                })

            data = json.loads(request.httprequest.data.decode('utf-8'))
            request_id = data.get('request_id')
            check_in_new = data.get('check_in_new')
            check_out_new = data.get('check_out_new')

            if not request_id:
                return json.dumps({
                    "success": False,
                    "error": "Missing request_id."
                })

            edit_request = request.env['hr.attendance.edit.request'].browse(int(request_id))
            if not edit_request.exists():
                return json.dumps({
                    "success": False,
                    "error": "Edit request not found."
                })


            if check_in_new and check_out_new:
                try:
                    check_in_dt = datetime.strptime(check_in_new, "%Y-%m-%d %H:%M:%S")
                    check_out_dt = datetime.strptime(check_out_new, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return json.dumps({
                        "success": False,
                        "error": "Invalid datetime format. Use YYYY-MM-DD HH:MM:SS"
                    })

                if check_in_dt >= check_out_dt:
                    return json.dumps({
                        "success": False,
                        "error": "\"Check In\" time cannot be later than or equal to \"Check Out\" time."
                    })

                edit_request.check_in_new = check_in_dt
                edit_request.check_out_new = check_out_dt

            edit_request.state = 'approved'

            return json.dumps({
                "success": True,
                "message": "Request approved successfully."
            })

        except Exception as e:
            _logger.error(f"Error in approve_attendance_edit_request: {str(e)}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": "Internal server error."
            })


    @validate_token
    @http.route('/api/attendance/update', type='http', auth='none', methods=['POST'], csrf=False)
    def admin_update_attendance(self):
        """
        Allows Admin or HR Manager to update an existing attendance record.
        Requires: attendance_id, check_in (optional: check_out)
        """
        try:
            user = request.env.user

            if user._name == 'res.users' and user.id == request.env.ref('base.public_user').id:
                return Response(
                    json.dumps({"success": False, "error": "Authentication required."}),
                    status=401,
                    content_type='application/json'
                )

            if not (user.has_group('base.group_system') or user.has_group('hr.group_hr_manager')):
                return Response(
                    json.dumps(
                        {"success": False, "error": "Access denied. Only Admin or HR Manager can update attendance."}),
                    status=403,
                    content_type='application/json'
                )

            raw_data = request.httprequest.data.decode('utf-8').strip()
            if not raw_data:
                return Response(
                    json.dumps({"success": False, "error": "Empty request body."}),
                    status=400,
                    content_type='application/json'
                )
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                return Response(
                    json.dumps({"success": False, "error": "Invalid JSON format."}),
                    status=400,
                    content_type='application/json'
                )

            attendance_id = data.get('attendance_id')
            check_in = data.get('check_in')
            check_out = data.get('check_out')

            if not attendance_id:
                return Response(
                    json.dumps({"success": False, "error": "Missing required field: attendance_id."}),
                    status=400,
                    content_type='application/json'
                )

            attendance = request.env['hr.attendance'].sudo().browse(attendance_id)
            if not attendance.exists():
                return Response(
                    json.dumps({"success": False, "error": "Attendance record not found."}),
                    status=404,
                    content_type='application/json'
                )

            try:
                if check_in:
                    fields.Datetime.to_datetime(check_in)
                if check_out:
                    fields.Datetime.to_datetime(check_out)
            except Exception as e:
                return Response(
                    json.dumps({"success": False, "error": f"Invalid datetime format: {str(e)}"}),
                    status=400,
                    content_type='application/json'
                )

            update_vals = {}
            if check_in is not None:
                update_vals['check_in'] = check_in
            if check_out is not None:
                update_vals['check_out'] = check_out

            if not update_vals:
                return Response(
                    json.dumps({"success": False, "error": "No fields to update."}),
                    status=400,
                    content_type='application/json'
                )

            # Wrap write operation in a savepoint for proper transaction handling
            try:
                with request.env.cr.savepoint():
                    attendance.sudo().write(update_vals)
                    request.env.cr.commit()  # Explicit commit
            except Exception as write_error:
                _logger.error(f"Error writing attendance record: {str(write_error)}", exc_info=True)
                request.env.cr.rollback()  # Explicit rollback on error
                return Response(
                    json.dumps({"success": False, "error": "Failed to update attendance record.", "debug": str(write_error)}),
                    status=500,
                    content_type='application/json'
                )

            return Response(
                json.dumps({
                    "success": True,
                    "message": "Attendance updated successfully.",
                    "attendance_id": attendance.id,
                    "employee_id": attendance.employee_id.id,
                    "check_in": attendance.check_in,
                    "check_out": attendance.check_out,
                }, default=str),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error("Error in admin_update_attendance:", exc_info=True)
            request.env.cr.rollback()  # Rollback on any error
            return Response(
                json.dumps({"success": False, "error": "Internal server error.", "debug": str(e)}),
                status=500,
                content_type='application/json'
            )