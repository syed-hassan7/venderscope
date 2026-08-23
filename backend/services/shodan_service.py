import config  # Loads backend/.env once with process env precedence.
import functools
import shodan
import os

SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")

# Ports that are considered risky if exposed publicly
RISKY_PORTS = {
    21:   ("FTP",        "HIGH",     "Unencrypted file transfer exposed"),
    22:   ("SSH",        "MEDIUM",   "SSH access exposed — check auth policy"),
    23:   ("Telnet",     "CRITICAL", "Telnet is unencrypted and highly dangerous"),
    25:   ("SMTP",       "MEDIUM",   "Mail server exposed"),
    80:   ("HTTP",       "LOW",      "Unencrypted web traffic exposed"),
    443:  ("HTTPS",      "LOW",      "HTTPS exposed — generally expected"),
    445:  ("SMB",        "CRITICAL", "SMB exposed — high ransomware risk"),
    1433: ("MSSQL",      "CRITICAL", "SQL Server exposed to internet"),
    3306: ("MySQL",      "CRITICAL", "MySQL database exposed to internet"),
    3389: ("RDP",        "CRITICAL", "Remote Desktop exposed — brute force risk"),
    5432: ("PostgreSQL", "CRITICAL", "PostgreSQL database exposed to internet"),
    6379: ("Redis",      "CRITICAL", "Redis exposed — often unauthenticated"),
    8080: ("HTTP-Alt",   "MEDIUM",   "Alternative HTTP port exposed"),
    9200: ("Elasticsearch", "CRITICAL", "Elasticsearch exposed — data leak risk"),
    27017:("MongoDB",    "CRITICAL", "MongoDB exposed to internet"),
}

def check_shodan_exposure(domain: str) -> list[dict]:
    """
    Queries Shodan for exposed services on the vendor's domain.
    Returns a list of risk events for any concerning open ports.
    """
    if not SHODAN_API_KEY:
        print("[Shodan] No API key found, skipping.")
        return []

    try:
        api = shodan.Shodan(SHODAN_API_KEY)
        # shodan-python's REST client has no timeout param — it calls the underlying
        # requests.Session directly, so a slow/unresponsive API can hang this thread
        # forever. Bind it here since the library gives no other hook.
        api._session.request = functools.partial(api._session.request, timeout=10)
        results = api.search(f"hostname:{domain}")
        events  = []

        for match in results.get("matches", []):
            port = match.get("port")
            ip   = match.get("ip_str", "unknown")

            if port in RISKY_PORTS:
                name, severity, reason = RISKY_PORTS[port]
                events.append({
                    "title":       f"{name} (Port {port}) Exposed — {ip}",
                    "description": f"{reason}. Detected on {ip} via Shodan passive scan.",
                    "severity":    severity,
                    "source":      "Shodan"
                })
            else:
                # Still report unknown exposed ports as LOW
                events.append({
                    "title":       f"Port {port} Exposed — {ip}",
                    "description": f"Unexpected open port {port} detected on {ip}.",
                    "severity":    "LOW",
                    "source":      "Shodan"
                })

        print(f"[Shodan] {domain} → {len(events)} exposed service(s) found")
        return events

    except shodan.APIError as e:
        if "403" in str(e) or "Access denied" in str(e):
            print(f"[Shodan] Free tier does not support search API — skipping {domain}")
        else:
            print(f"[Shodan] API error for {domain}: {e}")
        return []
    except Exception as e:
        print(f"[Shodan] Unexpected error for {domain}: {e}")
        return []
