#!/usr/bin/env python3
"""Send one Web Push message. Used by ao_leave_pwa via isolated venv."""
import json
import sys

from py_vapid import Vapid
from pywebpush import WebPushException, webpush


def main():
    payload = json.load(sys.stdin)
    private = payload.get("vapid_private_key") or ""
    claims = payload.get("vapid_claims") or {"sub": "mailto:leave-pwa@aboghaliaoffice.com"}
    if "BEGIN" in private and "\\n" in private:
        private = private.replace("\\n", "\n")
    try:
        vapid = Vapid.from_pem(private.encode() if isinstance(private, str) else private)
        webpush(
            subscription_info=payload["subscription"],
            data=payload.get("data") or "",
            vapid_private_key=vapid,
            vapid_claims=claims,
        )
        print(json.dumps({"ok": True}))
        return 0
    except WebPushException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        print(json.dumps({"ok": False, "error": str(e), "response": status}))
        return 2
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
