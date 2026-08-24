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


def test_web_search_does_not_consume_quota_when_search_fails(monkeypatch):
    consumed = []
    refunded = []

    class FakeResponse:
        status_code = 503
        text = "service unavailable"

    monkeypatch.setattr(compliance, "search_is_configured", lambda: True)
    monkeypatch.setattr(compliance, "consume_search_units", lambda units=1, period=None: consumed.append(units) or True)
    monkeypatch.setattr(compliance, "refund_search_units", lambda units=1, period=None: refunded.append(units) or True)
    monkeypatch.setenv("TAVILY_API_KEY", "key")
    monkeypatch.setattr(compliance.requests, "post", lambda *args, **kwargs: FakeResponse())

    quota_state = {"enabled": True, "used": 0, "exhausted": False}
    result = compliance._web_search("vendor soc2", quota_state)

    assert result == []
    assert consumed == [1]
    assert refunded == [1]
    assert quota_state["used"] == 0


def test_web_search_normalizes_tavily_response_shape(monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"results": [{"title": "Vendor SOC 2 Report", "url": "https://vendor.com/trust", "content": "SOC 2 Type II attestation"}]}

    monkeypatch.setattr(compliance, "search_is_configured", lambda: True)
    monkeypatch.setenv("TAVILY_API_KEY", "key")
    monkeypatch.setattr(compliance.requests, "post", lambda *args, **kwargs: FakeResponse())

    result = compliance._web_search("vendor soc2")

    assert result == [{"title": "Vendor SOC 2 Report", "link": "https://vendor.com/trust", "snippet": "SOC 2 Type II attestation"}]


def test_web_search_stops_at_per_scan_unit_cap(monkeypatch):
    consumed = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"results": [{"title": "t", "url": "u", "content": "c"}]}

    monkeypatch.setattr(compliance, "search_is_configured", lambda: True)
    monkeypatch.setattr(compliance, "consume_search_units", lambda units=1, period=None: consumed.append(units) or True)
    monkeypatch.setenv("TAVILY_API_KEY", "key")
    monkeypatch.setattr(compliance.requests, "post", lambda *args, **kwargs: FakeResponse())

    quota_state = {"enabled": True, "used": compliance.MAX_SEARCH_UNITS_PER_SCAN, "exhausted": False}
    result = compliance._web_search("vendor soc2", quota_state)

    assert result == []
    assert consumed == []  # capped before a unit is ever reserved
    assert quota_state["enabled"] is True  # per-scan cap, not global exhaustion
    assert quota_state["exhausted"] is False


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


def test_extract_relevant_links_rejects_marketplace_profile_paths():
    # Reproduces the jackandjill.ai bug: a same-site link to a *different*
    # company's profile page on a jobs/company marketplace must not be
    # treated as this vendor's own "security" evidence just because the
    # path happens to contain the word "security".
    html = '<a href="/companies/opal-security">Opal Security</a>'

    links = compliance._extract_relevant_links(html, "https://jackandjill.ai", "jackandjill.ai")

    assert links == []


def test_find_doc_links_rejects_junk_paths():
    html = '<a href="/companies/opal-security">Security</a>'

    found = compliance._find_doc_links(html, "https://jackandjill.ai")

    assert "security" not in found


def test_find_docs_in_sitemap_rejects_junk_paths(monkeypatch):
    # The actual leak in the jackandjill.ai bug: sitemap.xml lists every page
    # on the site, including another company's marketplace profile — a bare
    # "security" substring match there is what assigned it as this vendor's
    # own security doc.
    sitemap = """
        <urlset>
          <url><loc>https://jackandjill.ai/companies/opal-security</loc></url>
          <url><loc>https://jackandjill.ai/security</loc></url>
        </urlset>
    """
    monkeypatch.setattr(compliance, "_fetch_page", lambda url, timeout=8: sitemap if url.endswith("/sitemap.xml") else None)

    found = compliance._find_docs_in_sitemap("jackandjill.ai", {})

    assert found.get("security") == "https://jackandjill.ai/security"


def test_pattern_matches_word_boundary():
    assert compliance._pattern_matches("soc", "social media policy") is False
    assert compliance._pattern_matches("iso", "isolated environment") is False
    assert compliance._pattern_matches("soc", "/soc-2-report") is True
    # "security" is a real whole-word match here — the junk-path reject list,
    # not word-boundary matching, is what disqualifies this kind of URL.
    assert compliance._pattern_matches("security", "/companies/opal-security") is True


def test_result_is_credible_rejects_job_posting():
    items = [{
        "title": "IT Audit Subject Matter Expert",
        "link": "https://vendor.com/jobs/ops/it-audit-sme",
        "snippet": "Must have hands-on ISO 27001 and PCI DSS audit experience.",
    }]

    result = compliance._result_is_credible(items, compliance.CERT_KEYWORDS["iso_27001"], "Vendor Co", "vendor.com")

    assert result is None


def test_result_is_credible_rejects_generic_third_party_article():
    items = [{
        "title": "SOC 2 Reporting Explained",
        "link": "https://a-lign.com/articles/soc-2-reporting",
        "snippet": "SOC 2 is an attestation standard for service organizations.",
    }]

    result = compliance._result_is_credible(items, compliance.CERT_KEYWORDS["soc2"], "Vendor Co", "vendor.com")

    assert result is None


def test_result_is_credible_accepts_own_domain_blog_announcement():
    items = [{
        "title": "Vendor Co achieves SOC 2 Type II",
        "link": "https://vendor.com/blog/soc-2-announcement",
        "snippet": "We are proud to announce our SOC 2 Type II report.",
    }]

    result = compliance._result_is_credible(items, compliance.CERT_KEYWORDS["soc2"], "Vendor Co", "vendor.com")

    assert result == items[0]


def test_result_is_credible_rejects_lookalike_domain():
    # "vendor.com" must not match as a substring of a lookalike host —
    # host must equal or be a real subdomain of the vendor's domain.
    items = [{
        "title": "SOC 2 Type II Report",
        "link": "https://vendor.com.evil.ru/fake-report",
        "snippet": "This report covers SOC 2 controls in detail.",
    }]

    result = compliance._result_is_credible(items, compliance.CERT_KEYWORDS["soc2"], "Vendor Co", "vendor.com")

    assert result is None


def test_result_is_credible_accepts_credible_domain_immediately():
    items = [{
        "title": "Vendor Co ISO 27001 Certificate",
        "link": "https://bsigroup.com/certificates/vendor-co-iso27001",
        "snippet": "ISO 27001 certified",
    }]

    result = compliance._result_is_credible(items, compliance.CERT_KEYWORDS["iso_27001"], "Vendor Co", "vendor.com")

    assert result == items[0]


def test_web_search_stage_strips_dead_site_operator(monkeypatch):
    calls = []

    def fake_web_search(query, quota_state=None, include_domains=None):
        calls.append((query, include_domains))
        return []

    monkeypatch.setattr(compliance, "_web_search", fake_web_search)

    compliance._web_search_stage(
        "Vendor Co", "vendor.com", {"dpa": "not_found"},
        {"enabled": True, "used": 0, "exhausted": False},
    )

    assert all("site:" not in query for query, _ in calls)
    assert any(domains == ["vendor.com"] for _, domains in calls)
