# Recovery QA database isolation — costed approval plan

October 31, 2026. **Planning only. Nothing provisioned or changed.** Live QA writes remain paused by instruction, not an implemented service suspension. Do not open the recovery application or import its app with shared credentials. Existing original paid database, production service and all customer records must remain untouched.

## Recommendation and cost

Create a **new paid Render PostgreSQL18 instance in Ohio**, plan `0.1c-256mb` (legacy basic-256mb), with 1 GB storage and newly generated QA-only credentials. Proposed resource name: `aeriquote-recovery-qa`; proposed distinct database/login names: `aq_recovery_qa` / `aq_recovery_qa_owner`, subject to available naming constraints. Names are proposals, not existing resources.

| Option | Published compute/month, USD | 12-month equivalent, USD | Assessment |
|---|---:|---:|---|
| New 0.1c-256mb | 6.00 | 72.00 | Recommended minimum for light functional QA: 0.1 CPU, 256 MB RAM, published100 connections |
| New 0.5c-1g | 19.00 | 228.00 | Optional escalation if measured QA contention/memory pressure warrants it; not approved |
| Existing free Batch4 PG16 | 0 before expiry | Not a durable annual option | Expires November20; no managed recovery; contents/dependencies unverified |
| Upgrade existing Batch4 | Final upgrade preview required | Not quoted | Requires content audit, permission and major-version decision; less clean than fresh PG18 |
| Another logical DB on original paid instance | No separate compute | Not proposed | Shares infrastructure/admin scope; would change original instance and violate this assignment |

Actual paid database Plan page was read without clicking Edit or selecting anything: $6/month for0.1c-256mb, $19/month for0.5c-1g. Current official public pricing, rendered in browser, explicitly lists **1 GB SSD included** and expansion at$0.30/GB. USD is supported by Render's own pricing-comparison explanation. No CAD conversion or card exchange rate is assumed. Annual figures are multiplication by12, not an annual contract or prepayment.

**Expected incremental base: US$6/month / US$72/year before tax. Conservative approval budget: up to US$6.30/month / US$75.60/year before tax**, pending creation-summary confirmation of whether the initial1GB is separately billed. The pricing page says included, while a generic official cost article describes compute plus storage; do not silently pick the more expensive interpretation or promise a final invoice. If the actual summary exceeds the approved ceiling, stop. Payment conversion, taxes, extra storage, outbound traffic, build usage and any professional work are excluded. No workspace upgrade, HA, replica, paid web-service change or export storage is required by this minimum proposal. Existing production costs remain separate and unchanged.

Start at1GB, no automatic storage growth/HA/replicas proposed. Monitor usage; request approval before growth or larger compute. The original logical database measured about21.9MB, but it is not being copied and that size does not predict load capacity. Budget concurrency at no more than about10 simultaneous QA DB operations initially, reserve capacity for platform/maintenance, and measure rather than treating100 connections as100 busy users. This is not a production load certification or a change to app pool settings.

Paid backups/PITR are supported; current workspace Recovery UI shows a three-day window. A fresh database's history builds over time, not instantly. A seven-day window requires a different workspace entitlement; no upgrade proposed. Verify the new instance's actual Recovery page after provisioning. Published PITR creates a new target and excludes the latest ten minutes; logical exports retain seven days if created. No restore/export is part of this isolation plan.

## Compatibility and existing QA reuse

- Match existing paid PostgreSQL18 major version; accept the provider's current supported18.x minor after checking. psycopg3.2.10 is already pinned. CI currently proves PostgreSQL16; it does not certify18. Run isolated18 schema/functional/concurrency verification as a future acceptance gate as well as canonical CI.
- Fresh empty instance is preferred. Do not clone, restore, dump, copy table rows, account IDs, password hashes, estimates, profiles, usage or sessions from the original database.
- Batch4 resource `dpg-dbcjg2brjlhs73dn1g7g-a` is available Free PG16, expiring November20. No current inspected DATABASE_URL points at it, but contents and external/custom clients are unknown. Do not clear it, repurpose it or approve expiry merely because of its name. Reuse requires an independent read-only content/dependency audit and upgrade/version approval first. A new paid resource avoids that uncertainty.

## Immutable guardrails and exact target manifest

| Target | Permitted future scope after separate approval |
|---|---|
| Recovery srv-db5a2g5ckfvc739fui70 | Only application allowed to receive the new QA connection; controlled stop/restart/deploy of existing approved code needed |
| Original DB dpg-db019ijncjis7383g3a0-a | Leave settings, roles, data and backups untouched; never use for initialization/fixtures |
| Old main srv-db01g1p42hec73ehu1lg | No configuration, deployment, credential or connection change |
| New QA DB | Record actual assigned ID at creation; must differ from every existing resource and use distinct login/credentials |

Record pre-change branch/app SHA, deploy ID, current nonsecret DB identity, environment key names/presence, QA flags and stable session-key presence. Verify actual production domain designation with Sean. Do not record URLs, passwords or secret hashes. Original app at c049a04 and recovery application at764f1ff are different releases; this operation must not promote either.

## Future implementation procedure — NOT executed

1. **Approval gate:** approve cost ceiling, fresh empty PG18/Ohio resource, QA credential creation, controlled recovery stop/configuration/restart and tests. Confirm maintenance time and named operator. No production changes included. Confirm the existing CI results on the chosen exact recovery commit.
2. **Quiesce recovery only:** coordinate users to stop test work. Disable recovery automatic deployments and stop/suspend only srv-db5a2g5ckfvc739fui70 using the approved maintenance method; verify old instances have drained. Saving a new environment can deploy automatically: inspect the intended UI/API behavior first, and do not apply if old shared-DB workers could remain active. Never suspend production or change its deployment settings. If the recovery stop is not verifiable, stop the procedure.
3. **Provision the new QA instance:** select the same workspace/Ohio, PG18,0.1c-256mb,1GB, no replica/HA/autoscale, clearly QA-only name and fresh unique role/credentials. Confirm final price/currency before creation. Prefer empty external allowlist/internal networking. Do not weaken original DB rules. Internal QA/admin access must be planned because the Free web service has no interactive Shell; do not assume a remote shell or hosted MCP can reach a closed allowlist.
4. **Verify empty target before writes:** record assigned QA resource ID, supported version and availability. Compare host/resource, logical DB and login against the original using only masked equality results; all must be distinct. Through an authorized internal path or separately approved trusted admin connection, confirm no user tables/business rows exist. No original DB query or credentials in the bootstrap process. If the safe internal path cannot be established, stop rather than broadening external access.
5. **Credentials and privilege scope:** use the new QA-only owner credential initially because current startup performs CREATE/ALTER. It must not be a reused production credential. Keep the provider administrative credential separate from the app where supported; a full migration/runtime privilege redesign is not part of this change and needs separate engineering approval. Do not revoke original grants or rotate original secrets.
6. **Change only recovery DATABASE_URL:** while recovery is stopped, replace that single service-level key with the new internal URL through secure Dashboard input. Keep FLASK_SECRET_KEY exactly as configured; preserve all provider keys, pricing, flags, startup/build commands and code. Do not change a shared env group (none currently exist). Review the actual target again before saving. No secrets in terminal arguments, tickets, screenshots, git or chat. A blank URL is forbidden because it selects ephemeral SQLite. If Save necessarily restarts/deploys, perform it only within the specifically approved restart window after new-target verification; otherwise save without deploy and resume with the new environment. Do not blindly use a historical Render rollback.
7. **Initialize new schema using existing code:** confirm the persisted masked target before starting any worker. Start the exact approved recovery code with the new connection. `estimate_db()` acquires an advisory lock and runs `_initialize_estimate_schema`, including support/auth/credit tables. Importing app.py also calls `reset_trial_usage_for_v1196_testing_once()`, which writes a migration marker and can reset trial usage. On an empty QA database this affects only fictional state; importing with old credentials would be unsafe. Do not run a copied manual DDL schema or initialize the original database. Check generic safe startup status and QA-only schema inventory; no customer logs.
8. **Fictional seed only:** confirm all business/estimate tables empty apart from internal schema/migration bookkeeping. Create newly named “QA TEST” owners/businesses through existing signup/account flows; owner UI creates new employees; use unique new IDs, invented customer details and test passwords entered securely. No real signup/reset email sends. Seed Basic/Pro/Business fixtures and complimentary rules only in QA under a reviewed scoped fixture plan. Do not adapt localhost-guarded CI scripts to Render. `prelaunch_browser_server.py` forces temporary SQLite and mocked imagery; it is not a Render PostgreSQL seeder.
9. **Session and QA restrictions:** because FLASK_SECRET_KEY is preserved, old cookies may still decode but must not authenticate against absent original IDs. Verify fresh login and reject stale original-session access without resetting any real account. Manual Roofing and Vector flags are ID-allowlisted: new QA account IDs may require separately approved updates to only the existing recovery QA-ID allowlists. Do not reuse customer IDs to avoid this or globally enable features. If no allowlist permission is granted, report these live checks pending and retain isolated local evidence.
10. **Verify isolation before tests:** confirm recovery runtime/current configured URL points only at the new resource, original main still has its original masked identity, and both logical DB/role/credential identities are distinct. Confirm no duplicate alternate URL/secret-file/env-group overrides. Recheck original service configuration read-only; do not issue app requests that could initialize old schema. Verify no customer records were imported into QA through empty-before/fictional-only-after inventory.
11. **Acceptance tests:** execute the checklist below solely on the new QA DB and disposable local/CI targets. Keep QA blocked from general use until every required gate passes or Sean accepts a clearly documented limitation.
12. **Handover:** record exact new resource ID, recovery deploy/application commit, original deployment unchanged, test evidence, backup window, costs and operator; update resume. Any automatic-deploy setting restoration requires approval and proof future deployments retain the isolated target. No original records are moved/deleted, including old QA/demo accounts; those accounts will not automatically appear in the new QA site.

## Rollback and failure handling

- Failure before switch: keep recovery stopped on its old configuration; do NOT resume it while it still has the shared connection. Preserve original and partially created QA resources. Seek correction approval.
- Failure after switch: keep the new QA URL configured and stop recovery if necessary. Never blank it, reconnect to the original or restore an old configuration as routine rollback.
- Code rollback, if needed, must retain the new QA connection and current schema compatibility. Render code rollback/environment behavior must be verified first; no automatic historical rollback that might revive original credentials. No app change is needed by the planned isolation itself.
- Failed bootstrap must be diagnosed in QA without dropping tables or deleting fixtures/resources by default. Reinitialization, larger plan, extra network access or credential change requires scoped approval. Preserve both databases; no restore over either original or newer QA work.
- Lost unsaved browser drafts may not be recoverable across the maintenance restart. Warn testers to stop first; do not save pending drafts to the original database to preserve them. Existing shared records remain untouched, not migrated.

## Required post-implementation verification checklist

| Gate | Evidence required; no current claim of completion |
|---|---|
| Runtime isolation | New Render ID/logical DB/login distinct; authenticated runtime metadata agrees with service config; no stale old workers |
| Credentials/session | QA credentials not production; persistent session key unchanged; new login works, stale original account cannot access QA |
| Fictional data | Empty initial business tables; only approved QA identities/measurements after seed; no dump/clone/import from original |
| Businesses/employees | Owner A/B and employee A; own records accessible, cross-business403/404; owner reads employee estimate; disable/reactivate/session checks |
| Measurements | Six industries; multiple Areas+Linear, irregular geometry, pitch confirmation/detached roofs where QA-enabled; independent geodesic checks |
| Corrections | RETRACE OUTLINE, Save/Cancel/Undo, repeated cycles; original preserved until confirmation, independent Line/other Areas remain; invalid/overlap rejected |
| Persistence | Save/reopen/refresh; interrupted and duplicate submissions; stale revisions/conflicts; no loss, duplicates or wrong-owner saves |
| Prices/taxes | Independent quantities, rates, discounts, GST/PST/HST settings, rounding and totals match preview/saved record |
| PDFs | Actual Single/Expanded downloads and rendered visual inspection agree with geometry/prices/taxes/customer/branding; no design change |
| Allowances | 25/75/200, shared employee usage, complimentary fixtures; failed loads/reopening/duplicate calls not charged; controlled renewal boundaries and concurrency |
| Automated tests | Canonical full regression and disposable PostgreSQL CI; additional isolated PG18 schema/concurrency evidence, never customer DATABASE_URL |
| Production protection | Original service/config/deploy unchanged; no original target in QA runtime/seed/test process; no QA writes against original |
| Device limits |320/390/768 browser checks; real iPhone remains distinct and owner-verified, not inferred from emulation |

“Production records unchanged” must mean this operation never writes to them. Do not promise byte-for-byte global immutability if legitimate production traffic can write concurrently. No customer-row export/hash/restore should be introduced to manufacture that assurance. Use target/role separation, process drain, scoped execution/audit evidence and unchanged production configuration; record any verification limits.

## Approval decisions

1. New paid QA PG18 resource at expected US$6/month, conservative ceiling US$6.30/month before tax pending final quote; no annual prepayment or broader spending authority.
2. Controlled recovery-only stop, auto-deploy pause, DATABASE_URL replacement and restart/deploy of existing approved code. Original service/database unchanged.
3. QA-only synthetic fixtures and tests; any required existing manual-Roofing/Vector ID-allowlist updates require explicit inclusion before changing those settings.
4. A safe QA-only bootstrap/admin path if internal access is unavailable. Do not add open network access as an assumed workaround.

If these are not approved, continue disposable local/GitHub testing only. The current shared database remains a critical live-QA blocker.

## Verified sources and checkpoint

- Current official compute catalog: https://render.com/docs/compute-plans (Markdown retrieval unsupported; official HTML read).
- Actual Dashboard read-only cost view: https://dashboard.render.com/d/dpg-db019ijncjis7383g3a0-a/plan — no Edit/plan control activated.
- Public rendered pricing: https://render.com/pricing — $6/$19, first1GB included, expansion$0.30/GB. Generic cost article differs on storage inclusion; final order summary resolves it.
- Currency context: https://render.com/articles/render-vs-netlify — provider explicitly describes its published prices in US dollars.
- Billing/storage discussion: https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses ; https://render.com/docs/faq .
- Backup/version/internal connection policy: https://render.com/docs/postgresql-backups ; https://render.com/docs/postgresql-creating-connecting ; https://render.com/docs/free .

Starting recovery HEAD be3e59e529232a0c94363e10bc435cb4b4143112; both GitHub runs41234825020/41234825028 SUCCESS. Recovery still live at764f1ff, dep-dbj2ldrm8hqs73fc0ao0. Main remains c049a04. No live app QA, database writes or new regression runs were initiated for this planning assignment. This document's containing commit is the new documentation checkpoint and uses [skip render]. Stop for approval.
