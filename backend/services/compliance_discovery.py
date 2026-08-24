import re
import os
import socket
import ipaddress
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote, urlparse, urlunparse
from services.quota import consume_search_units, refund_search_units, search_is_configured, current_quota_period

# ── SSRF protection ────────────────────────────────────────────────────────────
BLOCKED_PATTERNS = [
    r"^localhost$", r"^127\.", r"^10\.",
    r"^172\.(1[6-9]|2[0-9]|3[01])\.",
    r"^192\.168\.", r"^169\.254\.", r"^0\.", r"^::1$",
]

# Cloud metadata endpoints not covered by the regex blocklist above
BLOCKED_HOSTNAMES = {
    "metadata.google.internal",    # GCP metadata
    "metadata.azure.com",          # Azure metadata (hostname variant)
    "100.100.100.200",             # Alibaba Cloud metadata
    "0.0.0.0",
}

HEADERS = {"User-Agent": "VenderScope/1.0 Compliance Discovery Bot (security research)"}

# ── Document link patterns ─────────────────────────────────────────────────────
DOC_PATTERNS = {
    "privacy_policy": [
        "/privacy", "/privacy-policy", "/privacy_policy", "/legal/privacy",
        "/legal/privacy-policy", "/en/privacy", "/data-protection", "/gdpr",
        "/privacy-notice", "privacy",
    ],
    "terms": [
        "/terms", "/terms-of-service", "/terms-of-use", "/tos",
        "/legal/terms", "/legal/terms-of-service", "/en/terms", "terms",
    ],
    "security": [
        "/security", "/security-policy", "/security.txt", "/legal/security",
        "/vulnerability-disclosure", "security",
    ],
    "cookie_policy": ["/cookies", "/cookie-policy", "/cookie_policy", "cookies"],
}

# Paths probed directly when link extraction finds nothing for a doc type.
# HEAD request only — no body fetched until a 200 is confirmed.
DOC_PROBE_PATHS = {
    "privacy_policy": [
        "/privacy", "/privacy-policy", "/privacy_policy", "/legal/privacy",
        "/legal/privacy-policy", "/en/privacy", "/data-protection", "/gdpr",
        "/privacy-notice", "/legal",
    ],
    "terms": [
        "/terms", "/terms-of-service", "/terms-of-use", "/tos",
        "/legal/terms", "/legal/terms-of-service", "/en/terms",
    ],
    "security": [
        "/security", "/security-policy", "/legal/security",
        "/vulnerability-disclosure",
    ],
    "cookie_policy": ["/cookies", "/cookie-policy", "/cookie_policy"],
}

# ── Trust centre URL patterns ──────────────────────────────────────────────────
TRUST_PATTERNS = [
    "trust.{domain}", "security.{domain}", "compliance.{domain}",
    "{domain}/trust", "{domain}/trust-center", "{domain}/trust-centre",
    "{domain}/security", "{domain}/compliance",
]

# ── Certification keyword sets (page scrape stage) ────────────────────────────
CERT_KEYWORDS = {
    "iso_27001": [
        "iso 27001", "iso27001", "iso/iec 27001", "information security management",
        "isms certified", "certified to iso 27001", "iso 27001:2022", "iso/iec 27001:2022",
    ],
    "soc2": [
        "soc 2", "soc2", "soc type 2", "soc type ii", "aicpa soc",
        "service organization control", "soc 2 type 2", "soc ii",
        "aicpa trust", "trust services criteria",
    ],
    "gdpr": [
        "gdpr compliant", "gdpr compliance", "general data protection",
        "data protection regulation", "uk gdpr", "data controller", "lawful basis",
    ],
    "cyber_essentials": ["cyber essentials", "cyber essentials plus"],
    "pci_dss":          ["pci dss", "pci-dss", "payment card industry"],
    "dpa": [
        "data processing agreement", "data processing addendum", "dpa",
        "controller to processor", "sub-processor agreement",
        "article 28", "gdpr article 28",
    ],
}

# ── Google search query templates (web fallback stage) ────────────────────────
CERT_SEARCH_QUERIES = {
    "iso_27001":        ["{name} ISO 27001 certified", "{domain} ISO 27001 certificate"],
    "soc2":             ["{name} SOC 2 report", "{domain} SOC 2 type II"],
    "gdpr":             ["{name} GDPR compliant", "{domain} GDPR compliance"],
    "cyber_essentials": ["{name} Cyber Essentials certified", "{domain} Cyber Essentials"],
    "pci_dss":          ["{name} PCI DSS compliant", "{domain} PCI DSS"],
    "dpa": [
        '"{name}" "data processing agreement"',
        '"{name}" "DPA" site:{domain}',
        "{name} data processing agreement GDPR",
        "{domain} data processing addendum",
    ],
}

# ── Third-party attribution patterns ─────────────────────────────────────────
# Matches sentences where a cert keyword is attributed to the vendor's infra/
# suppliers rather than the vendor itself.  Used to detect "our data centres
# are ISO 27001 certified" vs "we hold ISO 27001 certification".
THIRD_PARTY_PATTERNS = [
    # "third-party / third parties ... certified / cert keyword" (100-char clause limit)
    r"third[- ]?part(?:y|ies)\b.{0,100}\b(iso.?27001|soc\s*2|pci|cyber\s*essentials|certified)",
    # "infrastructure / data centre / cloud provider ... certified"
    r"\b(infrastructure|data[- ]?cent(?:er|re)|hosting\s+provider|cloud\s+provider)\b.{0,150}\b(certified|iso.?27001|soc\s*2|pci)",
    # "partners / providers / vendors are certified"
    r"\b(partners?|providers?|vendors?|suppliers?)\s+(are|is|that\s+are|which\s+are|who\s+are)\b.{0,150}\b(certified|iso.?27001|soc\s*2|pci)",
    # cert keyword then "infrastructure / partner / provider" in same window
    r"\b(iso.?27001|soc\s*2|pci\s*dss|cyber\s*essentials)\b.{0,150}\b(infrastructure|data[- ]?cent(?:er|re)|hosting|cloud\s+provider|partner|vendor)\b",
    # "relies on / hosted by / powered by ... certified"
    r"\b(relies?\s+on|built\s+on|powered\s+by|operated\s+by|hosted\s+by|runs?\s+on)\b.{0,150}\b(certified|iso.?27001|soc\s*2|pci)\b",
    # "all of the third parties ... [cert]" — cert keyword required in same clause
    r"\ball\s+of\s+(the\s+)?(our\s+)?third[- ]?part(?:y|ies)\b.{0,150}\b(certified|iso.?27001|soc\s*2|pci|cyber\s*essentials)",
    # "core infrastructure" near cert keyword
    r"\bcore\s+infrastructure\b.{0,100}\b(iso.?27001|soc\s*2|certified)\b",
]

# ── Credible certification body domains ───────────────────────────────────────
CREDIBLE_DOMAINS = [
    "bsigroup.com", "schellman.com", "aicpa.org", "ukas.com",
    "iasme.co.uk", "ncsc.gov.uk", "pcisecuritystandards.org",
    "certified.iso.org", "tuvsud.com", "dnv.com",
]

# ── Security contact email prefixes ───────────────────────────────────────────
SECURITY_EMAIL_PREFIXES = ["security", "privacy", "dpo", "compliance", "legal", "infosec", "gdpr"]

MAX_RESPONSE_BYTES = 1_048_576  # 1 MB — prevents oversized pages from spiking RSS

# Hard cap on net Tavily units one run_compliance_discovery() call (one vendor,
# one scan) can spend. Worst case without this — 6 certs x up to 4 query
# templates each, plus 7 security-contact prefixes — is ~21 units for a single
# vendor, not the ~6 ESTIMATED_SCAN_COST assumes. Without a per-scan ceiling,
# a handful of scan-all calls on a vendor-heavy account could burn the entire
# shared monthly Tavily budget in minutes. Matches ESTIMATED_SCAN_COST
# (services/quota.py) so the "estimated full scans remaining" figure it drives
# reflects a real ceiling, not an average.
MAX_SEARCH_UNITS_PER_SCAN = 6

RELEVANT_PAGE_HINTS = [
    "trust", "security", "privacy", "legal", "compliance", "gdpr",
    "dpa", "data-processing", "data-processing-agreement", "data-processing-addendum",
    "subprocessor", "sub-processor", "terms", "cookie", "certificate", "certification",
    "soc", "iso", "attestation",
]

# Never legitimate cert/doc evidence regardless of whose domain hosts them —
# job listings and marketplace/directory profile pages describe or list an
# entity, they don't attest on its behalf. (e.g. a scan of a jobs-marketplace
# vendor site picking up /companies/<other-company>/ as "evidence".)
JUNK_PATH_MARKERS = [
    "/jobs/", "/job/", "/careers/", "/career/", "/hiring/", "/vacancy/",
    "/vacancies/", "/apply/", "/recruiting/", "/positions/",
    "/companies/", "/company/", "/directory/", "/listing/", "/profile/",
]
JUNK_TITLE_MARKERS = ["hiring", "job description", "apply now", "join our team"]

# Generic third-party explainer content — only disqualifying when the result
# is NOT on the vendor's own domain and NOT a CREDIBLE_DOMAINS body, since a
# vendor's own blog/article legitimately announces its own compliance posture.
GENERIC_CONTENT_PATH_MARKERS = [
    "/blog/", "/articles/", "/article/", "/glossary/", "/resources/",
    "/resource/", "/learn/", "/guides/", "/guide/",
]
GENERIC_CONTENT_TITLE_MARKERS = ["what is", "guide to", "definition of", "explained"]


def _has_marker(haystack: str, markers: list[str]) -> bool:
    return any(m in haystack for m in markers)


def _pattern_matches(pattern: str, haystack: str) -> bool:
    """
    Word-boundary match so short DOC_PATTERNS/RELEVANT_PAGE_HINTS tokens
    ("soc", "iso", "dpa") only match whole path segments/words instead of
    colliding with unrelated substrings ("social", "isolated").
    """
    boundary = r"(?:^|[/_\-\s.])"
    end = r"(?:$|[/_\-\s.?#])"
    return re.search(boundary + re.escape(pattern.strip("/")) + end, haystack) is not None


MAX_DISCOVERY_PAGES = 8


def _validate_and_resolve(hostname: str) -> str | None:
    """
    Full SSRF safety check on `hostname` — returns its resolved IP if safe, else None.
    Single DNS resolution shared by the safety check and the pinned fetch that follows
    it (see _pinned_get). Checking here and then letting a later, separate call
    re-resolve DNS on its own would reopen a DNS-rebinding window: an attacker-
    controlled domain (any vendor domain a user adds) could pass this check pointing
    at a public IP, then flip to 169.254.169.254 / 127.0.0.1 / an internal host by the
    time the real request resolves DNS again.
    """
    clean = hostname.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    # URL-decode to prevent bypass via 127%2E0%2E0%2E1
    clean = unquote(clean)

    # Check cloud metadata endpoints not covered by regex patterns
    if clean.lower() in BLOCKED_HOSTNAMES:
        return None

    # Check against regex blocklist
    if any(re.match(p, clean) for p in BLOCKED_PATTERNS):
        return None

    # Check for decimal/hex/octal IP notation (e.g. 2130706433 → 127.0.0.1)
    try:
        ip_obj = ipaddress.ip_address(int(clean))
        if ip_obj.is_private or ip_obj.is_loopback:
            return None
        return clean  # already a literal IP — nothing left to resolve
    except (ValueError, TypeError):
        pass  # Not a numeric IP, continue to DNS resolution

    # Resolve DNS and check the resolved IP — prevents DNS rebinding attacks
    try:
        resolved_ip = socket.gethostbyname(clean)
        try:
            ip_obj = ipaddress.ip_address(resolved_ip)
            # ipaddress handles is_private, is_loopback, is_link_local natively
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                return None
            # Block IPv4-mapped IPv6 addresses (::ffff:127.0.0.1 etc)
            if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
                if ip_obj.ipv4_mapped.is_private or ip_obj.ipv4_mapped.is_loopback:
                    return None
        except ValueError:
            return None  # Unparseable IP → block
    except socket.gaierror:
        return None

    return resolved_ip


def _is_safe_domain(domain: str) -> bool:
    return _validate_and_resolve(domain) is not None


def _pinned_get(hostname: str, ip: str, port: int, scheme: str, path: str, timeout: int):
    """
    Makes exactly one GET, connecting directly to the pre-validated `ip` instead of
    letting the HTTP client re-resolve `hostname` (which is what would reopen the
    rebinding window _validate_and_resolve exists to close). TLS SNI and certificate
    verification still use `hostname`, so this doesn't weaken cert checking — it only
    pins which address the socket actually connects to.
    Returns (status_code, headers, body_bytes) — headers is urllib3's
    case-insensitive HTTPHeaderDict (HTTP header names are case-insensitive per
    spec; a plain dict() here would silently miss e.g. a lowercase `location:`
    header from a server that doesn't title-case it).
    """
    pool_cls = urllib3.HTTPSConnectionPool if scheme == "https" else urllib3.HTTPConnectionPool
    kwargs = {"timeout": timeout, "retries": False}
    if scheme == "https":
        kwargs["assert_hostname"] = hostname
        kwargs["server_hostname"] = hostname
    with pool_cls(ip, port=port, **kwargs) as pool:
        r = pool.request(
            "GET", path,
            headers={**HEADERS, "Host": hostname},
            redirect=False,
            preload_content=False,
        )
        try:
            body = r.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES]
            return r.status, r.headers, body
        finally:
            r.release_conn()


def _fetch_page(url: str, timeout: int = 8) -> str | None:
    max_hops = 3
    current_url = url
    for _ in range(max_hops):
        parsed = urlparse(current_url)
        hostname = parsed.hostname
        if not hostname:
            return None
        ip = _validate_and_resolve(hostname)
        if not ip:
            return None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        try:
            status, headers, body = _pinned_get(hostname, ip, port, parsed.scheme, path, timeout)
        except Exception:
            return None
        if status == 200:
            return body.decode("utf-8", errors="replace")
        if status in (301, 302, 303, 307, 308):
            location = headers.get("Location", "")
            if not location:
                return None
            # Redirect target is re-validated (and re-pinned) at the top of the
            # next loop iteration via _validate_and_resolve — no separate check
            # needed here, that would just be a second, discarded DNS lookup.
            current_url = urljoin(current_url, location)
            continue
        return None
    return None


def _normalise_url(url: str) -> str:
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean).rstrip("/")


def _is_same_vendor_site(url: str, base: str) -> bool:
    host = urlparse(url).netloc.lower()
    base = base.lower()
    return host in {base, f"www.{base}"} or host.endswith(f".{base}")


def _extract_relevant_links(html: str, base_url: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(" ", strip=True).lower()
        full = _normalise_url(urljoin(base_url, href))
        if not full.startswith("http"):
            continue
        if not _is_same_vendor_site(full, base):
            continue
        if _has_marker(full.lower(), JUNK_PATH_MARKERS):
            continue
        haystack = f"{href.lower()} {text}"
        if any(_pattern_matches(hint, haystack) for hint in RELEVANT_PAGE_HINTS):
            candidates.append(full)
    return candidates


def _find_doc_links(html: str, base_url: str) -> dict:
    soup  = BeautifulSoup(html, "html.parser")
    found = {}
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        text = link.get_text(strip=True).lower()
        full = _normalise_url(urljoin(base_url, link["href"]))
        if _has_marker(full.lower(), JUNK_PATH_MARKERS):
            continue
        for doc_type, patterns in DOC_PATTERNS.items():
            if doc_type in found:
                continue
            if any(_pattern_matches(p, href) or _pattern_matches(p, text) for p in patterns):
                found[doc_type] = full
    return found


def _probe_doc_paths(base: str, found: dict) -> dict:
    """
    Direct-path fallback: for any doc type not found by link extraction,
    probe known paths with a HEAD request and take the first 200 response.
    """
    result = dict(found)
    for doc_type, paths in DOC_PROBE_PATHS.items():
        if doc_type in result:
            continue
        for path in paths:
            url = f"https://{base}{path}"
            try:
                r = requests.head(url, headers=HEADERS, timeout=5, allow_redirects=True)
                if r.status_code == 200:
                    result[doc_type] = url
                    break
            except Exception:
                continue
    return result


def _find_docs_in_sitemap(base: str, found: dict) -> dict:
    """
    Parse sitemap.xml / sitemap_index.xml for missing doc type URLs.
    Only fills gaps — does not overwrite already-found entries.
    """
    result = dict(found)
    for path in ["/sitemap.xml", "/sitemap_index.xml"]:
        if len(result) == len(DOC_PATTERNS):
            break
        content = _fetch_page(f"https://{base}{path}", timeout=8)
        if not content:
            continue
        urls = re.findall(r"<loc>(https?://[^<]+)</loc>", content)
        for u in urls:
            u_lower = u.lower()
            if _has_marker(u_lower, JUNK_PATH_MARKERS):
                continue
            for doc_type, patterns in DOC_PATTERNS.items():
                if doc_type in result:
                    continue
                if any(_pattern_matches(p, u_lower) for p in patterns if p.startswith("/")):
                    result[doc_type] = u
    return result


def _collect_discovery_pages(base: str, home_url: str, home_html: str | None, doc_links: dict, trust: dict | None) -> dict[str, str]:
    pages: dict[str, str] = {}

    def add_page(url: str | None, html: str | None = None):
        if not url or len(pages) >= MAX_DISCOVERY_PAGES:
            return
        clean_url = _normalise_url(url)
        if clean_url in pages:
            return
        if not _is_same_vendor_site(clean_url, base):
            return
        pages[clean_url] = html if html is not None else (_fetch_page(clean_url) or "")

    add_page(home_url, home_html)
    for url in doc_links.values():
        add_page(url)
    if trust:
        add_page(trust.get("url"))

    seed_pages = [(url, html) for url, html in pages.items() if html]
    for source_url, source_html in seed_pages:
        for link in _extract_relevant_links(source_html, source_url or home_url, base):
            add_page(link)
            if len(pages) >= MAX_DISCOVERY_PAGES:
                break
        if len(pages) >= MAX_DISCOVERY_PAGES:
            break

    return pages


def _normalise_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    return re.sub(r"\s+", " ", text)


def _check_trust_centre(domain: str) -> dict | None:
    base = domain.replace("https://", "").replace("http://", "").rstrip("/")
    for pattern in TRUST_PATTERNS:
        url = pattern.format(domain=base)
        if not url.startswith("http"):
            url = f"https://{url}"
        try:
            r = requests.head(url, headers=HEADERS, timeout=6, allow_redirects=True)
            if r.status_code in (200, 301, 302):
                body = _fetch_page(url, timeout=6)
                return {"url": url, "accessible": bool(body and len(body) > 500)}
        except Exception:
            continue
    return None


def _is_third_party_attribution(full_text: str, keyword: str) -> bool:
    """
    Returns True when every text segment containing `keyword` attributes the cert
    to the vendor's infrastructure/suppliers rather than the vendor itself.

    Splits on HTML tags AND sentence-ending punctuation so adjacent list items /
    paragraphs never bleed into each other's pattern check.  A ±N char window
    was unreliable when two cert mentions sat in adjacent <li> elements.

    Only returns True when third-party evidence exists and NO direct evidence does,
    so "we are ISO 27001 certified AND our data centres are ISO 27001 certified"
    still resolves to found (direct evidence wins).
    """
    # Split raw HTML into isolated text segments on tags and sentence boundaries
    segments = [
        s.strip() for s in re.split(r'<[^>]+>|[.!?\n]', full_text)
        if keyword in s and len(s.strip()) > 15
    ]
    if not segments:
        return False

    has_direct = False
    has_third_party = False

    for seg in segments:
        if any(re.search(p, seg, re.IGNORECASE) for p in THIRD_PARTY_PATTERNS):
            has_third_party = True
        else:
            has_direct = True

    return has_third_party and not has_direct


def _scrape_stage(full_text: str) -> dict:
    """Stage 1 — keyword search across all fetched page content."""
    results = {}
    for cert, keywords in CERT_KEYWORDS.items():
        matched_kw = next((kw for kw in keywords if kw in full_text), None)
        if matched_kw is None:
            results[cert] = "not_found"
        elif _is_third_party_attribution(full_text, matched_kw):
            results[cert] = "third_party"
        else:
            results[cert] = "found"
    return results


def _web_search(query: str, quota_state: dict | None = None, include_domains: list[str] | None = None) -> list[dict]:
    """Fires a single Tavily search query. Returns [] on failure or missing key."""
    if not search_is_configured():
        return []

    reserved_unit = False
    period = None
    if quota_state is not None:
        if not quota_state.get("enabled", True):
            return []
        if quota_state.get("used", 0) >= MAX_SEARCH_UNITS_PER_SCAN:
            return []
        period = current_quota_period()
        if not consume_search_units(1, period=period):
            quota_state["enabled"] = False
            quota_state["exhausted"] = True
            return []
        reserved_unit = True

    api_key = os.getenv("TAVILY_API_KEY")
    payload = {"query": query, "max_results": 5, "chunks_per_source": 1}
    if include_domains:
        payload["include_domains"] = include_domains
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=8,
        )
        if r.status_code == 200:
            if quota_state is not None and reserved_unit:
                quota_state["used"] = quota_state.get("used", 0) + 1
            return [
                {"title": item.get("title", ""), "link": item.get("url", ""), "snippet": item.get("content", "")}
                for item in r.json().get("results", [])
            ]
        print(f"[Tavily] {r.status_code}: {r.text[:300]}")
    except Exception as e:
        print(f"[Tavily] Request failed: {e}")
    if reserved_unit:
        refund_search_units(1, period=period)
    return []


def _host_matches(link: str, domain: str) -> bool:
    """Exact-or-subdomain host match, not substring — 'vendor.com' must not
    match a lookalike like 'vendor.com.evil.ru' or 'notvendor.com'."""
    host = (urlparse(link).hostname or "").lower()
    domain = domain.lower()
    return bool(host) and (host == domain or host.endswith(f".{domain}"))


def _is_vendor_relevant(item: dict, name: str, base: str) -> bool:
    """True when a search result is actually tied to this vendor: a credible
    certifying-body domain, the vendor's own domain, or the vendor's name
    mentioned in the result text."""
    link = item.get("link", "")
    text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
    if any(_host_matches(link, d) for d in CREDIBLE_DOMAINS):
        return True
    if _host_matches(link, base):
        return True
    name_tokens = [t for t in re.split(r"\W+", name.lower()) if len(t) > 2]
    return bool(name_tokens) and all(t in text for t in name_tokens)


def _is_junk_result(item: dict, base: str) -> bool:
    """True when a result's shape says 'not an attestation' regardless of a
    keyword match — a job posting listing the cert as a skill requirement, or
    (off the vendor's own domain / a credible body) generic explainer content
    that never actually asserts anything about this vendor."""
    link = item.get("link", "")
    text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
    if _has_marker(link.lower(), JUNK_PATH_MARKERS) or _has_marker(text, JUNK_TITLE_MARKERS):
        return True
    is_own_domain_or_credible = _host_matches(link, base) or any(_host_matches(link, d) for d in CREDIBLE_DOMAINS)
    if not is_own_domain_or_credible:
        if _has_marker(link.lower(), GENERIC_CONTENT_PATH_MARKERS) or _has_marker(text, GENERIC_CONTENT_TITLE_MARKERS):
            return True
    return False


def _result_is_credible(items: list[dict], cert_keywords: list[str], name: str, base: str) -> dict | None:
    """
    Returns the first search result that both (a) mentions a cert keyword,
    (b) isn't shaped like junk (job posting / marketplace listing / generic
    third-party explainer), and (c) is actually tied to this vendor (credible
    body domain, vendor's own domain, or vendor name mentioned). No keyword-
    only fallback — a result that fails either gate is not evidence.
    """
    for item in items:
        text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
        if not any(kw in text for kw in cert_keywords):
            continue
        if _is_junk_result(item, base):
            continue
        if _is_vendor_relevant(item, name, base):
            return item
    return None


def _web_search_stage(vendor_name: str, domain: str, scrape_results: dict, quota_state: dict | None = None) -> dict:
    """
    Stage 2 — web search fallback (Tavily).
    - "found"       → already confirmed on-site, skip search.
    - "third_party" → run search to try to find direct cert evidence; if search
                      also only surfaces third-party attribution, preserve that status.
    - "not_found"   → run search as before; apply attribution check to snippets.
    """
    base     = domain.replace("https://", "").replace("http://", "").rstrip("/")
    enriched = {}

    for cert, status in scrape_results.items():
        if status == "found":
            enriched[cert] = {"status": "found", "source": "site"}
            continue

        queries = CERT_SEARCH_QUERIES.get(cert, [])
        match   = None
        for q_template in queries:
            # Tavily has no "site:" search operator — a literal "site:{domain}"
            # in the query string is just noise. Strip it and scope the search
            # via Tavily's own include_domains param instead.
            if "site:{domain}" in q_template:
                query = q_template.replace(" site:{domain}", "").format(name=vendor_name, domain=base)
                items = _web_search(query, quota_state, include_domains=[base])
            else:
                query = q_template.format(name=vendor_name, domain=base)
                items = _web_search(query, quota_state)
            print(f"[Compliance] Web search: {query}")
            match = _result_is_credible(items, CERT_KEYWORDS[cert], vendor_name, base)
            if match:
                break

        if match:
            # Attribution-check the snippet before calling it "found"
            snippet    = (match.get("title", "") + " " + match.get("snippet", "")).lower()
            kw_in_snip = next((kw for kw in CERT_KEYWORDS[cert] if kw in snippet), None)
            is_tp      = (
                kw_in_snip is not None
                and any(re.search(p, snippet, re.IGNORECASE) for p in THIRD_PARTY_PATTERNS)
            )
            enriched[cert] = {
                "status": "third_party" if is_tp else "found",
                "source": "external",
                "url":    match.get("link", ""),
                "title":  match.get("title", ""),
            }
        else:
            # No web evidence found — preserve third_party from scrape if that's what we had
            enriched[cert] = {
                "status": status if status == "third_party" else "not_found",
                "source": "site" if status == "third_party" else None,
            }

    return enriched


def _find_security_contact(domain: str, scraped_pages: list[str], use_web_search: bool = True) -> dict | None:
    """
    1. Check security.txt (RFC 9116) — most authoritative.
    2. Scrape already-fetched pages for emails matching known prefixes.
    3. Web search fallback (only if use_web_search=True).
    Never fabricates — only returns confirmed findings.
    """
    base = domain.replace("https://", "").replace("http://", "").rstrip("/")

    # Stage 1 — security.txt
    for path in ["/.well-known/security.txt", "/security.txt"]:
        content = _fetch_page(f"https://{base}{path}")
        if content:
            match = re.search(r"Contact:\s*(mailto:)?([^\s]+@[^\s]+)", content, re.IGNORECASE)
            if match:
                return {"email": match.group(2).strip(), "verified": True, "source": "security.txt"}

    # Stage 2 — scrape pages already fetched
    combined = " ".join(filter(None, scraped_pages)).lower()
    for prefix in SECURITY_EMAIL_PREFIXES:
        pattern = rf"{prefix}@(?:www\.)?{re.escape(base)}"
        if re.search(pattern, combined, re.IGNORECASE):
            return {"email": f"{prefix}@{base}", "verified": True, "source": "site"}

    # Stage 3 — web search fallback (skipped if quota exhausted)
    if use_web_search:
        for prefix in SECURITY_EMAIL_PREFIXES:
            query = f'"{prefix}@{base}"'
            items = _web_search(query)
            for item in items:
                text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
                if f"{prefix}@{base}" in text:
                    return {"email": f"{prefix}@{base}", "verified": True, "source": "web_search"}

    return None


def _find_security_contact_with_quota(
    domain: str,
    scraped_pages: list[str],
    quota_state: dict | None = None,
) -> dict | None:
    """
    Same as _find_security_contact but consumes search quota incrementally when needed.
    """
    base = domain.replace("https://", "").replace("http://", "").rstrip("/")

    for path in ["/.well-known/security.txt", "/security.txt"]:
        content = _fetch_page(f"https://{base}{path}")
        if content:
            match = re.search(r"Contact:\s*(mailto:)?([^\s]+@[^\s]+)", content, re.IGNORECASE)
            if match:
                return {"email": match.group(2).strip(), "verified": True, "source": "security.txt"}

    combined = " ".join(filter(None, scraped_pages)).lower()
    for prefix in SECURITY_EMAIL_PREFIXES:
        pattern = rf"{prefix}@(?:www\.)?{re.escape(base)}"
        if re.search(pattern, combined, re.IGNORECASE):
            return {"email": f"{prefix}@{base}", "verified": True, "source": "site"}

    if quota_state is not None and quota_state.get("enabled", True):
        for prefix in SECURITY_EMAIL_PREFIXES:
            query = f'"{prefix}@{base}"'
            items = _web_search(query, quota_state)
            for item in items:
                text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
                if f"{prefix}@{base}" in text:
                    return {"email": f"{prefix}@{base}", "verified": True, "source": "web_search"}

    return None


def run_compliance_discovery(domain: str, vendor_name: str = "", use_web_search: bool = True) -> dict:
    """
    Main entry point. Two-stage cert discovery:
      1. Keyword scrape of vendor's own pages (always runs)
      2. Web search fallback (skipped when use_web_search=False / quota exhausted)
    """
    if not _is_safe_domain(domain):
        print(f"[Compliance] Blocked unsafe domain: {domain}")
        return {}

    base     = domain.replace("https://", "").replace("http://", "").rstrip("/")
    name     = vendor_name or base
    home_url = f"https://{base}"

    print(f"[Compliance] Starting {'Full Intelligence' if use_web_search else 'Standard'} "
          f"discovery for {name} ({base})...")

    # ── Fetch pages ──────────────────────────────────────────────────────────
    home_html    = _fetch_page(home_url) or _fetch_page(f"https://www.{base}")
    doc_links    = _find_doc_links(home_html, home_url) if home_html else {}

    # Fallback 1: probe known paths directly for any missing doc types
    if len(doc_links) < len(DOC_PATTERNS):
        doc_links = _probe_doc_paths(base, doc_links)

    # Fallback 2: sitemap.xml for any still-missing doc types
    if len(doc_links) < len(DOC_PATTERNS):
        doc_links = _find_docs_in_sitemap(base, doc_links)

    trust      = _check_trust_centre(base)
    pages      = _collect_discovery_pages(base, home_url, home_html, doc_links, trust)
    quota_state = {"enabled": use_web_search, "used": 0, "exhausted": False}

    # ── Stage 1: scrape ──────────────────────────────────────────────────────
    full_text      = " ".join(_normalise_text(html) for html in pages.values() if html)
    scrape_results = _scrape_stage(full_text)

    # ── Stage 2: web search fallback (skipped if quota exhausted) ────────────
    if use_web_search:
        certifications = _web_search_stage(name, base, scrape_results, quota_state)
    else:
        print(f"[Compliance] Standard Scan — skipping web search for {base}")
        certifications = {
            k: {"status": v, "source": "site" if v in ("found", "third_party") else None}
            for k, v in scrape_results.items()
        }

    # ── Security contact ─────────────────────────────────────────────────────
    # Move refs to list then clear dict — reduces peak HTML copies from 3x to 1x
    scraped_pages = list(pages.values())
    pages.clear()
    contact       = _find_security_contact_with_quota(base, scraped_pages, quota_state)

    found_count = sum(1 for v in certifications.values() if v["status"] == "found")
    tp_count    = sum(1 for v in certifications.values() if v["status"] == "third_party")
    ext_count   = sum(1 for v in certifications.values() if v.get("source") == "external")
    print(f"[Compliance] Done — {len(doc_links)} docs, {len(scraped_pages)} pages checked, "
          f"{found_count} certs direct, {tp_count} via infra partners "
          f"({ext_count} via web search), {quota_state['used']} search unit(s) used, "
          f"trust centre: {'yes' if trust else 'no'}, "
          f"contact: {'verified' if contact else 'none'}")

    return {
        "documents":        doc_links,
        "trust_centre":     trust,
        "certifications":   certifications,
        "security_contact": contact,
        "search_units_used": quota_state["used"],
    }
