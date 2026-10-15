# Support intake and deployment storage verification — October 15, 2026

Branch: landscaping-multi-area-recovery-oct11. Main remains untouched.

## Support
- Contact & Support now has six accessible SVG topic cards: Getting Started, Account & Login, Measurement & PDF Help, Report a Bug, Billing & Subscription, Feature Request.
- Public web/mobile form validates input and CSRF, applies submission limits, saves requests in the existing account/estimate database before notifying Resend. Reference IDs and idempotent submission protect network retries from duplicate requests.
- Notification recipient is sean@aeriquote.com, explicitly selected by Sean. Optional SUPPORT_INBOX overrides it. Uses the existing RESEND_API_KEY, PASSWORD_RESET_FROM and AERIQUOTE_PUBLIC_URL configuration. Reply-To is the submitter’s email. No additional API secret is needed.
- Head Office → Support requests lists the latest 100 saved requests, escapes user input and can retry failed notification attempts. Accepted means accepted by Resend, not inbox delivery confirmation.
- Optional page links have query strings/fragments removed to avoid storing reset tokens. No attachments, chat, phone queue or CRM was added.

## Storage
- Corrected PostgreSQL dict-row compatibility in /api/estimate-storage-status count queries.
- Head Office → Deployment storage check shows the connected backend and whether a stable FLASK_SECRET_KEY is configured; never reveals connection strings or secrets.
- Save a pre-deployment checkpoint. It records per-row hashes for accounts, employee accounts, business profiles, estimates, revisions and support requests. No raw account contents are copied into the checkpoint.
- After a real Render redeploy, reload and confirm the same checkpoint remains and Missing is zero in every row. Changed rows may reflect legitimate activity. New rows are allowed. Process identity changes alone do not prove a deployment occurred.
- Checkpoints are comparison records, not backups. SQLite requires a configured persistent disk. PostgreSQL backup policy must be verified in Render separately.

## Validation and remaining live steps
- Backend tests cover actual public intake, CSRF, malformed input, redacted URLs, saved email failures, idempotent retries, admin authorization/escaping and checkpoint survival across module restart, including missing-record detection.
- Frontend tests cover all six SVG cards, failed-network retry with retained values/same request ID, and saved reference confirmation.
- Existing account-access, password-recovery, clean public routes and public UI checks pass locally. Embedded measurement application HTML is unchanged.
- No real support email was sent during automated tests. After deployment, submit a clearly labeled test request, check sean@aeriquote.com and Head Office. Then save a storage checkpoint, redeploy the same commit, reload and inspect Missing counts. Render persistence is not yet proven by local tests.
