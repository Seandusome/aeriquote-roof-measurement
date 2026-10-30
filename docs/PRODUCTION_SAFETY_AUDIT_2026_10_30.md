# AeriQuote production safety and emergency recovery audit

Audit date: October 30, 2026 (Edmonton and UTC; host PDF metadata uses JST).
Baseline: `f3065e2154eaa801aae12e3013d6216ff1d5c3fe`, recovery branch only.

**Decision: operational readiness is not yet demonstrated.** Existing correctness and isolation controls are valuable, but automated detection, safe release gates, proven recoverability and a named technical responder remain launch requirements. This audit changes tests and documentation only. No production requests, customer estimate reads, live database queries, restores, vendor contact or infrastructure changes were performed.

## Verified deployment and repository state

| Item | Observed state, read-only metadata |
|---|---|
| Recovery branch | `landscaping-multi-area-recovery-oct11`, HEAD `f3065e2` before audit; branch metadata `protected:false` |
| Baseline checks | Application run41126508995 and recovery run41126508795 SUCCESS; latter includes disposable PostgreSQL tests |
| Recovery service | `aeriquote-commercial-test`, `srv-db5a2g5ckfvc739fui70`; LIVE `f3065e2`, deploy `dep-dbig6k3bc2fs73bkt6q0` |
| Main service candidate | `aeriquote-roof-measurement`, `srv-db01g1p42hec73ehu1lg`; LIVE old main `c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a`, deploy `dep-db5b726k1f9s73e862ug` |
| Both web services | Free plan, auto-deploy on commit, empty HTTP health-check path, notification setting `default` |
| AeriQuote-named database | Available, paid `0.1c-256mb`, PostgreSQL18, 1GB, HA disabled; plan metadata only |
| Old isolated QA database | Free PostgreSQL16, expires November20; never a permanent backup |
| Main baseline | `c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a`; unchanged |

The main service is behind the recovery application. Do not assume it is launch-ready or blindly deploy recovery to it. Actual launch domain, database mapping, QA/production separation, secret configuration, notification destinations and workspace plan require authorized confirmation without printing secrets. The available connector cannot list actual backup recovery points or read service environment mappings. No live customer logs were retrieved.

## Prioritized risks and approval-dependent remedies

| Priority | Confirmed finding or unresolved prerequisite | Required action and proof |
|---|---|---|
| P0 before launch | Actual database-to-service mapping, separate QA database and usable recovery point unverified | Record non-secret service/database IDs, inspect backup window in Dashboard, obtain approval for recovery into a NEW isolated database; compare synthetic fixtures, scope access and time recovery. Never restore over customer data |
| P0 before launch | Both branches report unprotected; services deploy on commit rather than after CI/approval; production main lacks the full recovery-only test gate | Approve protected release process, required checks and explicit owner approval. Prove failed checks cannot deploy production |
| P1 security | Recovery default Gunicorn access logging includes password-reset query token; synthetic unexpected exception text is not globally scrubbed | Approve query-free/access-log redaction and allowlisted exception monitoring; test canaries absent from every destination. Production command differs, so production exposure is NOT established |
| P1 detection | No centralized browser PDF/error collector or reason-coded geometry/pricing incident alerts found | Approve privacy-filtered client/server monitoring, alert owner, response times and synthetic probes. Test alert receipt, deduplication, outage fallback, no keys/customer payloads |
| P1 availability | TCP-only checks; no `/health` route (404); `/healthz` redirects to login (302) | Approve minimal HTTP readiness check with bounded database check, no private data. Test DB outage returns503; do not use existing redirect as health check |
| P1 recovery | Paid DB recovery eligibility exists, but actual backup history, retention, usable latest point and full live restoration are unverified | Document recovery point objective (RPO), recovery time objective (RTO), restore access, encrypted independent export policy and approved drill. Hash checkpoints are not backups |
| P1 operations | Free web plans; no verified on-call engineer, secondary contact or tested emergency process | Approve production hosting plan and name responder plus backup. Verify contact outside the app; owner should not need to code |
| P1 privacy | Support free text stored verbatim and included in notification email; users can paste secrets or customer information | Approve clear no-secrets guidance, scoped retention/access and redaction design. Do not silently alter support evidence. Audit email/log permissions and delivery |
| P2 support | Status and internal notes work; no automatic priority field, routing or verified delivery alert | Use internal P1/P2/P3 notes now; approve alerts/escalation only if needed. Do not add CRM complexity |
| P2 recovery | Unsaved browser work is not a database backup; current recovery cannot guarantee draft recovery after tab loss | Keep browser open during incidents. Separate approved draft persistence design is required; no autosave introduced |

P0 means a release prerequisite, not evidence that existing customer data has been lost. Missing protections were documented rather than speculative app changes.

## Error monitoring and critical failure safeguards

Source inspected: `app.py`, `measurement_integrity.py`, `pricing_integrity.py`, account/security modules, support modules, storage checks, browser PDF handlers, workflows and `render.yaml`.

Existing server geometry/quantity/price validation rejects invalid, duplicated, overlapping and mismatched inputs. Failed saves roll back database transactions; stale revisions and repeated idempotency keys are guarded. Unfinished corrections block estimate/PDF completion. Client PDF failures show status but remain browser-local; a server access log cannot detect them. A calculation bug that passes validators needs independent fixture tests and synthetic estimate checks; ordinary uptime monitoring cannot prove quote correctness. Existing full regression tests include independent measurement/pricing, failed saves, business isolation, password expiry and shared allowances. They are not a guarantee against every incorrect quote.

Isolated audit uses fictional canaries only. `/health`404 and `/healthz`302 reproduced. A genuine loopback Gunicorn process with recovery access-log settings recorded a fake reset token in its request line. A synthetic exception printed a fake key-shaped value in server logs, while the HTTP500 body remained generic. No actual password, API key or reset token was used or exposed. No live production log exposure is claimed. Expected support notification exceptions use a safe generic log message.

Recommended monitoring events: failed property acceptance, rejected geometry/pricing reason code, save conflict/failure, client PDF failure, login/reset failure bursts and server5xx. Only event type, random correlation ID, release and coarse browser/device information should be sent by default. No passwords, reset URLs, tokens, API keys, addresses, customer fields or full quote geometry. Account correlation, if needed, must be access-controlled and pseudonymous. Validate alert delivery before launch, not just event submission.

## Support workflow evidence

Disposable SQLite/mocked email test verifies public CSRF, ticket saved before notification, failed-mail state, idempotent retry, Head Office gate, status changes and manual P1 internal note. Page URL queries/fragments are removed. Full support regression tests cover escaped display and email workflows. Head Office can triage a support report without opening business estimates; no business estimate permission is granted by a support reference. A report itself contains voluntarily supplied name/email/company/message, so this is not anonymous or PII-free support.

Notification acceptance is not proof of inbox delivery. Resend delivery, inbox access, notification alerts and external email fallback were not tested live. Existing default support destination is `sean@aeriquote.com`; verify monitored ownership and deliverability before launch. An app outage can also disable its support form, so an independently reachable support channel and technical contact are required.

Suggested manual triage: P1 wrong total/data loss/security/outage; P2 failed save/PDF with work preserved; P3 wording/cosmetic. Record time, release, ticket reference and a redacted reproduction. Do not request customer estimates, credentials or reset links as the default debugging step.

## Database protection and drill scope

Current app uses PostgreSQL when `DATABASE_URL` exists; otherwise local SQLite. This fallback is appropriate for local tests but not a proven production protection: on a free ephemeral service it can lose writes if deployment configuration is missing. Configured database connection failures raise errors rather than silently switching databases. Stable session secret and persistent test DB were previously verified by Sean on October15, but that is not a current backup or production-isolation audit.

`storage_checks.py` hashes rows in selected tables and stores its checkpoint in the same database. It detects changes; it cannot restore records. It excludes several operational/authentication/usage/support tables and cannot survive total database loss on its own.

New `scripts/test_emergency_backup_recovery.py` forcibly uses a temporary SQLite database or explicitly guarded localhost `aeriquote_qa` PostgreSQL. It saves a fictional estimate, backs up, writes another estimate, imports the previous recovery revision in a separate process against the same current disposable DB, and checks both estimates still match. It restores ONLY into a new empty database/file and verifies saved payload/geometry/pricing plus the expected absence of post-backup writes. The original source remains intact with newer records. PostgreSQL CI uses native `pg_dump`/`pg_restore` inside its disposable16 container, never a Render/customer DB. No `--clean`, no production connection, no destructive restore.

This establishes a limited adjacent-version compatibility and logical-backup drill, not arbitrary rollback compatibility, full-site disaster recovery, managed PITR, PostgreSQL18 restore readiness, branding asset retention, external mail recovery or production RPO/RTO. The exported data remains temporary; no real or fictional DB dumps are committed. Actual managed backup inventory is still unverified.

Render's published policy provides continuous PITR on paid PostgreSQL, with a3-day window on Hobby workspaces and7days on Pro+. PITR creates a NEW instance; newest10minutes are excluded. Logical exports are retained7days. Free databases lack managed recovery. Workspace tier and exact instance recovery window must be verified in Dashboard. Do not delete a database as a recovery step.

## Proposed safe release process - NOT executed

1. Confirm production service/domain and its dedicated database using non-secret IDs. Verify QA is isolated. Record current release, DB ID/schema, stable secret configuration and working backup point.
2. Fix only on recovery, run complete regressions, disposable PostgreSQL concurrency/recovery, QA browser and PDF checks. Preserve approved physical-iPhone RETRACE behaviour.
3. Review exact diff and migration compatibility. Obtain Sean's approval for a named tested commit. No blind main reset, branch switch, automatic customer migration or restore.
4. A designated maintainer promotes via reviewed release/PR with required checks and a production approval gate. Current recovery CI is branch-restricted; equivalent production gates must exist first. Approve infrastructure/rules changes separately.
5. Deploy the exact approved release only. Run dedicated production synthetic probes using a preauthorized isolated business, confirm login/readiness/save/reopen/PDF, observe alerts. Never inspect customer estimates as a smoke test.
6. Record deployment ID, release, schema requirements, safe rollback target and monitoring window. Pause if failure; do not repeatedly redeploy random versions.

`render.yaml` describes an older differently named service, starter plan and `/healthz`; it does not match observed live metadata. Do not apply it blindly as the production source of truth.

## Application rollback without overwriting newer data

A trained responder first pauses new releases, identifies exact last known-good compatible build, and confirms database identity/schema and session/environment compatibility. A rollback changes application build/settings; it is NOT database recovery. Keep current customer database and newer records. Never pair an application rollback with an old backup restore just to make code work. Startup/schema changes must be checked; the current app initializes schema automatically.

In Render Dashboard select the correct service, Deploys, a verified compatible successful deploy, then Rollback. Review confirmation with the owner. Dashboard rollback disables auto deploy; API rollback does not. Target deploy can restore its environment/start/health settings while linked environment groups retain current values, so verify DB mapping without exposing credentials before proceeding. Artifact retention is finite; free web rollback is limited to the two most recent previous deployments. If a safe retained target is unavailable, a maintainer can prepare a new tested forward release from known-good code after approval, preserving data/schema.

Actual Render rollback was NOT performed. Recovery docs/tests checkpoint uses `[skip render]` to avoid a pointless build; CI still runs. Live recovery application stays `f3065e2`. No new application defect was changed during this audit.

For actual corruption/loss: preserve current DB, stop affected operations through an approved incident process, contact Render Support, restore to a NEW isolated DB and validate all business/employee/estimate/revision/profile/usage/security/support tables and assets. Reconcile writes after recovery point before any approved switchover. Do not merge tables or reset usage ad hoc. RPO/RTO and switch-back plan must be agreed before launch.

## Tests and remaining proof

- Operational audit: PASS execution; readiness findings include confirmed gaps, not a production-readiness pass.
- Disposable SQLite backup/new-target restore and previous recovery app read: PASS.
- Full local existing regression suite: 74/74 PASS; see `docs/qa/production-safety-2026-10-30/regression-summary.json`.
- GitHub PostgreSQL16 native export/restore, previous-app compatibility, privacy/support audit and all five existing PostgreSQL concurrency/lifecycle steps: PASS at `ec0a9d5`, run41131179510, job124322186303. See `postgres-drill.json`. Local machine has no PostgreSQL tool/server; no local PostgreSQL pass is claimed.
- Owner guide: one-page rendered PDF visually inspected.
- Not performed: production deployment/rollback/restore, managed PITR, live email/alert delivery, real customer tests, physical iPhone QA, new imagery/PDF app output tests (unchanged paths).

## Official references reviewed

- [PostgreSQL recovery and backups](https://render.com/docs/postgresql-backups)
- [PostgreSQL setup and paid recovery features](https://render.com/docs/postgresql-creating-connecting)
- [Rollbacks and settings](https://render.com/docs/rollbacks)
- [Health checks](https://render.com/docs/health-checks)
- [Notifications](https://render.com/docs/notifications)
- [Deploy triggers and skip phrase](https://render.com/docs/deploys)
- [Free-service limitations](https://render.com/docs/free)

Current official docs checked during audit. These policies establish eligibility and platform behaviour, not proof of AeriQuote's actual backup history or configured alert receipt. Stop for review; monitoring/redaction, release gates, production hosting and live recovery drills require separately approved work.

## Checkpoint history

Audit/docs/tests checkpoint `1a2b971`: application validation PASS, recovery workflow rejected before jobs because a container context was placed at job-env level. Test-only follow-up `ec0a9d5` moves that reference to the drill step; PostgreSQL job PASS. Application run41131179468 and full recovery run41131179510 both SUCCESS, including recovery job124322186524. No application or infrastructure change. Final documentation checkpoint checks are reported separately; do not confuse the historical failed workflow with an application defect.

## October30 follow-up

Approved narrow logging fix is recorded in `docs/SECURITY_DATA_PROTECTION_2026_10_30.md` (application6e9457f). The historical exposure findings above describe the pre-fix baseline. New read-only system metadata confirms active WAL archiving, while managed restore points and QA/production mapping remain unverified. See `docs/DEVELOPER_HANDOVER_2026_10_30.md`. No production setting or customer record changed.
