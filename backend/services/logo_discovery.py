import json
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from services.compliance_discovery import _is_safe_domain

HEADERS = {"User-Agent": "VenderScope/1.0 Logo Discovery Bot (security research)"}
MAX_LOGO_BYTES = 256 * 1024
ICON_REL_TOKENS = ("icon", "shortcut icon", "apple-touch-icon", "mask-icon")
COMMON_ICON_PATHS = [
    "/apple-touch-icon.png",
    "/apple-touch-icon-precomposed.png",
    "/favicon-48x48.png",
    "/favicon-32x32.png",
    "/favicon-16x16.png",
    "/favicon.png",
    "/favicon.ico",
]
LOGO_HINTS = ("logo", "brand", "wordmark", "navbar", "header")


def _is_same_vendor_site(url: str, base: str) -> bool:
    host = urlparse(url).netloc.lower()
    base = base.lower()
    return host in {base, f"www.{base}"} or host.endswith(f".{base}")


def _safe_get(url: str, timeout: int = 6) -> requests.Response | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=False, stream=True)
        if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
            response.close()
            return None
        final_url = response.url
        final_host = urlparse(final_url).netloc
        if not final_host or not _is_safe_domain(final_host):
            response.close()
            return None
        return response
    except Exception:
        return None


def _icon_score(url: str, rel: str = "", sizes: str = "") -> tuple[int, int, int]:
    rel = (rel or "").lower()
    url = (url or "").lower()
    sizes = (sizes or "").lower()

    primary = 0
    if rel.strip() == "icon":
        primary = 5
    elif "shortcut icon" in rel:
        primary = 4
    elif "manifest" in rel:
        primary = 3
    elif "apple-touch-icon" in rel:
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

    extension_bias = 1 if url.endswith(".png") else 0
    penalty = -1 if "apple-touch" in url else 0
    return (primary, size_value, extension_bias + penalty)


def _extract_icon_links(base: str, home_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    candidates: list[tuple[tuple[int, int, int], str]] = []
    manifest_url = None

    for link in soup.find_all("link", href=True):
        href = link["href"]
        rel_attr = link.get("rel") or []
        rel = " ".join(rel_attr).strip().lower() if isinstance(rel_attr, list) else str(rel_attr).strip().lower()
        full = urljoin(home_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https") or not _is_same_vendor_site(full, base):
            continue
        if rel == "manifest":
            manifest_url = full
            continue
        if any(token in rel for token in ICON_REL_TOKENS):
            candidates.append((_icon_score(full, rel, link.get("sizes", "")), full))

    if manifest_url:
        manifest_resp = _safe_get(manifest_url)
        if manifest_resp and manifest_resp.status_code == 200:
            try:
                manifest = json.loads(manifest_resp.text)
                for icon in manifest.get("icons", []):
                    src = icon.get("src")
                    if not src:
                        continue
                    full = urljoin(manifest_url, src)
                    parsed = urlparse(full)
                    if parsed.scheme not in ("http", "https") or not _is_same_vendor_site(full, base):
                        continue
                    candidates.append((_icon_score(full, "manifest", icon.get("sizes", "")), full))
            except Exception:
                pass
            finally:
                manifest_resp.close()

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [url for _, url in candidates]


def _image_score(url: str, alt: str = "", class_name: str = "", width: int = 0, height: int = 0) -> tuple[int, int, int]:
    alt = (alt or "").lower()
    class_name = (class_name or "").lower()
    url = (url or "").lower()

    hint_score = 0
    haystack = f"{alt} {class_name} {url}"
    if "logo" in haystack:
        hint_score += 4
    if "brand" in haystack or "wordmark" in haystack:
        hint_score += 2
    if "header" in haystack or "nav" in haystack:
        hint_score += 1

    size_score = 0
    if width and height:
        min_edge = min(width, height)
        max_edge = max(width, height)
        if min_edge >= 24:
            size_score += min(min_edge, 256)
        if max_edge <= 800:
            size_score += 10

    extension_bias = 2 if url.endswith(".svg") else 1 if url.endswith(".png") else 0
    return (hint_score, size_score, extension_bias)


def _extract_logo_images(base: str, home_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    candidates: list[tuple[tuple[int, int, int], str]] = []

    for img in soup.find_all("img", src=True):
        src = img.get("src")
        full = urljoin(home_url, src)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https") or not _is_same_vendor_site(full, base):
            continue

        alt = img.get("alt", "")
        class_name = " ".join(img.get("class", [])) if isinstance(img.get("class"), list) else str(img.get("class") or "")
        haystack = f"{alt} {class_name} {src}".lower()
        if not any(hint in haystack for hint in LOGO_HINTS):
            continue

        try:
            width = int(img.get("width", 0) or 0)
        except ValueError:
            width = 0
        try:
            height = int(img.get("height", 0) or 0)
        except ValueError:
            height = 0

        candidates.append((_image_score(full, alt, class_name, width, height), full))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [url for _, url in candidates]


def _probe_common_icon_paths(base: str) -> list[str]:
    return [f"https://{base}{path}" for path in COMMON_ICON_PATHS] + [
        f"https://www.{base}{path}" for path in COMMON_ICON_PATHS
    ]


def discover_logo_candidates(domain: str) -> list[str]:
    base = domain.replace("https://", "").replace("http://", "").rstrip("/")
    if not _is_safe_domain(base):
        return []

    home_candidates = [f"https://{base}", f"https://www.{base}"]
    html = None
    home_url = None
    for candidate in home_candidates:
        resp = _safe_get(candidate)
        if not resp:
            continue
        try:
            if resp.status_code == 200 and "text/html" in (resp.headers.get("Content-Type", "").lower()):
                html = resp.text
                home_url = resp.url or candidate
                break
        finally:
            resp.close()

    candidates: list[str] = []
    if html and home_url:
        candidates.extend(_extract_icon_links(base, home_url, html))
        for url in _extract_logo_images(base, home_url, html):
            if url not in candidates:
                candidates.append(url)

    for url in _probe_common_icon_paths(base):
        if url not in candidates:
            candidates.append(url)
    return candidates


def fetch_vendor_logo_asset(domain: str) -> tuple[bytes, str] | None:
    for candidate in discover_logo_candidates(domain):
        response = _safe_get(candidate)
        if not response:
            continue
        try:
            if response.status_code != 200:
                continue
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if not content_type.startswith("image/"):
                continue
            content = response.raw.read(MAX_LOGO_BYTES + 1, decode_content=True)
            if not content or len(content) > MAX_LOGO_BYTES:
                continue
            return content, content_type
        finally:
            response.close()
    return None
