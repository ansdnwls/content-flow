# ContentFlow — Security Architecture

## Overview

ContentFlow implements defense-in-depth security across authentication, data encryption, webhook integrity, and row-level access control.

---

## Threat Model

### Assets
| Asset | Sensitivity | Storage |
|-------|------------|---------|
| OAuth tokens (access/refresh) | Critical | AES-256-GCM encrypted in Supabase |
| API keys | Critical | bcrypt hashed in Supabase |
| Stripe customer data | High | Stripe-managed, only IDs stored |
| User PII (email, name) | High | Supabase with RLS |
| Post content | Medium | Supabase with RLS |
| Webhook signing secrets | High | Supabase, per-webhook unique |

### Threat Actors
1. **External attacker** — API brute-force, SSRF, injection
2. **Malicious user** — IDOR, privilege escalation, payment bypass
3. **Compromised dependency** — supply chain attack
4. **Insider threat** — credential exposure, data exfiltration

### Attack Surface
```
Internet ──► API Gateway ──► FastAPI ──► Supabase (DB)
                  │                 ├──► Redis (cache/queue)
                  │                 ├──► Stripe (billing)
                  │                 ├──► Resend (email)
                  │                 └──► External platforms (OAuth)
                  │
                  └──► Stripe Webhooks (inbound)
```

---

## Security Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                    Client Request                     │
└─────────────┬───────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────┐
│  RequestValidatorMiddleware                          │
│  • Body size limit (10MB / 100MB for uploads)        │
│  • Scanner user-agent blocking                       │
└─────────────┬───────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────┐
│  SecurityHeadersMiddleware                           │
│  • HSTS, CSP, X-Frame-Options, X-Content-Type        │
│  • Permissions-Policy, Referrer-Policy               │
└─────────────┬───────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────┐
│  RequestIdMiddleware + LoggingMiddleware              │
│  • UUID v4 per request                               │
│  • Structured logging (no PII)                       │
└─────────────┬───────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────┐
│  Authentication (get_current_user / get_admin_user)  │
│  • API key validation (bcrypt, timing-safe)          │
│  • User lookup + workspace resolution               │
│  • Admin: enterprise plan enforcement                │
└─────────────┬───────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────┐
│  Authorization (per-endpoint)                        │
│  • owner_id filtering on all queries                 │
│  • workspace_id scoping                              │
│  • Billing quota checks                              │
└─────────────┬───────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────┐
│  Business Logic + Supabase (RLS enabled)             │
└─────────────────────────────────────────────────────┘
```

---

## 1. API Key Authentication

### How It Works

```
Client                          API Server
  │                                │
  │  X-API-Key: cf_live_xxxxx      │
  │ ─────────────────────────────► │
  │                                │  1. Validate prefix (cf_live_ or cf_test_)
  │                                │  2. Lookup key_prefix in api_keys table
  │                                │  3. bcrypt.checkpw(raw_key, hashed_key)
  │                                │  4. Resolve user_id → AuthenticatedUser
  │   200 OK                       │
  │ ◄───────────────────────────── │
```

### Key Generation

- Raw key format: `{prefix}_{token}` (e.g., `cf_live_Ab3x...`)
- Token: `secrets.token_urlsafe(24)` (192 bits of entropy)
- Storage: Only the **bcrypt hash** is stored in the database
- The raw key is shown exactly once at creation time

### Key Prefixes

| Prefix | Environment | Description |
|--------|-------------|-------------|
| `cf_live_` | Production | Full access to all endpoints |
| `cf_test_` | Sandbox | Rate-limited, no real publishing |
| `cf_admin_` | Admin | Elevated privileges, enterprise-only |

### Security Properties

- **bcrypt** with automatic salt (cost factor 12)
- Raw keys never stored or logged
- `key_preview` field shows only `cf_live_...xxxx` (last 4 chars)
- Keys can be deactivated (`is_active = false`) without deletion
- **Key rotation** with 24-hour grace period

## 2. Token Encryption

### OAuth Token Storage

Connected social account tokens (access + refresh) are encrypted at rest using **AES-256-GCM** (authenticated encryption).

```
TOKEN_ENCRYPTION_KEY (env var, base64-encoded 32 bytes)
        │
        ▼
┌──────────────────┐
│  AES-256-GCM     │──► encrypted_access_token  (stored in DB)
│  encrypt()       │──► encrypted_refresh_token  (stored in DB)
│  (random nonce)  │
└──────────────────┘
```

### Key Rotation

1. Generate a new 32-byte key: `python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"`
2. Run migration script to re-encrypt all tokens with the new key
3. Update `TOKEN_ENCRYPTION_KEY` environment variable
4. Restart all services

### Token Refresh

- Celery Beat runs `refresh_oauth_tokens` every 10 minutes
- Tokens are refreshed `TOKEN_REFRESH_LEEWAY_SECONDS` (default: 300s) before expiry
- Platform-specific rate limits are respected during refresh

## 3. Webhook Signing

### HMAC-SHA256 Signature

Every webhook delivery is signed so recipients can verify authenticity.

```
Signing:
  payload = f"{timestamp}.{json_body}"
  signature = HMAC-SHA256(signing_secret, payload)

Headers:
  X-ContentFlow-Signature: sha256={hex_signature}
  X-ContentFlow-Timestamp: {unix_timestamp}
  X-ContentFlow-Event: {event_type}
```

### Verification (recipient side)

```python
import hashlib, hmac, time

def verify_webhook(body: bytes, signature: str, timestamp: str, secret: str, tolerance: int = 300):
    if abs(time.time() - int(timestamp)) > tolerance:
        raise ValueError("Timestamp too old — possible replay attack")

    signed_payload = f"{timestamp}.{body.decode()}"
    expected = "sha256=" + hmac.new(
        secret.encode(), signed_payload.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise ValueError("Invalid signature")
```

### Properties

- Per-webhook `signing_secret` (unique per subscription)
- Timestamp tolerance prevents replay attacks (default: 5 minutes)
- `hmac.compare_digest` prevents timing attacks
- Failed deliveries retry with exponential backoff (max 6 attempts)
- Dead letter queue for permanently failed deliveries

## 4. SSRF Defense

### URL Validation (`app/core/url_validator.py`)

All external URLs (webhook targets, media URLs) are validated:

- **Scheme whitelist** — only `http://` and `https://` allowed
- **Blocked hostnames** — `localhost`, `*.local`, `*.internal`
- **Private IP ranges** — 10.x, 172.16-31.x, 192.168.x, 127.x, ::1, fe80::
- **DNS re-resolution** — resolves hostname and validates all returned IPs
- **DNS rebinding defense** — checks resolved IPs, not just hostname

## 5. Row Level Security (RLS)

### Policies

All tables have RLS enabled. Policies ensure data isolation between users.

| Table | Policy | Rule |
|-------|--------|------|
| `users` | Self-select | `id = auth.uid()` |
| `users` | Self-update | `id = auth.uid()` |
| `api_keys` | Service role only | Blocked for `authenticated` role |
| `social_accounts` | Owner access | `owner_id = auth.uid()` |
| `posts` | Owner access | `owner_id = auth.uid()` |
| `post_deliveries` | Owner access | `owner_id = auth.uid()` |
| `video_jobs` | Owner access | `owner_id = auth.uid()` |
| `webhooks` | Owner access | `owner_id = auth.uid()` |

### Service Role Key

The API server uses `SUPABASE_SERVICE_ROLE_KEY` to bypass RLS for cross-user operations (e.g., Celery workers processing tasks). This key must **never** be exposed to clients.

## 6. Rate Limiting

### Per-Plan Limits

| Plan | Requests/min | Posts/month | Videos/month | Social Sets |
|------|-------------|-------------|--------------|-------------|
| Free | 10 | 20 | 3 | 2 |
| Build | 60 | 200 | 20 | 5 |
| Scale | 300 | 999,999 | 100 | 20 |
| Enterprise | 1,000 | Unlimited | Unlimited | Unlimited |

### Implementation

- Redis-backed sliding window counter
- Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- HTTP 429 when exceeded

## 7. Middleware Security Stack

### Request Validation

- **Body size limit** — 10MB default, 100MB for upload endpoints
- **Scanner blocking** — known vulnerability scanner user-agents rejected (403)

### Security Headers

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |
| `Content-Security-Policy` | `default-src 'self'` | Restrict resource loading |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Disable browser APIs |

### Error Handling

- `ErrorTrackingMiddleware` catches unhandled exceptions
- Error responses never leak stack traces or internal details
- Generic `{"detail": "Internal server error"}` for 500 errors
- Sentry integration captures full context (opt-in via `SENTRY_DSN`)

## 8. Input Validation

### Pydantic Models

All API inputs validated via Pydantic `BaseModel`:

- Type checking and coercion
- `max_length` constraints on all string inputs
- `min_length` / `max_length` on list fields (e.g., platforms: 1-20)
- Enum validation for platforms, statuses
- JSON schema validation for nested objects

### SQL Injection Prevention

- All database operations use Supabase client (parameterized queries)
- No raw SQL execution from user input

---

## Security Responsibility Model

### ContentFlow Responsibilities
- Encrypt tokens at rest (AES-256-GCM)
- Hash API keys (bcrypt)
- Enforce data isolation (RLS + owner_id queries)
- Sign webhook deliveries (HMAC-SHA256)
- Validate and sanitize all inputs
- Maintain security headers on responses
- Monitor and alert on security events
- Regular dependency audits

### User Responsibilities
- Keep API keys confidential
- Rotate API keys regularly
- Validate webhook signatures on receipt
- Use HTTPS for all API communication
- Report security vulnerabilities responsibly

---

## Incident Response Process

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| P0 | Active breach, data exposure | Immediate (< 1 hour) |
| P1 | Vulnerability with exploit path | < 4 hours |
| P2 | Vulnerability without known exploit | < 24 hours |
| P3 | Security improvement | Next sprint |

### Response Steps

1. **Detect** — Sentry alerts, monitoring, user reports
2. **Contain** — Disable affected endpoints, rotate compromised keys
3. **Investigate** — Audit logs, request traces, git blame
4. **Remediate** — Fix root cause, deploy patch
5. **Notify** — Affected users within 72 hours (GDPR requirement)
6. **Review** — Post-mortem, update threat model

### Contacts

- Security team: security@contentflow.dev
- Bug reports: https://github.com/contentflow/api/security/advisories

---

## Vulnerability Disclosure

We welcome responsible disclosure of security vulnerabilities.

### Reporting Channel
- Email: security@contentflow.dev
- Response within 48 hours

### Scope
- API endpoints (`api.contentflow.dev`)
- OAuth token handling
- Webhook delivery security
- Admin panel access controls

### Out of Scope
- Social engineering attacks
- Physical attacks
- Denial of service attacks
- Third-party platform vulnerabilities

---

## Compliance Readiness

### GDPR
- [ ] Data processing agreement (DPA) template
- [ ] Right to erasure (`DELETE /users/{id}`)
- [ ] Data export (`GET /users/{id}/export`)
- [ ] Breach notification within 72 hours
- [ ] Privacy policy referencing data handling

### SOC 2 (Preparation)
- [x] Access control (API keys, admin isolation)
- [x] Encryption at rest (AES-256-GCM for tokens)
- [x] Audit logging (audit_logs table)
- [x] Change management (git, CI/CD)
- [ ] Formal security policies documentation
- [ ] Annual penetration testing

---

## Security Checklist

### Before Deploy

- [ ] `TOKEN_ENCRYPTION_KEY` is set and securely generated (32 bytes)
- [ ] `OAUTH_STATE_SECRET` is set and unique per environment
- [ ] `JWT_SECRET` is set (NOT the default `change-me-in-production`)
- [ ] `STRIPE_WEBHOOK_SECRET` is set
- [ ] `SUPABASE_SERVICE_ROLE_KEY` is set (never exposed to clients)
- [ ] No hardcoded secrets in source code
- [ ] RLS policies applied (`02_rls.sql`)
- [ ] Sentry DSN configured for error tracking
- [ ] Security headers middleware enabled

### Periodic Review

- [ ] Rotate `TOKEN_ENCRYPTION_KEY` quarterly
- [ ] Rotate `JWT_SECRET` quarterly
- [ ] Audit API key usage (`last_used_at` field)
- [ ] Review webhook delivery failures (dead letter queue)
- [ ] Run `pip-audit` for dependency vulnerabilities
- [ ] Run `scripts/secret_scan.py --git` for leaked secrets
- [ ] Review audit_logs for suspicious activity
- [ ] Update OAuth client secrets per platform requirements
