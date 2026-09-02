from odoo import http
from odoo.http import request
import functools
import werkzeug.wrappers
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, messaging
from odoo.modules.module import get_module_resource


firebase_file = get_module_resource('ao_attendance_app_api', 'config', 'notifications.json')
firebase_cred = credentials.Certificate(firebase_file)
firebase_app = firebase_admin.initialize_app(firebase_cred)


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

def valid_response(data, status=200):
    """Valid Response
    This will be return when the http request was successfully processed."""
    data = {"count": len(data) if not isinstance(data, str) else 1, "data": data}
    return werkzeug.wrappers.Response(
        status=status, content_type="application/json; charset=utf-8", response=json.dumps(data),
    )

class Notifications(http.Controller):

    @validate_token
    @http.route('/api/test', type='http', auth='public', methods=['POST'], csrf=False)
    def test_notif(self, **kwargs):
        employees_recs = request.env["hr.employee"].sudo().search([])
        tokens = []
        for employee_rec in employees_recs:
            if employee_rec.last_attendance_id.check_in:
                if employee_rec.free_attendance == False:
                    if employee_rec.fcm_token:
                        tokens.append(employee_rec.fcm_token)

        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title="Verifying location..."),
            data={ "check": "location" }
        )
        try:
            response = messaging.send_each_for_multicast(message)
        except Exception as e:
            print("/////////////// notification cron error")
            print(str(e))

    @validate_token
    @http.route('/api/notifications/register', type='http', auth='public', methods=['POST'], csrf=False)
    def register_token(self, **kwargs):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id

        payload = request.httprequest.data.decode()
        payload = json.loads(payload)

        fcm_token = payload.get("fcm_token")

        try:
            record = request.env["hr.employee"].sudo().search([("id", "=", employee.id)], limit=1)

            if not record:
                return request.make_json_response(({
                    "status": "error",
                    "message": "Record not found!"
                }), status=404)

            record.sudo().write({"fcm_token": fcm_token})

            return request.make_json_response(({
                "status": "success",
                "message": "Token successfully created or updated!"
            }), status=201)
        except Exception as e:
            return valid_response({"error": str(e)}, status=500)

    @validate_token
    @http.route('/api/notifications/verify-location', type='http', auth='public', methods=['POST'], csrf=False)
    def verify_location(self, **kwargs):
        user_id = request.uid
        user_obj = request.env['res.users'].browse(user_id)
        employee = user_obj.employee_id

        payload = request.httprequest.data.decode()
        payload = json.loads(payload)

        latitude = payload.get("latitude")
        longitude = payload.get("longitude")

        employees_recs = request.env["hr.employee"].sudo().search([])

        for employee_rec in employees_recs:
            if employee_rec.last_attendance_id.check_in:
                if employee_rec.free_attendance == False:
                    if employee_rec.fcm_token:
                        try:
                            check_location_range = request.env['hr.attendance'].sudo().check_location_range_for_notification(
                                employee,
                                latitude,
                                longitude
                            )
                            return request.make_json_response((), status=204)
                        except Exception as e:
                            message = messaging.Message(
                                token=employee_rec.fcm_token,
                                notification=messaging.Notification(
                                    title="Out of location area!",
                                    body=str(e)
                                )
                            )
                            try:
                                response = messaging.send(message)
                            except Exception as error:
                                print("/////////////// notification cron error")
                                print(str(error))
                            return invalid_response("error", str(e), 400)