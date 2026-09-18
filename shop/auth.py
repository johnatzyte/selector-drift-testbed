"""API key protection for the mutating endpoints.

Fail-closed by design: if SHOP_API_KEY is unset the app generates a random key at
startup and prints it, rather than running open. There is no configuration mistake
that leaves a public droplet writable by strangers.

Reads stay public. The current class names are already visible in the page source,
so GET /api/selectors gives away nothing a browser does not.
"""

import os
import secrets
from functools import wraps

from flask import jsonify, request

HEADER = "X-API-Key"
ENV_VAR = "SHOP_API_KEY"


def resolve_key():
    """Return (key, was_configured)."""
    configured = os.environ.get(ENV_VAR, "").strip()
    if configured:
        return configured, True
    return secrets.token_urlsafe(24), False


def require_key(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        from flask import current_app

        expected = current_app.extensions["api_key"]
        presented = request.headers.get(HEADER, "")
        if not secrets.compare_digest(presented, expected):
            return jsonify(
                error="unauthorized",
                reason=f"set the {HEADER} header to the value of {ENV_VAR}",
            ), 401
        return view(*args, **kwargs)

    return wrapper
