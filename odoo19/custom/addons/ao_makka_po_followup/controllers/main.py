# -*- coding: utf-8 -*-
import base64
import json
import logging

from odoo import http
from odoo.exceptions import AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)


class PoOrderApiController(http.Controller):

    def _authenticate_basic(self):
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Basic '):
            return False, request.make_json_response({
                'status': 'error',
                'message': 'Missing or invalid Authorization header. Use Basic Auth.',
            }, status=401)

        ICP = request.env['ir.config_parameter'].sudo()
        expected_login = ICP.get_param('ao_makka_po_followup.po_order_api_login') or ''
        expected_password = ICP.get_param('ao_makka_po_followup.po_order_api_password') or ''

        try:
            encoded = auth_header.split('Basic ', 1)[1]
            decoded = base64.b64decode(encoded).decode('utf-8')
            login, password = decoded.split(':', 1)
        except Exception:
            return False, request.make_json_response({
                'status': 'error',
                'message': 'Invalid Basic Auth credentials format.',
            }, status=401)

        if expected_login and expected_password and login == expected_login and password == expected_password:
            return True, None

        try:
            uid = request.env['res.users'].sudo()._login(
                request.db, login, password, user_agent_env={}
            )
        except AccessDenied:
            uid = False
        except Exception:
            _logger.exception('Makka PO Order API login fallback failed')
            uid = False
        if not uid:
            return False, request.make_json_response({
                'status': 'error',
                'message': 'Invalid credentials.',
            }, status=401)
        return True, None

    def _parse_items(self):
        try:
            payload = json.loads(request.httprequest.data.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return None, request.make_json_response({
                'status': 'error',
                'message': 'Invalid JSON body.',
            }, status=400)

        items = payload.get('items')
        if items is None:
            items = [payload]
        if not isinstance(items, list) or not items:
            return None, request.make_json_response({
                'status': 'error',
                'message': 'Expected a non-empty item or items list.',
            }, status=400)
        return items, None

    @http.route(
        '/api/makka_po_order/receive',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def receive_po_order(self, **kwargs):
        try:
            ok, error_response = self._authenticate_basic()
            if not ok:
                return error_response

            items, error_response = self._parse_items()
            if error_response:
                return error_response

            results = []
            PoOrder = request.env['makka.po.order'].sudo()
            for item in items:
                try:
                    document = item.get('document') or item.get('pdf_base64')
                    record = PoOrder.create_from_accounting({
                        'po_number': item.get('po_number') or item.get('name'),
                        'document': document,
                        'document_filename': item.get('document_filename') or item.get('filename'),
                        'remote_invoice_id': item.get('remote_invoice_id') or item.get('invoice_id'),
                        'remote_invoice_name': item.get('remote_invoice_name') or item.get('invoice_name'),
                        'followup_id': item.get('followup_id'),
                    })
                    results.append({
                        'ok': True,
                        'po_number': record.name,
                        'po_order_id': record.id,
                    })
                except Exception as exc:
                    _logger.exception('Failed to receive Makka PO Order item')
                    results.append({
                        'ok': False,
                        'po_number': item.get('po_number') or item.get('name'),
                        'error': str(exc),
                    })

            all_ok = all(row.get('ok') for row in results)
            return request.make_json_response({
                'status': 'success' if all_ok else 'partial',
                'results': results,
            }, status=200 if all_ok else 207)
        except Exception as exc:
            _logger.exception('Makka PO Order receive API crashed')
            return request.make_json_response({
                'status': 'error',
                'message': 'Portal receive failed: %s' % exc,
            }, status=500)

    @http.route(
        '/api/makka_po_order/archive',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def archive_po_order(self, **kwargs):
        try:
            ok, error_response = self._authenticate_basic()
            if not ok:
                return error_response

            items, error_response = self._parse_items()
            if error_response:
                return error_response

            results = []
            PoOrder = request.env['makka.po.order'].sudo()
            for item in items:
                try:
                    archived = PoOrder.archive_from_accounting(item)
                    results.append({
                        'ok': True,
                        'po_number': item.get('po_number') or item.get('name'),
                        'followup_ids': archived.get('followup_ids') or [],
                        'po_order_ids': archived.get('po_order_ids') or [],
                    })
                except Exception as exc:
                    _logger.exception('Failed to archive Makka PO Order item')
                    results.append({
                        'ok': False,
                        'po_number': item.get('po_number') or item.get('name'),
                        'error': str(exc),
                    })

            all_ok = all(row.get('ok') for row in results)
            return request.make_json_response({
                'status': 'success' if all_ok else 'partial',
                'results': results,
            }, status=200 if all_ok else 207)
        except Exception as exc:
            _logger.exception('Makka PO Order archive API crashed')
            return request.make_json_response({
                'status': 'error',
                'message': 'Portal archive failed: %s' % exc,
            }, status=500)
