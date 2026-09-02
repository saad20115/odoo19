# -*- coding: utf-8 -*-
import mimetypes
import os

from odoo import http
from odoo.http import request
from odoo.modules.module import get_module_path

SECURITY_HEADERS = [
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('Referrer-Policy', 'no-referrer'),
    ('Permissions-Policy', 'geolocation=(), microphone=(), camera=()'),
]


class LeavePwaMain(http.Controller):

    def _static_path(self, *parts):
        base = get_module_path('ao_leave_pwa')
        return os.path.join(base, 'static', 'src', *parts)

    def _read_static(self, *parts):
        path = self._static_path(*parts)
        # Prevent path traversal
        real_base = os.path.realpath(self._static_path())
        real_path = os.path.realpath(path)
        if not real_path.startswith(real_base + os.sep) and real_path != real_base:
            return None
        if not os.path.isfile(real_path):
            return None
        with open(real_path, 'rb') as fh:
            return fh.read()

    def _response(self, content, headers):
        merged = list(SECURITY_HEADERS) + list(headers)
        return request.make_response(content, headers=merged)

    @http.route(['/leave', '/leave/'], type='http', auth='public', methods=['GET'], csrf=False, website=False)
    def leave_pwa_index(self, **kwargs):
        content = self._read_static('leave_pwa.html')
        if content is None:
            return request.not_found()
        return self._response(
            content,
            [
                ('Content-Type', 'text/html; charset=utf-8'),
                ('Cache-Control', 'no-cache'),
                (
                    'Content-Security-Policy',
                    "default-src 'self'; "
                    "script-src 'self'; "
                    "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
                    "font-src 'self' https://fonts.gstatic.com data:; "
                    "img-src 'self' data:; "
                    "connect-src 'self'; "
                    "manifest-src 'self'; "
                    "worker-src 'self'; "
                    "frame-ancestors 'none'",
                ),
            ],
        )

    @http.route('/leave/manifest.webmanifest', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_pwa_manifest(self, **kwargs):
        content = self._read_static('manifest.webmanifest')
        if content is None:
            return request.not_found()
        return self._response(
            content,
            [
                ('Content-Type', 'application/manifest+json'),
                ('Cache-Control', 'public, max-age=3600'),
            ],
        )

    @http.route('/leave/sw.js', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_pwa_sw(self, **kwargs):
        content = self._read_static('service-worker.js')
        if content is None:
            return request.not_found()
        return self._response(
            content,
            [
                ('Content-Type', 'application/javascript; charset=utf-8'),
                ('Cache-Control', 'no-cache'),
            ],
        )

    @http.route('/leave/static/<path:asset>', type='http', auth='public', methods=['GET'], csrf=False)
    def leave_pwa_asset(self, asset, **kwargs):
        content = self._read_static(*asset.split('/'))
        if content is None:
            return request.not_found()
        ctype, _ = mimetypes.guess_type(asset)
        if not ctype:
            if asset.endswith('.js'):
                ctype = 'application/javascript; charset=utf-8'
            elif asset.endswith('.css'):
                ctype = 'text/css; charset=utf-8'
            elif asset.endswith('.svg'):
                ctype = 'image/svg+xml'
            elif asset.endswith('.png'):
                ctype = 'image/png'
            else:
                ctype = 'application/octet-stream'
        return self._response(
            content,
            [
                ('Content-Type', ctype),
                ('Cache-Control', 'no-cache' if asset.endswith(('.js', '.css', '.html')) else 'public, max-age=86400'),
            ],
        )
