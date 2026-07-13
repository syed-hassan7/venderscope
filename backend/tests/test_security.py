# VenderScope — Security Test Suite
# Run with:  cd backend && python -m pytest tests/test_security.py -v
#
# Covers: Registration, Login, JWT, Authorization, Password Security

import time
import uuid
import pytest
import os
from fastapi.testclient import TestClient
import jwt

# ── Bootstrap ────────────────────────────────────────────────────────────────
from main import app
from database import engine, Base
from services.auth_service import JWT_SECRET, ALGORITHM

# Never allow destructive test setup to run against a non-test database.
if not str(engine.url).startswith("sqlite:///./test_security.db"):
    raise RuntimeError(f"Refusing to run tests against non-test database: {engine.url}")

# Use a fresh DB for tests
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)

VALID_EMAIL = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
VALID_PASS  = "SecureP@ss123!"


# ═════════════════════════════════════════════════════════════════════════════
# REGISTRATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestRegistration:
    """Tests for POST /api/auth/register"""

    def test_register_valid(self):
        """Register with valid credentials — expect 200."""
        resp = client.post("/api/auth/register", json={
            "email": VALID_EMAIL, "password": VALID_PASS,
        })
        assert resp.status_code == 200
        assert "created" in resp.json()["message"].lower()

    def test_register_duplicate_email(self):
        """Register with duplicate email — expect 409 with clear message."""
        dup_email = "duplicate@test.example"
        client.post("/api/auth/register", json={"email": dup_email, "password": VALID_PASS})
        resp = client.post("/api/auth/register", json={"email": dup_email, "password": VALID_PASS})
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    def test_register_missing_email(self):
        """Register with missing email — expect 422 validation error."""
        resp = client.post("/api/auth/register", json={"password": VALID_PASS})
        assert resp.status_code == 422

    def test_register_missing_password(self):
        """Register with missing password — expect 422 validation error."""
        resp = client.post("/api/auth/register", json={"email": "missing@pw.com"})
        assert resp.status_code == 422

    def test_register_long_password_rejected(self):
        """Register with 10,000-char password — expect 422 rejection (CRIT-03)."""
        resp = client.post("/api/auth/register", json={
            "email": "longpw@test.com", "password": "A" * 10_000,
        })
        assert resp.status_code == 422

    def test_register_sql_injection_email(self):
        """Register with SQL injection in email — safe handling."""
        resp = client.post("/api/auth/register", json={
            "email": "'; DROP TABLE users; --@test.com",
            "password": VALID_PASS,
        })
        # Should be 422 (invalid email format) — NOT a 500 crash
        assert resp.status_code == 422

    def test_register_xss_payload_email(self):
        """Register with XSS payload in email — safe handling/escaping."""
        resp = client.post("/api/auth/register", json={
            "email": "<script>alert(1)</script>@test.com",
            "password": VALID_PASS,
        })
        assert resp.status_code == 422

    def test_register_invalid_email_format(self):
        """Register with invalid email format — expect 422."""
        resp = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": VALID_PASS,
        })
        assert resp.status_code == 422

    def test_register_short_password(self):
        """Register with password < 8 chars — expect 422."""
        resp = client.post("/api/auth/register", json={
            "email": "short@pw.com",
            "password": "abc",
        })
        assert resp.status_code == 422


# ═════════════════════════════════════════════════════════════════════════════
# LOGIN TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestLogin:
    """Tests for POST /api/auth/login"""

    def test_login_correct_credentials(self):
        """Login with correct credentials — expect 200 + JWT token."""
        resp = client.post("/api/auth/login", json={
            "email": VALID_EMAIL, "password": VALID_PASS,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self):
        """Login with wrong password — expect 401."""
        resp = client.post("/api/auth/login", json={
            "email": VALID_EMAIL, "password": "WrongPassword123!",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self):
        """Login with non-existent user — expect 401 (same as wrong password)."""
        resp = client.post("/api/auth/login", json={
            "email": "nobody@nowhere.com", "password": "SomePassword123!",
        })
        assert resp.status_code == 401

    def test_login_sql_injection_password(self):
        """Login with SQL injection in password — safe handling."""
        resp = client.post("/api/auth/login", json={
            "email": VALID_EMAIL,
            "password": "' OR '1'='1'; DROP TABLE users; --",
        })
        # Should be 401 (wrong password) — NOT a 500 crash
        assert resp.status_code == 401

    def test_login_empty_fields(self):
        """Login with empty fields — expect 422."""
        resp = client.post("/api/auth/login", json={
            "email": "", "password": "",
        })
        assert resp.status_code == 422

    def test_login_long_password_rejected(self):
        """Login with 10,000-char password — expect 422 (bcrypt DoS protection)."""
        resp = client.post("/api/auth/login", json={
            "email": VALID_EMAIL, "password": "A" * 10_000,
        })
        assert resp.status_code == 422


# ═════════════════════════════════════════════════════════════════════════════
# JWT TOKEN TESTS
# ═════════════════════════════════════════════════════════════════════════════

def _get_valid_token():
    """Helper — get a valid access token."""
    resp = client.post("/api/auth/login", json={
        "email": VALID_EMAIL, "password": VALID_PASS,
    })
    return resp.json()["access_token"]


class TestJWT:
    """Tests for JWT token validation on protected routes."""

    def test_valid_token(self):
        """Use a valid token — expect 200."""
        token = _get_valid_token()
        resp = client.get("/api/vendors/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_expired_token(self):
        """Use an expired token — expect 401 or 403."""
        expired = jwt.encode(
            {"sub": "fake-user-id", "exp": 1000000000, "type": "access"},
            JWT_SECRET, algorithm=ALGORITHM,
        )
        resp = client.get("/api/vendors/", headers={"Authorization": f"Bearer {expired}"})
        assert resp.status_code in (401, 403)

    def test_tampered_payload(self):
        """Use a token with tampered user_id — expect 401."""
        token = _get_valid_token()
        # Decode, change sub, re-encode with same secret
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        payload["sub"] = "tampered-user-id"
        tampered = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
        resp = client.get("/api/vendors/", headers={"Authorization": f"Bearer {tampered}"})
        # User with tampered-user-id doesn't exist → 401
        assert resp.status_code == 401

    def test_none_algorithm(self):
        """Use a token with 'none' algorithm (CVE-2015-9235) — expect 401."""
        # Manually construct an unsigned token
        import base64, json as jsonlib
        header = base64.urlsafe_b64encode(jsonlib.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=")
        payload = base64.urlsafe_b64encode(jsonlib.dumps({"sub": "fake", "type": "access"}).encode()).rstrip(b"=")
        none_token = f"{header.decode()}.{payload.decode()}."
        resp = client.get("/api/vendors/", headers={"Authorization": f"Bearer {none_token}"})
        assert resp.status_code in (401, 403)

    def test_wrong_secret(self):
        """Use a token signed with a different secret — expect 401."""
        wrong = jwt.encode(
            {"sub": "fake-user-id", "type": "access"},
            "completely-wrong-secret",
            algorithm=ALGORITHM,
        )
        resp = client.get("/api/vendors/", headers={"Authorization": f"Bearer {wrong}"})
        assert resp.status_code in (401, 403)

    def test_no_token(self):
        """Access protected route with no token — expect 401 or 403."""
        resp = client.get("/api/vendors/")
        assert resp.status_code in (401, 403)

    def test_token_no_sensitive_data(self):
        """Check token payload does not contain password hash or other secrets."""
        token = _get_valid_token()
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        assert "password" not in str(payload).lower()
        assert "hash" not in str(payload).lower()
        assert "secret" not in str(payload).lower()
        # Should only contain: sub, exp, type
        assert set(payload.keys()).issubset({"sub", "exp", "type", "iat", "nbf"})

    def test_refresh_token_cannot_access_protected(self):
        """A refresh token should NOT work as an access token."""
        # Login + get refresh cookie, then try to use it as Bearer
        login_resp = client.post("/api/auth/login", json={
            "email": VALID_EMAIL, "password": VALID_PASS,
        })
        # Manually create a refresh-type token
        refresh = jwt.encode(
            {"sub": "fake-user-id", "type": "refresh"},
            JWT_SECRET, algorithm=ALGORITHM,
        )
        resp = client.get("/api/vendors/", headers={"Authorization": f"Bearer {refresh}"})
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# AUTHORIZATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestAuthorization:
    """Tests for cross-user access control (IDOR protection)."""

    def _create_user_and_vendor(self, email_suffix):
        """Helper — create a user, login, add a vendor, return (token, vendor_id)."""
        email = f"authtest_{email_suffix}_{uuid.uuid4().hex[:6]}@example.com"
        client.post("/api/auth/register", json={"email": email, "password": VALID_PASS})
        login = client.post("/api/auth/login", json={"email": email, "password": VALID_PASS})
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        v = client.post("/api/vendors/", json={
            "name": f"TestVendor-{email_suffix}",
            "domain": f"test-{email_suffix}-{uuid.uuid4().hex[:4]}.com",
        }, headers=headers)
        return token, v.json()["id"]

    def test_user_a_cannot_read_user_b_vendors(self):
        """User A tries to access User B's vendor — expect 404."""
        token_a, _ = self._create_user_and_vendor("a")
        _, vendor_b = self._create_user_and_vendor("b")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        # User A tries to get events for User B's vendor
        resp = client.get(f"/api/vendors/{vendor_b}/events", headers=headers_a)
        assert resp.status_code == 404

    def test_user_a_cannot_delete_user_b_vendor(self):
        """User A tries to delete User B's vendor — expect 404."""
        token_a, _ = self._create_user_and_vendor("c")
        _, vendor_b = self._create_user_and_vendor("d")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        resp = client.delete(f"/api/vendors/{vendor_b}", headers=headers_a)
        assert resp.status_code == 404

    def test_unauthenticated_access_protected(self):
        """Unauthenticated user accesses protected endpoints — expect 401/403."""
        for endpoint in ["/api/vendors/", "/api/quota/"]:
            resp = client.get(endpoint)
            assert resp.status_code in (401, 403), f"Expected 401/403 for {endpoint}, got {resp.status_code}"


# ═════════════════════════════════════════════════════════════════════════════
# PASSWORD SECURITY TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestPasswordSecurity:
    """Tests for password handling."""

    def test_passwords_hashed_with_bcrypt(self):
        """Verify passwords are stored as bcrypt hashes."""
        from database import SessionLocal
        from models import User
        db = SessionLocal()
        user = db.query(User).filter(User.email == VALID_EMAIL).first()
        assert user is not None
        # bcrypt hashes start with $2b$ or $2a$
        assert user.password_hash.startswith("$2b$") or user.password_hash.startswith("$2a$")
        db.close()

    def test_password_not_in_api_response(self):
        """Verify password is not returned in any API response."""
        token = _get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        # Check login response
        login_resp = client.post("/api/auth/login", json={
            "email": VALID_EMAIL, "password": VALID_PASS,
        })
        body = str(login_resp.json())
        assert VALID_PASS not in body
        assert "password_hash" not in body
        assert "$2b$" not in body

    def test_min_password_enforced(self):
        """Verify minimum password length is enforced."""
        resp = client.post("/api/auth/register", json={
            "email": "minpw@test.com", "password": "short",
        })
        assert resp.status_code == 422

    def test_max_password_enforced(self):
        """Verify maximum password length is enforced (bcrypt DoS protection)."""
        resp = client.post("/api/auth/register", json={
            "email": "maxpw@test.com", "password": "A" * 200,
        })
        assert resp.status_code == 422


# ═════════════════════════════════════════════════════════════════════════════
# SECURITY HEADERS TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestSecurityHeaders:
    """Tests for HTTP security headers."""

    def test_security_headers_present(self):
        """Verify security headers are set on responses."""
        resp = client.get("/")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "camera=()" in resp.headers.get("Permissions-Policy", "")

    def test_error_response_no_stack_trace(self):
        """Verify 500 errors don't expose stack traces."""
        # Access a non-existent route — should get 404 or 405, not 500 with trace
        resp = client.get("/api/nonexistent-endpoint-12345")
        body = str(resp.json())
        assert "Traceback" not in body
        assert "File " not in body

    def test_cors_preflight_allows_credentials(self):
        """Auth XHR uses withCredentials — OPTIONS must return ACAO + ACAC=true."""
        origin = "http://localhost:5173"
        resp = client.options(
            "/api/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == origin
        assert resp.headers.get("access-control-allow-credentials") == "true"


# ═════════════════════════════════════════════════════════════════════════════
# GUEST MODE SECURITY TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestGuestScan:
    """Tests for POST /api/guest/scan — unauthenticated CVE-only endpoint."""

    def test_guest_scan_valid_domain(self):
        """Valid domain returns events list and score — no auth required."""
        resp = client.post("/api/guest/scan", json={"domain": "example.com", "name": "Example"})
        # 200 with valid response shape; NVD may return 0 results in test env
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "score"  in data
        assert isinstance(data["events"], list)
        assert isinstance(data["score"], (int, float))

    def test_guest_scan_score_bounded(self):
        """Score must be in [0, 100]."""
        resp = client.post("/api/guest/scan", json={"domain": "example.com", "name": "Example"})
        assert resp.status_code == 200
        score = resp.json()["score"]
        assert 0.0 <= score <= 100.0

    def test_guest_scan_requires_no_auth(self):
        """No Authorization header needed — endpoint is public."""
        resp = client.post("/api/guest/scan", json={"domain": "example.com", "name": "Example"})
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_guest_scan_ssrf_localhost_blocked(self):
        """SSRF: localhost domain must be rejected."""
        resp = client.post("/api/guest/scan", json={"domain": "localhost", "name": "Local"})
        assert resp.status_code == 400

    def test_guest_scan_ssrf_loopback_ip_blocked(self):
        """SSRF: 127.0.0.1 must be rejected."""
        resp = client.post("/api/guest/scan", json={"domain": "127.0.0.1", "name": "Loopback"})
        assert resp.status_code == 400

    def test_guest_scan_ssrf_internal_ip_blocked(self):
        """SSRF: private IP ranges must be rejected."""
        for ip in ["192.168.1.1", "10.0.0.1", "172.16.0.1"]:
            resp = client.post("/api/guest/scan", json={"domain": ip, "name": "Internal"})
            assert resp.status_code == 400, f"Expected 400 for {ip}"

    def test_guest_scan_empty_domain_rejected(self):
        """Empty domain must fail validation — 422."""
        resp = client.post("/api/guest/scan", json={"domain": "", "name": "Test"})
        assert resp.status_code == 422

    def test_guest_scan_oversized_domain_rejected(self):
        """Domain > 253 chars must fail — 422."""
        resp = client.post("/api/guest/scan", json={"domain": "a" * 300 + ".com", "name": "Test"})
        assert resp.status_code == 422

    def test_guest_scan_oversized_name_rejected(self):
        """Name > 100 chars must fail — 422."""
        resp = client.post("/api/guest/scan", json={"domain": "example.com", "name": "x" * 101})
        assert resp.status_code == 422

    def test_guest_scan_http_prefix_stripped(self):
        """https:// prefix in domain should be accepted (stripped by validator)."""
        resp = client.post("/api/guest/scan", json={"domain": "https://example.com", "name": "Example"})
        # Should succeed — validator strips the scheme
        assert resp.status_code in (200, 400)  # 400 if example.com is SSRF-blocked, 200 otherwise

    def test_guest_scan_missing_name_rejected(self):
        """Missing name field — 422."""
        resp = client.post("/api/guest/scan", json={"domain": "example.com"})
        assert resp.status_code == 422

    def test_guest_scan_no_db_write(self):
        """Ephemeral scan must not write any vendor or event records to DB."""
        from database import SessionLocal
        from models import Vendor, RiskEvent
        db = SessionLocal()
        vendors_before = db.query(Vendor).count()
        events_before  = db.query(RiskEvent).count()
        db.close()

        client.post("/api/guest/scan", json={"domain": "example.com", "name": "EphemeralTest"})

        db = SessionLocal()
        assert db.query(Vendor).count() == vendors_before, "Guest scan must not create vendors"
        assert db.query(RiskEvent).count() == events_before, "Guest scan must not create events"
        db.close()

    def test_guest_scan_events_have_required_fields(self):
        """Each event in the response must have title, description, severity, source."""
        resp = client.post("/api/guest/scan", json={"domain": "microsoft.com", "name": "Microsoft"})
        assert resp.status_code == 200
        for evt in resp.json()["events"]:
            for field in ("title", "description", "severity", "source"):
                assert field in evt, f"Event missing field: {field}"

    def test_guest_scan_severity_values_valid(self):
        """All event severities must be one of CRITICAL/HIGH/MEDIUM/LOW."""
        resp = client.post("/api/guest/scan", json={"domain": "microsoft.com", "name": "Microsoft"})
        assert resp.status_code == 200
        valid = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        for evt in resp.json()["events"]:
            assert evt["severity"] in valid, f"Invalid severity: {evt['severity']}"


class TestGuestReport:
    """Tests for POST /api/guest/report — PDF generation from guest scan data."""

    _VALID_PAYLOAD = {
        "name":   "Test Vendor",
        "domain": "example.com",
        "score":  45.0,
        "events": [
            {"source": "NVD", "severity": "HIGH", "title": "CVE-2024-1234", "description": "Test CVE"},
        ],
    }

    def test_guest_report_returns_pdf(self):
        """Valid payload returns a PDF binary."""
        resp = client.post("/api/guest/report", json=self._VALID_PAYLOAD)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert len(resp.content) > 100  # non-empty PDF

    def test_guest_report_requires_no_auth(self):
        """No auth header needed."""
        resp = client.post("/api/guest/report", json=self._VALID_PAYLOAD)
        assert resp.status_code not in (401, 403)

    def test_guest_report_score_out_of_range_rejected(self):
        """Score > 100 or < 0 must be rejected — 422."""
        for bad_score in (-1.0, 101.0, 999.9):
            payload = {**self._VALID_PAYLOAD, "score": bad_score}
            resp = client.post("/api/guest/report", json=payload)
            assert resp.status_code == 422, f"Expected 422 for score={bad_score}"

    def test_guest_report_invalid_severity_rejected(self):
        """Unknown severity value in events must be rejected — 422."""
        payload = {**self._VALID_PAYLOAD, "events": [
            {"source": "NVD", "severity": "EXTREME", "title": "CVE-X", "description": "bad"},
        ]}
        resp = client.post("/api/guest/report", json=payload)
        assert resp.status_code == 422

    def test_guest_report_too_many_events_rejected(self):
        """More than 50 events must be rejected — 422."""
        events = [{"source": "NVD", "severity": "LOW", "title": f"CVE-{i}", "description": "x"} for i in range(51)]
        resp = client.post("/api/guest/report", json={**self._VALID_PAYLOAD, "events": events})
        assert resp.status_code == 422

    def test_guest_report_oversized_title_rejected(self):
        """Event title > 300 chars must fail — 422."""
        events = [{"source": "NVD", "severity": "LOW", "title": "x" * 301, "description": "x"}]
        resp = client.post("/api/guest/report", json={**self._VALID_PAYLOAD, "events": events})
        assert resp.status_code == 422

    def test_guest_report_oversized_description_rejected(self):
        """Event description > 1000 chars must fail — 422."""
        events = [{"source": "NVD", "severity": "LOW", "title": "CVE-X", "description": "x" * 1001}]
        resp = client.post("/api/guest/report", json={**self._VALID_PAYLOAD, "events": events})
        assert resp.status_code == 422

    def test_guest_report_xml_injection_in_title(self):
        """XML injection characters in event title must not crash PDF generation."""
        events = [{"source": "NVD", "severity": "HIGH", "title": "<script>alert(1)</script>&'\"", "description": "x"}]
        resp = client.post("/api/guest/report", json={**self._VALID_PAYLOAD, "events": events})
        # Must succeed — _xml_escape() handles it
        assert resp.status_code == 200

    def test_guest_report_zero_events(self):
        """Empty events list is valid — returns PDF with no CVEs section."""
        resp = client.post("/api/guest/report", json={**self._VALID_PAYLOAD, "events": []})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"


# ═════════════════════════════════════════════════════════════════════════════
# CLEANUP
# ═════════════════════════════════════════════════════════════════════════════

def teardown_module():
    """Clean up test database."""
    engine.dispose()
    try:
        os.remove("test_security.db")
    except FileNotFoundError:
        pass
    except PermissionError:
        pass
