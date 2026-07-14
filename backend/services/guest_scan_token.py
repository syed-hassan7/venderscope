"""Signed short-lived tokens binding guest PDF exports to server-side scan results."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import PyJWTError as JWTError

from services.auth_service import ALGORITHM, JWT_SECRET

GUEST_SCAN_TOKEN_TYPE = "guest_scan"
GUEST_SCAN_TOKEN_TTL_MINUTES = 15
MAX_EVENTS = 50


def create_guest_scan_token(
    *,
    name: str,
    domain: str,
    score: float,
    events: list[dict],
) -> str:
    """Embed scan result in a signed JWT so /guest/report cannot invent scores."""
    if len(events) > MAX_EVENTS:
        events = events[:MAX_EVENTS]
    expire = datetime.now(timezone.utc) + timedelta(minutes=GUEST_SCAN_TOKEN_TTL_MINUTES)
    payload = {
        "type": GUEST_SCAN_TOKEN_TYPE,
        "name": name,
        "domain": domain,
        "score": float(score),
        "events": events,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_guest_scan_token(token: str) -> dict:
    """
    Validate and return {name, domain, score, events}.
    Raises ValueError on any failure (caller maps to HTTP 400).
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired scan token") from exc

    if payload.get("type") != GUEST_SCAN_TOKEN_TYPE:
        raise ValueError("Invalid scan token type")

    name = payload.get("name")
    domain = payload.get("domain")
    score = payload.get("score")
    events = payload.get("events")

    if not isinstance(name, str) or not name or len(name) > 100:
        raise ValueError("Invalid scan token payload")
    if not isinstance(domain, str) or not domain or len(domain) > 253:
        raise ValueError("Invalid scan token payload")
    try:
        score_f = float(score)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid scan token payload") from exc
    if not (0.0 <= score_f <= 100.0):
        raise ValueError("Invalid scan token payload")
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError("Invalid scan token payload")

    return {
        "name": name,
        "domain": domain,
        "score": score_f,
        "events": events,
    }
