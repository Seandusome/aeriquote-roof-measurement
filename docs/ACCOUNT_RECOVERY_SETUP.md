# AeriQuote account recovery setup

Recovery branch only. No CRM or payments added.

## What is implemented
- Website Login leads to the existing same-service /dealer-login.
- Owners and employees request a reset at /forgot-password.
- Random 256-bit links expire in 30 minutes, are stored only as SHA-256 hashes, and are consumed atomically once.
- A reset changes only that login's password, invalidates other reset links and existing authenticated sessions, and preserves account status, estimates, quotas, profiles, and business ownership.
- Password changes or login-email changes invalidate older reset links. Disabled employees/businesses remain blocked.
- CSRF protection on recovery forms, no-store/no-referrer response headers, generic unknown-email responses, persistent request limits (3 reset requests per email per 15-minute window; 50 per source; 20 login attempts per email and 100 per source).
- Email delivered via Resend HTTPS API; no SMTP dependency.

## Configure on the commercial test service
1. Create/select a Resend account and verify the sending domain. Use a sending-only API key. Do not paste secrets into chat or commit them.
2. Add RESEND_API_KEY as a secret environment variable in Render.
3. Add PASSWORD_RESET_FROM with the verified sender, e.g. AeriQuote <accounts@your-verified-domain>.
4. Add AERIQUOTE_PUBLIC_URL=https://aeriquote-commercial-test.onrender.com (origin only; no path/query/fragment). When moving to the real domain, configure its actual HTTPS origin there.
5. Retain a stable FLASK_SECRET_KEY and persistent PostgreSQL DATABASE_URL. Recovery tokens/session versions survive restarts only with persistent storage. Free temporary SQLite is not durable account recovery.
6. Deploy, use an email inbox you own, request/reset password, verify delivery and old-password rejection, then test employee reactivation separately. No live email delivery was established by mocked tests.

If sending settings are missing, the recovery page explains that email recovery is unavailable (503); it does not manufacture or expose a reset link. Provider delivery failures are logged without email/token/password details. Provider acceptance is not proof of inbox delivery; check provider logs during live validation.

## Remaining launch work
Forgotten-email recovery needs a real support channel and ownership-verification procedure; the existing support form is still a placeholder. No automatic account email disclosure. Email verification, full paid-plan monthly usage/entitlements, billing, backups/monitoring and production configuration remain separate launch tasks. Rate limiting uses the request remote address; confirm trusted Render proxy behavior before launch. Fixed windows may allow a burst across a window boundary; shared source limits require live verification. Login limiting counts successful attempts as well as failures to bound total authentication traffic.
