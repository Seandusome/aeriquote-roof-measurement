> **Latest planning checkpoint:** [Costed QA isolation plan](QA_DATABASE_ISOLATION_PLAN_2026_10_31.md). Recommended NEW paid PG18/Ohio0.1c-256mb: published US$6/month with1GB included, US$72/year equivalent; conservative US$6.30/month before-tax approval ceiling pending final storage quote. Nothing created, purchased or switched. Live QA writes remain paused; no automated service stop was applied.

> After separate approval only: quiesce recovery, provision fresh QA-only credentials/database, verify target before app import (startup writes schema/legacy migration), change only recovery DATABASE_URL, preserve FLASK_SECRET_KEY/code, initialize/seed fictional data, verify isolation and full workflows. Never reconnect recovery to the original as fallback. PG18-specific validation and existing QA-ID allowlists need review. Existing Batch4 Free PG16 contents remain unknown; do not reuse or upgrade blindly. Starting be3e59e checks passed; new documentation CI tracked separately.

> **Dashboard verification update:** [Authorized read-only findings](RENDER_DASHBOARD_VERIFICATION_2026_10_31.md) confirms recovery and main share the same paid resource, logical database and login role — a critical launch blocker. Both have nonempty persisted Flask session secrets; workspace has no environment groups. Actual PITR overview says three days; no exports listed; exact timestamps unverified (Restore not opened). Pause live QA writes pending an approved separation plan. This update supersedes earlier isolation/secret-presence unknowns; preserve the historical evidence below.

> Latest scoped follow-up: [Database safety and recovery verification](DATABASE_RECOVERY_VERIFICATION_2026_10_31.md). Its containing documentation commit is the next resume checkpoint after cde3d5b. No application or infrastructure changes.

## Database-only follow-up checkpoint

- Reverified starting recovery HEAD cde3d5b7f41a04584ccf90809a319b88da41f98e; GitHub runs 41227746551 and 41227746432 SUCCESS, including recovery/PG jobs 124615339714 and 124615339925. Do not rerun completed application/PDF tests merely to resume.
- Recovery remains live at application 764f1ff, dep-dbj2ldrm8hqs73fc0ao0. Main/production candidate c049a04 and dep-db5b726k1f9s73e862ug unchanged. New documentation commit uses [skip render]; any automatic GitHub results must be checked on that exact commit. No manual deployment authorized.
- Paid system SELECT now shows 4,612 successful WAL archives, zero recorded failures, latest archive October31 19:13:07.422881 UTC. Actual recovery dates/base-backup chain/workspace retention still inaccessible. No restore/export attempted.
- Connector role: non-superuser, no RLS bypass, but CREATE DATABASE/ROLE privileges and ownership of 28 user tables. App role mapping remains unknown; do not equate connector and application roles. Startup uses DDL, so blind privilege revocation could break it.
- Test/production DB identities, linked env groups, credentials equality and stable session secret presence remain unverified. Missing DATABASE_URL would choose ephemeral SQLite; missing FLASK_SECRET_KEY would generate a per-process secret. These are code risks, not confirmed deployed mistakes.
- QA remains available Free PG16, expiry November20 22:09:13.900851 UTC /15:09 MST. One aggregate query blocked by empty external allowlist; no retries or rule changes. Do not approve expiry until masked references and current metadata are verified via an authorized internal path.
- New practical incident plan covers deletion, corruption, unavailability, code rollback, bad migrations and preserving post-backup writes/revocations. RTO/RPO values are proposed goals, not measured commitments.
- Next step: read-only Dashboard Recovery and masked service/environment review with named responder. Obtain separate approval before restore rehearsal/costs, network rules, roles, connections or infrastructure changes. No secrets should be sent in chat. Stop for review.

---

# Resume here — October 31, 2026

## Branch and checkpoint

Use ONLY `landscaping-multi-area-recovery-oct11`. Start from the latest remote HEAD; do not overwrite newer work. This document's containing commit is the final documentation checkpoint. Latest verified application commit: `764f1ff67d1d86f53fdefb44b28182ae8cc6dbbf`, following separate roof-integrity fix `e9edb235236a8a09874a0c90a54fb680b732e490`. Starting checkpoint was `b4e69d4`.

Read [today's batch evidence](QA_LAUNCH_RELIABILITY_2026_10_31.md), [database audit](DATABASE_SAFETY_2026_10_31.md), [monitoring/release proposal](MONITORING_DEPLOYMENT_APPROVAL_PLAN_2026_10_31.md), [blockers](LAUNCH_BLOCKERS_2026_10_31.md), [supplier status](SUPPLIER_STATUS_2026_10_31.md), developer handover and emergency recovery guide before continuing.

## Saved and verified

- Reject overlapping billable roof scopes independently of client QA flags; block unsafe PDF/Print before capture. No historical data migration.
- Stable evaluation of the existing server spherical area formula fixes tiny-area cancellation. Same model/tolerances; independent geodesic differences documented.
- Full local 78/78 commands; both application commits pass GitHub regression/PostgreSQL. Latest runs 41226577977 / 41226578063, PG job 124611878682.
- 1,200 randomized geometries; 72 valid API estimates; 276 manipulated requests rejected; 60 revision/conflict cases.
- Actual isolated Chromium 19 cases; 38 downloaded PDFs, 69 pages rendered and inspected. Synthetic imagery only. No fresh physical-device, Safari/Messenger or real-provider verification.
- Recovery live deployment dep-dbj2ldrm8hqs73fc0ao0 at 764f1ff. Documentation checkpoint intentionally skips Render deployment. Verify final GitHub checks again on resume.
- Main remained c049a04; production dep-db5b726k1f9s73e862ug. Production settings/databases/customer accounts untouched.

## Highest priorities next session — obtain authorization before infrastructure changes

1. Dashboard read-only verification of actual paid DB backup/recovery timestamps and workspace plan retention. WAL archiving alone is insufficient. Confirm test/production DATABASE_URL and roles by masked identities, never expose secrets.
2. Expiring QA dpg-dbcjg2brjlhs73dn1g7g-a: available free PG16, expiry November 20 at 22:09:13.900851 UTC. External SQL refused; no content verified. Inspect authorized internal schema/count metadata and every service/env-group reference before declaring disposable. Do not upgrade/delete/export/change access without approval.
3. Paid DB external allowlist currently 0.0.0.0/0; propose restricting authenticated external access after dependency inventory. Internal clients require separate assessment. No setting changed.
4. Review unapplied CI patch and production settings proposal. Production currently On Commit and lacks confirmed approval gates. No production gate, branch protection, monitor or alert recipient was configured.
5. Choose owner + technical responder; approve affordable uptime/error monitoring with strict event allowlisting and no PII/session replay. Trial/free service terms and actual notification delivery remain to verify.
6. Continue targeted genuine reliability testing only with QA data; owner physical iPhone confirmation remains distinct from emulation. Preserve RETRACE interface and all imagery/PDF designs.
7. Supplier: Stadia removed from active shortlist following explicit standard-terms tracing rejection reported by Sean. Spexi verbal CAD2,500/year ~13,333 lookups, Aaron coverage and written rights pending. Mapbox indicative 25,000/year with currency/inclusions/rights unsigned. No vendor contacted or integration approved. Stripe remains on hold.

No autosave, new tool, imagery change, allowance/price change or major infrastructure change authorized by this batch. Stop for owner review.
