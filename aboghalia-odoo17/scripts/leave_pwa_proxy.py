#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leaves PWA reverse proxy (beta).

Listens on a dedicated port (default 8095) and forwards to Odoo beta (8070).
Strips Cookie / Set-Cookie so PWA login/logout stays independent from /web sessions.

Usage:
  LEAVE_PWA_PORT=8095 ODOO_UPSTREAM=http://127.0.0.1:8070 python3 leave_pwa_proxy.py
"""
from __future__ import print_function

import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LISTEN_HOST = os.environ.get("LEAVE_PWA_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LEAVE_PWA_PORT", "8095"))
UPSTREAM = os.environ.get("ODOO_UPSTREAM", "http://127.0.0.1:8070").rstrip("/")

# Paths allowed through the leave PWA portal
ALLOWED_PREFIXES = (
    "/leave",
    "/ao_leave_pwa/",
)


def _allowed(path):
    if path == "/":
        return True
    return any(path == p or path.startswith(p if p.endswith("/") else p + "/") or path.startswith(p)
               for p in ALLOWED_PREFIXES) or path.startswith("/leave")


class LeavePwaProxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _proxy(self):
        path = self.path.split("?", 1)[0]
        # Root → leave app
        target_path = self.path
        if path == "/":
            target_path = "/leave" + (("?" + self.path.split("?", 1)[1]) if "?" in self.path else "")

        if not _allowed(path if path != "/" else "/leave"):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"Not found (Leaves PWA proxy)")
            return

        url = UPSTREAM + target_path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        headers = {}
        for key in ("Content-Type", "Accept", "Accept-Language", "access-token",
                    "x-company-id", "x-company-ids", "User-Agent", "Origin", "Referer"):
            val = self.headers.get(key)
            if val:
                headers[key] = val
        # Intentionally do NOT forward Cookie — keeps Odoo web session separate.
        headers["Connection"] = "close"
        headers["Host"] = self.headers.get("Host", "localhost").split(":")[0]

        req = Request(url, data=body, headers=headers, method=self.command)
        try:
            with urlopen(req, timeout=120) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for hk, hv in resp.headers.items():
                    lk = hk.lower()
                    # Drop hop-by-hop and auth cookies from Odoo
                    if lk in ("transfer-encoding", "connection", "keep-alive",
                              "proxy-authenticate", "proxy-authorization", "te",
                              "trailers", "upgrade", "set-cookie", "set-cookie2",
                              "content-encoding", "content-length"):
                        continue
                    self.send_header(hk, hv)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                # Helpful for PWA testing
                self.send_header("Cache-Control", resp.headers.get("Cache-Control", "no-cache"))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(data)
        except HTTPError as e:
            data = e.read() or b""
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "text/plain"))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
        except URLError as e:
            msg = ("Upstream Odoo unreachable (%s). Is beta running on %s?" % (e, UPSTREAM)).encode()
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(msg)

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def do_PATCH(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def do_OPTIONS(self):
        self._proxy()

    def do_HEAD(self):
        self._proxy()


def main():
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), LeavePwaProxy)
    print("Leaves PWA proxy listening on http://%s:%s -> %s" % (LISTEN_HOST, LISTEN_PORT, UPSTREAM),
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down", flush=True)
        server.server_close()


if __name__ == "__main__":
    main()
