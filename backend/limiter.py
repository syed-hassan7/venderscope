import os
from slowapi import Limiter
from fastapi import Request

# Set RATE_LIMIT_ENABLED=0 to disable for testing
_enabled = os.getenv("RATE_LIMIT_ENABLED", "1") != "0"


def _xff_client_mode() -> str:
    override = (os.getenv("RATE_LIMIT_XFF_CLIENT") or "").strip().lower()
    if override in ("first", "last"):
        return override
    if os.getenv("SPACE_ID") or os.getenv("SPACE_HOST"):
        return "first"
    return "last"


def _real_ip(request: Request) -> str:
    """
    Client IP for rate-limit keys.

    X-Forwarded-For hop order differs by platform:
    - Hugging Face Spaces (SPACE_ID or SPACE_HOST set): leftmost hop (XFF[0]).
      HF's reverse proxy typically places the browser IP first (same pattern as
      public HF Space examples). Residual: leftmost is spoofable if HF forwards
      a client-supplied XFF prefix.
    - Legacy Render / direct: rightmost hop (XFF[-1]). Render appends the
      connecting client last, so the last hop is the one the proxy observed.

    RATE_LIMIT_XFF_CLIENT=first|last (case-insensitive) overrides the default.
    X-Real-IP / CF-Connecting-IP are ignored unless RATE_LIMIT_TRUST_X_REAL_IP=1
    and the header is present (then that value is used, stripped). Default off
    so a spoofed X-Real-IP cannot bypass the limiter.

    Hop order has not been validated against live HF Space request headers.
    """
    if os.getenv("RATE_LIMIT_TRUST_X_REAL_IP") == "1":
        for name in ("x-real-ip", "cf-connecting-ip"):
            raw = request.headers.get(name)
            if raw and raw.strip():
                return raw.strip()

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[0] if _xff_client_mode() == "first" else hops[-1]
    return request.client.host if request.client else "unknown"


# Shared limiter instance — imported by main.py (attached to app.state)
# and by individual routers (for @limiter.limit() decorators)
limiter = Limiter(key_func=_real_ip, enabled=_enabled)
