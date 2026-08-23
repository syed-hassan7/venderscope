import services.compliance_discovery as compliance


def test_compliance_discovery_finds_cert_on_linked_trust_page(monkeypatch):
    pages = {
        "https://vendor.com": """
            <html><body>
              <a href="/trust-center">Trust Center</a>
              <a href="/privacy">Privacy Policy</a>
            </body></html>
        """,
        "https://vendor.com/trust-center": """
            <html><body>
              <h1>Trust Center</h1>
              <p>We are certified to ISO 27001:2022 and maintain a SOC 2 Type II report.</p>
            </body></html>
        """,
        "https://vendor.com/privacy": """
            <html><body>
              <p>Our GDPR compliance posture is documented here.</p>
            </body></html>
        """,
    }

    monkeypatch.setattr(compliance, "_is_safe_domain", lambda domain: True)
    monkeypatch.setattr(compliance, "_fetch_page", lambda url, timeout=8: pages.get(url.rstrip("/")))
    monkeypatch.setattr(compliance, "_probe_doc_paths", lambda base, found: found)
    monkeypatch.setattr(compliance, "_find_docs_in_sitemap", lambda base, found: found)
    monkeypatch.setattr(compliance, "_check_trust_centre", lambda domain: {"url": "https://vendor.com/trust-center", "accessible": True})

    result = compliance.run_compliance_discovery("vendor.com", "Vendor", use_web_search=False)

    assert result["certifications"]["iso_27001"]["status"] == "found"
    assert result["certifications"]["soc2"]["status"] == "found"
    assert result["certifications"]["gdpr"]["status"] == "found"


def test_fetch_page_allows_same_site_relative_redirect(monkeypatch):
    # _fetch_page now resolves+pins the IP via _validate_and_resolve, then makes
    # the actual request through _pinned_get — mock at that boundary rather than
    # requests.get, which the pinned fetch no longer calls directly.
    responses = [
        (302, {"Location": "/security"}, b""),
        (200, {}, b"<html>Security page</html>"),
    ]

    monkeypatch.setattr(
        compliance, "_validate_and_resolve",
        lambda hostname: "203.0.113.1" if hostname == "vendor.com" else None,
    )
    monkeypatch.setattr(
        compliance, "_pinned_get",
        lambda hostname, ip, port, scheme, path, timeout: responses.pop(0),
    )

    result = compliance._fetch_page("https://vendor.com")

    assert result == "<html>Security page</html>"


def test_google_search_does_not_consume_quota_when_search_fails(monkeypatch):
    consumed = []
    refunded = []

    class FakeResponse:
        status_code = 503

    monkeypatch.setattr(compliance, "search_is_configured", lambda: True)
    monkeypatch.setattr(compliance, "consume_search_units", lambda units=1: consumed.append(units) or True)
    monkeypatch.setattr(compliance, "refund_search_units", lambda units=1: refunded.append(units) or True)
    monkeypatch.setenv("GOOGLE_CSE_API_KEY", "key")
    monkeypatch.setenv("GOOGLE_CSE_ID", "cx")
    monkeypatch.setattr(compliance.requests, "get", lambda *args, **kwargs: FakeResponse())

    quota_state = {"enabled": True, "used": 0, "exhausted": False}
    result = compliance._google_search("vendor soc2", quota_state)

    assert result == []
    assert consumed == [1]
    assert refunded == [1]
    assert quota_state["used"] == 0


def test_extract_relevant_links_stays_on_vendor_site():
    html = """
        <a href="/security">Security</a>
        <a href="https://vendor.com/legal/dpa">DPA</a>
        <a href="https://external.example/iso-cert">ISO cert</a>
    """

    links = compliance._extract_relevant_links(html, "https://vendor.com", "vendor.com")

    assert "https://vendor.com/security" in links
    assert "https://vendor.com/legal/dpa" in links
    assert all("external.example" not in link for link in links)
