"""Unit tests for limiter client-IP selection (XFF hop + optional X-Real-IP)."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from limiter import _real_ip

_CONTROL_KEYS = (
    "RATE_LIMIT_XFF_CLIENT",
    "SPACE_ID",
    "SPACE_HOST",
    "RATE_LIMIT_TRUST_X_REAL_IP",
)

XFF_TWO_HOPS = "1.1.1.1, 2.2.2.2"


@contextmanager
def limiter_env(**kwargs):
    """Isolate limiter env. Omitted control keys are deleted for the block."""
    with patch.dict("os.environ", {}, clear=False):
        import os

        saved = {k: os.environ[k] for k in _CONTROL_KEYS if k in os.environ}
        for k in _CONTROL_KEYS:
            os.environ.pop(k, None)
        os.environ.update(kwargs)
        try:
            yield
        finally:
            for k in _CONTROL_KEYS:
                os.environ.pop(k, None)
            os.environ.update(saved)


def make_request(xff=None, x_real_ip=None, client_host="9.9.9.9"):
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    if x_real_ip is not None:
        headers["x-real-ip"] = x_real_ip
    client = SimpleNamespace(host=client_host) if client_host is not None else None
    return SimpleNamespace(headers=headers, client=client)


def test_xff_override_first_uses_leftmost_hop():
    with limiter_env(RATE_LIMIT_XFF_CLIENT="first"):
        assert _real_ip(make_request(xff=XFF_TWO_HOPS)) == "1.1.1.1"


def test_xff_override_last_uses_rightmost_hop():
    with limiter_env(RATE_LIMIT_XFF_CLIENT="last"):
        assert _real_ip(make_request(xff=XFF_TWO_HOPS)) == "2.2.2.2"


def test_xff_override_is_case_insensitive():
    with limiter_env(RATE_LIMIT_XFF_CLIENT="FIRST"):
        assert _real_ip(make_request(xff=XFF_TWO_HOPS)) == "1.1.1.1"


def test_space_id_defaults_to_first_hop_when_no_override():
    with limiter_env(SPACE_ID="user/venderscope"):
        assert _real_ip(make_request(xff=XFF_TWO_HOPS)) == "1.1.1.1"


def test_no_space_id_no_override_defaults_to_last_hop():
    with limiter_env():
        assert _real_ip(make_request(xff=XFF_TWO_HOPS)) == "2.2.2.2"


def test_no_xff_falls_back_to_request_client_host():
    with limiter_env():
        req = make_request(xff=None, client_host="8.8.8.8")
        assert _real_ip(req) == "8.8.8.8"


def test_x_real_ip_ignored_by_default():
    with limiter_env():
        req = make_request(xff=XFF_TWO_HOPS, x_real_ip="3.3.3.3")
        assert _real_ip(req) == "2.2.2.2"


def test_trust_x_real_ip_uses_header_when_enabled():
    with limiter_env(RATE_LIMIT_TRUST_X_REAL_IP="1"):
        req = make_request(xff=XFF_TWO_HOPS, x_real_ip=" 3.3.3.3 ")
        assert _real_ip(req) == "3.3.3.3"


def test_audit_ip_uses_limiter_hop():
    from services.audit import _get_ip

    with limiter_env(SPACE_ID="user/space"):
        req = make_request(xff=XFF_TWO_HOPS)
        assert _get_ip(req) == _real_ip(req) == "1.1.1.1"
    with limiter_env(RATE_LIMIT_XFF_CLIENT="last"):
        req = make_request(xff=XFF_TWO_HOPS)
        assert _get_ip(req) == _real_ip(req) == "2.2.2.2"


def test_whitespace_and_empty_hops_skipped():
    messy = "  1.1.1.1 , , 2.2.2.2  "
    with limiter_env(RATE_LIMIT_XFF_CLIENT="first"):
        assert _real_ip(make_request(xff=messy)) == "1.1.1.1"
    with limiter_env(RATE_LIMIT_XFF_CLIENT="last"):
        assert _real_ip(make_request(xff=messy)) == "2.2.2.2"
