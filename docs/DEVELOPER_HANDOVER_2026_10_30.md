# AeriQuote - concise technical handover

October 30, 2026. Read current recovery HEAD and latest `docs/RESUME_HERE_2026_10_30.md` first. Application logging fix6e9457f passed GitHub/full/PostgreSQL and is live on the recovery site. Operational launch sign-off is pending. Owner: Sean Dusome. Technical responder/backup contacts have not been appointed. Do not infer credentials or permissions from this document.

## Architecture and environments

- Self-contained Flask application in `app.py`, including browser JavaScript/CSS; Leaflet measurement interface. Six industries share validated geometry and server pricing. Existing RETRACE OUTLINE is physical-iPhone visually approved; preserve it.
- Server modules: `measurement_integrity.py`, `pricing_integrity.py`, `saved_estimate_edit.py`, `property_address.py`, `property_sessions.py`, `account_credits.py`, `account_recovery.py`, `activation_metrics.py`; support and checkpoint modules. DB adapter supports PostgreSQL and local SQLite. Quotes, revisions, profiles/branding and usage are persisted; do not rewrite historical rows.
- Python dependencies pinned in `requirements.txt`: Flask3.1.2, Gunicorn23.0.0, psycopg3.2.10. CI Python3.13/Node24; JS regression dependencies jsdom30.1.2 and Leaflet1.9.4. Customer PDFs use existing browser html2canvas/jsPDF; preserve Single/Expanded and QA-only vector designs.
- `safe_logging.py` installed by app and default `gunicorn.conf.py` before worker startup. Unknown log detail is suppressed, exception category/locations and safe access metrics retained. Browser diagnostics are fixed codes. Never bypass config or add raw credential/request/exception logging.
- Current Google/Mapbox/Solar/Street View code and AutoMeasure are preserved; imagery licensing is unresolved. Manual Roofing and vector remain QA-restricted. AI Trace stays removed. Do not add Stripe or change plan allowances without approval.

| Environment | Branch/service | Known state |
|---|---|---|
| Recovery QA | `landscaping-multi-area-recovery-oct11`; `srv-db5a2g5ckfvc739fui70`, aeriquote-commercial-test | Only authorized development/deployment target. Verify live exact commit in Render |
| Main service candidate | `main`; `srv-db01g1p42hec73ehu1lg`, aeriquote-roof-measurement | Old `c049a04...`, behind recovery. Never promote/reset/modify without explicit approval |
| Managed database | `dpg-db019ijncjis7383g3a0-a` | Paid PG18.6. Actual service mapping not verified |
| Disposable tests | Local temporary SQLite; GitHub PostgreSQL16 container `aeriquote_qa` | Synthetic data only. Not production backups |

Both web services currently free/On Commit/TCP-only, branches report unprotected. `render.yaml` describes an older differently named service; do not apply blindly. Never copy live DB URLs or session secrets between test and production. Confirm dedicated DB IDs, env group membership and least-privilege roles via authorized masked review before launch. Missing `DATABASE_URL` chooses local SQLite; missing stable Flask secret breaks session continuity. Read current config without printing values.

## Tests and working locally

Use disposable environments. Never export production `DATABASE_URL` into tests. Canonical complete command list and PostgreSQL service definition: `.github/workflows/validate-landscaping-recovery.yml`. GitHub Actions recovery workflow includes the full suite and separate PostgreSQL concurrency, allowances, identity/security and native backup drill. Require successful jobs on the exact commit, not just a syntax check or previous release.

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm install --no-save --package-lock=false jsdom@30.1.2 leaflet@1.9.4
.venv/bin/python scripts/check_release_files.py
.venv/bin/python scripts/test_sensitive_logging.py
node scripts/test_browser_log_privacy.cjs
.venv/bin/python scripts/test_password_recovery.py
.venv/bin/python scripts/test_security_lifecycle.py
.venv/bin/python scripts/test_server_pricing.py
.venv/bin/python scripts/test_emergency_backup_recovery.py
```

Full regression: run every step of the `recovery` Actions job; it is the authoritative list (75 local regression commands at this checkpoint). PostgreSQL: run the separate `postgres_integrity` job in that workflow. Its `QA_POSTGRES_URL`/container are disposable CI fixtures. `--postgres` scripts guard localhost/test DB; do not adapt them to customer DBs. CI credentials in the workflow are fictional throwaway values, never deployment credentials. Full password-reset tests use mocked delivery; do not reset real accounts to test.

## Backups and recovery

Read `docs/SECURITY_DATA_PROTECTION_2026_10_30.md` and original production safety audit. Actual system SELECTs show WAL archiving on/successful, but managed base backups and exact recovery window remain unverified. Paid Render policy supplies continuous PITR,3/7-day window depending on workspace; available dates must be checked in Dashboard Recovery. Native CI restore proves isolated PG16 mechanics, not managed PG18 recoverability.

For data loss, preserve current DB and escalate to Render Support. An approved responder restores into a NEW isolated instance, validates all table classes/assets with authorized access, reconciles writes since the recovery point, then requests approval for any service switch. Never drop tables, restore over live data, reset usage or delete the original DB. No destructive command is provided here. Record RPO/RTO before launch. Storage hash checkpoints detect differences but are not backups.

## Investigate and deploy safely

1. Obtain a redacted reproduction/time, industry/browser, error code/ticket reference and release. Do not ask for passwords/reset links or private business estimates by default. Head Office can triage support without business estimate access.
2. Check platform status, deploy/health events, safe error code/category/module/line,5xx and database system metadata. Current logs omit raw exception detail deliberately. Reproduce with synthetic fixtures to find the cause; do not temporarily turn on raw customer logging.
3. Fix only on recovery, run targeted/full/PostgreSQL tests and required browser/PDF verification. Distinguish emulation from physical Safari/Messenger. Record exact commit and evidence.
4. Production requires separately approved protection/CI/review gate and explicit named release approval. Do not just point production at recovery. Verify dedicated DB, backup, stable session secret and schema compatibility first.
5. Preserve known-good commit/build manifest. App rollback keeps current customer DB; inspect target environment/start settings and schema compatibility. Render Dashboard rollback disables auto deploy; API does not. Old pre-security builds can reintroduce logging leaks. Never restore a backup simply to make old application code run.

## Monitoring and escalation

Native Render notifications can cover failed deploys/unhealthy services after destination verification. Current inherited defaults and recipient delivery are unverified. Central browser PDF alerts and proper HTTP DB readiness still require approval/implementation. Fixed browser `AQ:pdf-generation-failed` is local-console evidence, not an owner notification.

Sean decides whether to pause affected quoting. A named engineer diagnoses/recovers, backup engineer covers absence, Render Support handles platform recovery assistance. Contact channels/response agreement must be established outside the app; no responder details invented. P1: wrong totals, data loss, security or outage - stop affected estimates immediately. P2: failed save/PDF with work preserved. Preserve browser work; do not refresh/clear storage during an unsaved correction. Use `docs/EMERGENCY_RECOVERY_2026_10_30.md` / its one-page PDF for owner instructions. Support default `sean@aeriquote.com` needs confirmed monitoring/delivery and an external outage path.

No ongoing developer-free guarantee is possible: launch needs an accountable responder, tested backup access, working alerts and a controlled release process. Stop after this scoped batch and request approval for remaining infrastructure/security settings.
