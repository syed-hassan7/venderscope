# Privacy Policy

**Last updated:** 25 August 2026
**Effective date:** 23 March 2026

This Privacy Policy explains how VenderScope ("we", "us", "our") collects, uses, stores, and protects your information when you use our vendor risk intelligence platform.

We are committed to full compliance with the UK General Data Protection Regulation (UK GDPR), the EU General Data Protection Regulation (EU GDPR), and the Data Protection Act 2018.

---

## 1. Who We Are

VenderScope is a vendor risk intelligence platform that aggregates publicly available security signals (breach data, CVEs, infrastructure exposure, compliance documentation) to generate risk scores for third-party vendors.

**Data Controller:** VenderScope
**Contact:** syedzrk1000@gmail.com

---

## 2. What Data We Collect

### 2.0 Guest Mode
If you use the Guest Scan feature (accessible without an account), VenderScope performs a CVE-only lookup of the domain you enter. No data from a guest scan is stored — not the domain, not the results, not your IP address beyond the standard rate-limit window. Guest scans are ephemeral: they are computed and returned in the HTTP response and immediately discarded.

### 2.1 Account Data
When you create an account, we collect:
- Email address
- Account creation timestamp

**Passkeys:** We store a public key and credential identifier for your passkey. We never store biometrics or device secrets.

**Recovery codes:** We store hashed one-time recovery codes (not plaintext). Codes are shown once at signup.

**Google Sign-In:** New accounts start with Google, then a passkey. We store Google's subject identifier (`sub`) and your verified Google email as the account label. Linking Google later requires confirming with a passkey or password. You can disconnect Google from Sign-in methods unless it is the last strong sign-in method.

**Legacy passwords:** Password sign-in is closed. Older accounts may still store a bcrypt hash so you can confirm identity when adding a passkey, linking Google, or deleting the account.

We do not collect your name, phone number, address, date of birth, or payment information.

### 2.2 Vendor Data You Add
Information you choose to add to the platform about third-party vendors:
- Vendor name
- Vendor domain
- Companies House number (optional, UK only)

This data belongs to you. We process it solely to provide the service.

### 2.3 Intelligence Data (Auto-Discovered)
For each vendor you add, VenderScope queries public sources and stores:
- Data breach records from HaveIBeenPwned (domain-level, not personal breach records)
- CVE/vulnerability records from NIST NVD (publicly available)
- Infrastructure exposure data from Shodan (publicly available)
- Compliance document links discovered from vendor's public website
- Security contact email addresses found in publicly accessible `security.txt` files or websites
- Companies House governance data (publicly available)
- Vendor risk scores and scan history

All intelligence data is sourced from public registries and websites. We do not collect any personal data about your vendors' end users.

### 2.4 Usage Data
Standard server logs automatically record:
- IP address of requests
- Timestamp of requests
- HTTP method and endpoint accessed
- HTTP response status code

We do not log request bodies. We do not log passwords. We do not log authentication tokens.

Logs are retained for **30 days** and then automatically deleted.

---

## 3. Legal Basis for Processing (UK/EU GDPR)

| Data Type | Legal Basis |
|-----------|-------------|
| Account data | **Contract** — necessary to provide the service you signed up for |
| Vendor data you add | **Contract** — you direct us to process this data as part of the service |
| Auto-discovered intelligence | **Legitimate interests** — aggregating publicly available security data for risk assessment |
| Usage/log data | **Legitimate interests** — fraud prevention, security monitoring, service integrity |

---

## 4. How We Use Your Data

We use your data exclusively to:
- Provide and operate the VenderScope platform
- Authenticate your identity and protect your account
- Run automated vendor risk scans on your behalf
- Send you risk alert notifications (if configured)
- Respond to support requests
- Ensure platform security and prevent abuse
- Comply with legal obligations

We do **not**:
- Sell your data to third parties
- Share your vendor list with other VenderScope users
- Use your data to train AI or machine learning models
- Send marketing emails (unless you explicitly opt in)
- Profile you for advertising purposes

---

## 5. Data Sharing

We share data only in the following limited circumstances:

### 5.1 Third-Party Services We Use
| Service | Purpose | Data Shared | Location |
|---------|---------|-------------|----------|
| Hugging Face | API hosting (Docker Spaces) | All platform data (except database) | USA (EU-equivalent safeguards) |
| Supabase | Database hosting (PostgreSQL) | All stored vendor and account data | USA (EU-equivalent safeguards) |
| Vercel | Hosting (frontend) | No personal data | USA (EU-equivalent safeguards) |
| HaveIBeenPwned | Breach lookups | Vendor domain (not user data) | USA |
| NIST NVD | CVE lookups | Vendor name (not user data) | USA |
| Shodan | Infrastructure lookups | Vendor domain (not user data) | USA |
| Google (CSE) | Compliance web search | Vendor name/domain | USA |
| Resend | Transactional email | Your email address | USA |

No third party receives your account credentials, your vendor list structure, or your risk scores.

### 5.2 Legal Requirements
We may disclose data if required by law, court order, or to protect the rights, property, or safety of VenderScope users or the public. We will notify you where legally permitted to do so.

### 5.3 Business Transfer
In the event of a merger, acquisition, or asset sale, your data may be transferred. We will provide notice before your data is transferred and becomes subject to a different privacy policy.

---

## 6. Data Retention

| Data Type | Retention Period |
|-----------|-----------------|
| Account data | Deleted immediately on account deletion |
| Vendor data & risk events | Until vendor deletion or account deletion |
| Score history | Until vendor deletion or account deletion |
| Server logs | 30 days rolling |
| Audit logs | 12 months |
| Revoked tokens | Until token expiry date |

When an account is deleted, vendor data, risk events, score history, compliance data, passkeys, recovery hashes, and audit rows tied to that user id are deleted immediately. Failed-login audit events that never had a user id may remain until the audit retention window ends.

---

## 7. Your Rights Under UK/EU GDPR

You have the following rights. To exercise any of them, email us at syedzrk1000@gmail.com.

### 7.1 Right of Access (Article 15)
You have the right to request a copy of all personal data we hold about you. We will respond within **30 days**. You can also export your data directly from the platform (see Settings → Export My Data).

### 7.2 Right to Rectification (Article 16)
You can correct inaccurate personal data at any time via your account settings.

### 7.3 Right to Erasure / Right to be Forgotten (Article 17)
You can delete your account at any time via Delete Account in the footer. This removes:
- Your email address, password hash (if any), Google subject, passkeys, and recovery hashes
- All vendors you added
- All associated risk events, score history, and compliance data
- Audit log rows attributed to your user id

You can also remove individual passkeys or disconnect Google from **Sign-in methods** in the footer without deleting the account. Recovery codes are not enough to drop the last passkey or unlink Google. Use Delete Account if you want everything gone.

Deletion is permanent. Unattributed failed-login audit events may remain until the audit log retention period ends.

### 7.4 Right to Restriction of Processing (Article 18)
You can ask us to pause processing of your data while a dispute is resolved.

### 7.5 Right to Data Portability (Article 20)
You can export all your vendor data and risk history in JSON format via Settings → Export My Data.

### 7.6 Right to Object (Article 21)
You can object to processing based on legitimate interests. We will stop unless we have compelling legitimate grounds.

### 7.7 Right to Lodge a Complaint
If you are in the UK, you have the right to lodge a complaint with the **Information Commissioner's Office (ICO):** [ico.org.uk](https://ico.org.uk) | 0303 123 1113

If you are in the EU, contact your local Data Protection Authority.

---

## 8. Cookies

VenderScope uses minimal cookies and separates them into strictly necessary cookies and optional cookies.

### 8.1 Strictly Necessary Cookies

These cookies are required for core platform security and authentication. They cannot be disabled without breaking sign-in or secure session continuity.

| Cookie / Storage | Purpose | Type | Duration |
|------------------|---------|------|---------|
| `vs_refresh` | Stores your refresh token for silent re-authentication and secure session continuity | httpOnly, Secure, SameSite=None (production) / Lax (local dev) | 7 days |
| In-memory access token | Stores your short-lived access token used for authenticated API calls | Not a cookie — held in browser memory only | Up to 15 minutes |

### 8.2 Optional Cookies

Optional cookies are reserved for future non-essential features. They are not required to use the VenderScope platform today.

- You can **accept** or **decline optional cookies** using the cookie banner or the **Cookie Settings** control in the site footer
- If you decline optional cookies, VenderScope keeps strictly necessary authentication cookies active but blocks optional cookie/storage use
- If optional client-side storage has been used for a non-essential feature, it is cleared when you decline optional cookies

### 8.3 What We Do Not Use

We do not use:
- Advertising cookies
- Cross-site tracking cookies
- Third-party analytics cookies
- Social media tracking pixels

Declining optional cookies does **not** prevent you from logging in, using the dashboard, viewing vendor details, or exporting reports, because those flows rely only on strictly necessary security cookies.

---

## 9. Security

We protect your data through:
- **Encryption in transit:** All data transmitted over HTTPS (TLS 1.2+)
- **Encryption at rest:** Database encrypted at rest on Supabase (PostgreSQL)
- **Password security:** bcrypt hashing with minimum 12 rounds — we cannot recover your password
- **Access control:** Authentication required for all data access; data scoped to your account only
- **Token security:** Authentication tokens stored in httpOnly cookies inaccessible to JavaScript
- **Audit logging:** All access to your data is logged for security monitoring

For full details, see our [Security Policy](./SECURITY.md).

In the event of a data breach that affects your personal data and poses a high risk to your rights, we will notify you within **72 hours** of becoming aware of the breach, in accordance with Article 33-34 of the UK/EU GDPR.

---

## 10. International Data Transfers

VenderScope uses infrastructure providers located in the United States. Data transfers to the US are made under:
- **Standard Contractual Clauses (SCCs)** where applicable
- Providers' participation in equivalent data protection frameworks

---

## 11. Children's Privacy

VenderScope is not directed at individuals under 18 years of age. We do not knowingly collect personal data from anyone under 18. If we become aware that we have collected data from a minor, we will delete it immediately.

---

## 12. Changes to This Policy

We will notify registered users by email of any material changes to this policy at least **30 days** before they take effect. The "Last updated" date at the top of this document will always reflect the most recent revision.

Continued use of VenderScope after a policy change constitutes acceptance of the updated policy.

---

## 13. Contact

For any privacy-related questions, requests, or concerns:

**Email:** syedzrk1000@gmail.com
**Response time:** Within 5 business days
