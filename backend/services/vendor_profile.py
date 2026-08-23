from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from services.compliance_discovery import _is_safe_domain, _fetch_page as _fetch

# Auth patterns — ordered most-specific to least-specific so the first match wins
AUTH_PATTERNS = [
    ("SSO (SAML 2.0)",  ["saml 2.0", "saml2.0", "saml-based sso", "saml-based authentication"]),
    ("SAML",            ["saml"]),
    ("OpenID Connect",  ["openid connect", "oidc"]),
    ("SSO",             ["single sign-on", "single sign on"]),
    ("OAuth 2.0",       ["oauth 2.0", "oauth2.0"]),
    ("OAuth",           ["oauth"]),
    ("Passwordless",    ["passwordless", "magic link", "passkey", "webauthn", "fido2"]),
    ("Social Login",    [
        "sign in with google", "log in with google", "login with google",
        "continue with google", "sign in with github", "continue with github",
        "sign in with microsoft", "continue with microsoft",
        "google oauth", "github oauth",
    ]),
    ("Okta",            ["okta"]),
    ("Auth0",           ["auth0"]),
    ("Password-based",  [
        "email and password", "username and password", "email/password",
        "sign in with email", "log in with email",
    ]),
]

TWO_FA_KEYWORDS = [
    "two-factor", "two factor", "2fa", "2-fa",
    "mfa", "multi-factor", "multifactor",
    "totp", "authenticator app", "google authenticator", "authy",
    "sms verification", "sms code", "one-time password", "one-time code",
    "time-based one", "hardware key", "yubikey", "security key",
]

LOGIN_PATHS = [
    "/login", "/signin", "/sign-in",
    "/auth/login", "/users/sign_in", "/app/login",
]

ICON_REL_TOKENS = ("icon", "shortcut icon", "apple-touch-icon", "mask-icon")


def _to_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()


def _meta_description(soup: BeautifulSoup) -> str | None:
    for attr, val in [("property", "og:description"), ("name", "description")]:
        tag = soup.find("meta", attrs={attr: val})
        if tag:
            content = tag.get("content", "").strip()
            if len(content) > 20:
                return content
    return None


def _icon_score(rel: str, href: str, sizes: str) -> tuple[int, int, int]:
    rel = (rel or "").lower()
    href = (href or "").lower()
    sizes = (sizes or "").lower()

    primary = 0
    if "apple-touch-icon" in rel:
        primary = 4
    elif rel.strip() == "icon":
        primary = 3
    elif "shortcut icon" in rel:
        primary = 2
    elif "mask-icon" in rel:
        primary = 1

    size_value = 0
    for token in sizes.split():
        if "x" not in token:
            continue
        try:
            width, height = token.split("x", 1)
            size_value = max(size_value, min(int(width), int(height)))
        except ValueError:
            continue

    extension_bias = 1 if href.endswith(".png") else 0
    return (primary, size_value, extension_bias)


def _discover_logo_url(base: str, home_url: str, soup: BeautifulSoup) -> str | None:
    candidates: list[tuple[tuple[int, int, int], str]] = []

    for link in soup.find_all("link", href=True):
        rel_attr = link.get("rel") or []
        rel = " ".join(rel_attr).strip().lower() if isinstance(rel_attr, list) else str(rel_attr).strip().lower()
        if not any(token in rel for token in ICON_REL_TOKENS):
            continue
        full = urljoin(home_url, link["href"])
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc.lower() not in {base.lower(), f"www.{base.lower()}"} and not parsed.netloc.lower().endswith(f".{base.lower()}"):
            continue
        candidates.append((_icon_score(rel, full, link.get("sizes", "")), full))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]
    return None


def _detect_auth(text: str) -> str | None:
    for label, keywords in AUTH_PATTERNS:
        if any(kw in text for kw in keywords):
            return label
    return None


def _detect_2fa(text: str) -> str | None:
    return "Yes" if any(kw in text for kw in TWO_FA_KEYWORDS) else None


def discover_vendor_profile(domain: str) -> dict:
    """
    Passively discovers three fields for a vendor:
      - description : 1-2 line summary from homepage meta tags
      - auth_method : e.g. "SSO (SAML 2.0)", "OAuth 2.0", "Password-based"
      - two_factor  : "Yes" or None (not detected — we never assert "No")

    Never raises — returns partial results on any failure.
    """
    base   = domain.replace("https://", "").replace("http://", "").rstrip("/")
    result = {"description": None, "logo_url": None, "auth_method": None, "two_factor": None}

    if not _is_safe_domain(base):
        print(f"[Profile] Blocked unsafe domain: {base}")
        return result
    try:
        home_url = f"https://{base}"
        home_html = _fetch(home_url)
        if not home_html:
            home_url = f"https://www.{base}"
            home_html = _fetch(home_url)
        if not home_html:
            print(f"[Profile] Could not fetch homepage for {base}")
            return result

        home_soup = BeautifulSoup(home_html, "html.parser")
        home_html = None  # Release raw HTML — one parse covers all three extractions
        result["description"] = _meta_description(home_soup)
        result["logo_url"] = _discover_logo_url(base, home_url, home_soup)
        home_text = home_soup.get_text(" ", strip=True).lower()
        home_soup = None  # Release parse tree before next fetches

        # Fetch login page — best source for auth method signals
        login_text = ""
        for path in LOGIN_PATHS:
            html = _fetch(f"https://{base}{path}", timeout=5)
            if html:
                login_text = _to_text(html)
                break

        # Security page — best source for 2FA signals
        sec_html  = _fetch(f"https://{base}/security", timeout=5)
        sec_text  = _to_text(sec_html) if sec_html else ""

        combined = home_text + " " + login_text + " " + sec_text

        result["auth_method"] = _detect_auth(combined)
        result["two_factor"]  = _detect_2fa(combined)

        print(f"[Profile] {base} → auth={result['auth_method']}, "
              f"2fa={result['two_factor']}, desc={'yes' if result['description'] else 'no'}, "
              f"logo={'yes' if result['logo_url'] else 'no'}")

    except Exception as e:
        print(f"[Profile] Error for {domain}: {e}")

    return result
