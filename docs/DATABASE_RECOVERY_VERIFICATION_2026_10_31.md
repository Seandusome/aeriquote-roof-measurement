# Database safety and recovery verification — October 31, 2026

## Decision for Sean

**Do not approve commercial data-protection readiness yet.** Paid PostgreSQL is available and its archive statistics are healthy, but no actual recovery-point inventory or application-to-database mapping was accessible. Nothing establishes that test and production are separate; nothing establishes they are shared either. Treat isolation as an unresolved critical launch gate, not a confirmed shared-database incident.

This assignment was read-only infrastructure verification and planning. No customer rows, credentials, estimates, passwords, SQL statement text or reset tokens were inspected. No exports, restore attempts, new databases, upgrades, migrations, network changes or manual deployments occurred. Only repository documentation changed.

## Starting release verification

- Remote recovery HEAD: `cde3d5b7f41a04584ccf90809a319b88da41f98e`; main unchanged at `c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a`.
- GitHub application validation run `41227746551`: SUCCESS. Complete recovery run `41227746432`: SUCCESS, recovery job `124615339714` and PostgreSQL job `124615339925` both SUCCESS. Existing full local result remains 78/78; no completed application tests were restarted for this documentation-only assignment.
- Recovery live: `dep-dbj2ldrm8hqs73fc0ao0`, application `764f1ff67d1d86f53fdefb44b28182ae8cc6dbbf`. Documentation-only checkpoint deliberately did not deploy.
- Old main service still live at `dep-db5b726k1f9s73e862ug`, commit `c049a04...`; actual commercial production domain/service designation still needs owner confirmation. Nothing was promoted.

## Actual paid database findings

| Check | Verified result | What this does NOT prove |
|---|---|---|
| Instance | `dpg-db019ijncjis7383g3a0-a`, available, paid 0.1c-256mb, Ohio, PostgreSQL 18.6 | Application connection mapping or commercial capacity |
| Storage configuration | 1 GB provisioned; logical DB size 21,903,039 bytes at query time | Full disk/WAL/backup usage, future growth or throughput |
| Availability | HA disabled; system catalog SELECTs worked | SLA, failover or load-test readiness |
| WAL | archive_mode on; wal_level replica; 4,612 successful archives, zero recorded failures | A usable base-backup chain or retained PITR dates |
| Archive timestamp | Last archived 2026-10-31 19:13:07.422881 UTC (13:13:07 MDT); stats since October 2 | Recovery to that exact moment; newest WAL may not be eligible |
| Recovery inventory | Not exposed by available connector | No claim that exports exist, or that any specific date is selectable |
| Account retention | Workspace response has identity/type, no subscription tier | Paid database compute does not establish Pro workspace retention |
| External access | 0.0.0.0/0, valid credentials still required | Anonymous public database access; no breach was established |
| Connection snapshot | max_connections 103; one connection to this DB during aggregate inspection | No active dependency: pooled, idle or intermittent apps can be absent |

Only system catalogs/statistics and aggregate storage metadata were queried. No estimate/account/support tables were read.

### Published capability versus actual protection

Official Render policy: paid databases receive continuous PITR; Hobby workspace retains three days, Pro-or-higher seven. Recovery creates a new instance; the newest ten minutes are unavailable. Logical exports, if created, retain seven days. Free databases have no managed recovery. The actual selectable dates, export list, subscription tier and restoration success for our instance remain unknown.

An isolated new-instance recovery is therefore a documented supported path, **not a performed or validated recovery here**. Its settings must be reviewed before approval; Render says the original external allowlist is copied. Do not assume the new instance is private simply because it is called recovery. Extra instance compute/storage, any workspace upgrade, retained exports/storage and transfer/support charges need a cost preview; exact account pricing was not available from the public pricing page. No zero-cost restore is promised.

The bundled skill's generic daily-snapshot wording is not used as proof of actual daily snapshots; current official continuous-PITR documentation governs this report.

## Test versus production separation

| Service | Verified branch/region | DB ID / role / env groups | Stable session secret |
|---|---|---|---|
| Recovery `srv-db5a2g5ckfvc739fui70` | Recovery branch, Ohio, Free web service | Unverified | Unverified |
| Main candidate `srv-db01g1p42hec73ehu1lg` | main, Ohio, Free web service | Unverified | Unverified |

The workspace inventory lists four web services (the other two are ShingleXtra/Shingle Guard services). No worker/cron service appears. This does not cover external scheduled tasks, undeclared clients or historical deployments. Neither list/get-service exposes environment variables or environment-group membership. `serviceDetails.env` identifies the runtime, not secret values. No read-only connector action lists recovery points or environment groups. No mutation endpoint was used as a substitute for reading. No credential discovery, API-key creation or broader browser access was attempted.

The recovery source uses DATABASE_URL when set; otherwise local SQLite. It generates a random per-process Flask secret if FLASK_SECRET_KEY is missing. These are code facts, not proof of deployed misconfiguration. Free web storage is ephemeral, so missing persistent DB configuration would be critical. An unstable secret would invalidate sessions across workers/restarts. The old main release must be assessed separately; do not assume recovery code equals production code. The old render.yaml names a different service and cannot establish either service's actual variables.

**Needed masked evidence:** for each app, DB resource ID, logical DB equality/difference, role equality/difference, internal/external connection type, linked env-group IDs and whether a stable non-empty session secret is configured. Compare secret equality locally only when needed; never share values, connection strings or reusable secret hashes. Distinct secret values per environment are recommended. Distinct DBs and restricted roles are stronger than account-level row isolation. If sharing is found, it becomes a confirmed critical blocker; change nothing until an approved separation plan exists.

### Role permissions

The connector's current database role is not a PostgreSQL superuser and does not bypass RLS, but can create databases/roles and create objects in public, and owns 28 user tables. Role names were not printed. These are **connector-role** permissions; the app's actual role remains unidentified. If applications reuse this owner role, privilege separation is needed.

Current recovery startup performs CREATE/ALTER operations. Simply revoking ownership or DDL could break startup. Propose separate migration/administration and runtime roles with staged QA verification; do not apply grants/revocations blindly. No permissions were changed. System statistics do not establish any table-level RLS policy or tenant isolation guarantee.

## Expiring QA database

- ID `dpg-dbcjg2brjlhs73dn1g7g-a`, available Free PG16 in Ohio, expiry November 20 at 22:09:13.900851 UTC (**15:09 MST**).
- External allowlist empty. A single aggregate schema/estimated-row/client query was rejected by the connector. No query retries or allowlist changes were attempted. Contents and preservation value remain unknown.
- Earlier Batch4 records say it was created but not populated; actual test workloads ran in disposable local/GitHub PostgreSQL. Current tracked CI uses localhost aeriquote_qa and contains no active reference to this Render database. Historical purpose does not prove current emptiness.
- Same-region internal clients can still connect despite an empty external allowlist. A quiet connection snapshot, absence from source or resource name cannot prove no service depends on it.

**Recommendation: leave it unchanged pending masked dependency and internal metadata verification.** Do not upgrade just because of the notice, and do not certify expiry as safe yet. If no active references and no valuable data, allowing expiry is reasonable. If valuable records exist, seek approval for an encrypted scoped export with retention controls. If active service dependencies exist, seek a migration/retention plan before suspension. Do not rely on the published post-expiry grace period. No export or migration was performed or approved.

## Network security plan — recommendations only

1. Inventory all four service connection identities plus external admin/backup/CI clients and env groups. Current CI is disposable localhost; it does not need customer DB access. Do not infer the other two services' DBs.
2. Prefer internal Render connections for same-region/workspace applications, respecting project isolation. Ohio placement makes this technically possible; actual URL selection is unknown.
3. Restrict paid external access to required trusted admin/backup egress addresses, or disable it if every external dependency has a safe alternative. Hosted MCP has no documented stable egress allowlist available here; restrictions may end this connector access. Do not leave the whole internet allowed solely for AI convenience.
4. Separate environment credentials and migration/runtime permissions under an approved plan. Rotate only after enumerating and coordinating every dependent client.
5. Verify independent responder/recovery access before closing any path. Do not block the only recovery administrator, monitoring or backup jobs. Network rules do not replace credentials or least privilege.

## Practical recovery plan — approval required before execution

| Incident | Safe response | Keep newer records safe |
|---|---|---|
| Accidental deletion | Pause affected writes; preserve original; identify incident time; request approved PITR to a new isolated instance | Compare restored versus current data; reconcile missing rows/revisions with authorized business-scoped review; never replace the entire live DB merely to recover one deletion |
| Corrupted saved estimate | Block affected quote/PDF; preserve revisions and audit evidence; reproduce without customer data | Use an authorized verified revision or reconcile a new-instance recovery; independently revalidate geometry/pricing/customer ownership before approved repair |
| DB unavailable | Check Render status/system metadata and limits; notify responder/Render Support; avoid repeated submissions or blind connection changes | Restore connectivity first where possible; absence of connectivity is not evidence that restoring old data is necessary |
| Failed app deployment | Owner-approved compatible code rollback with current DB mapping preserved | Verify old code will not run incompatible initialization/migrations; retain new customer writes |
| Incorrect migration | Stop affected writes/deployments; preserve schema and data state; investigate compatible forward repair | New-instance restore only if needed, with post-recovery write reconciliation and explicit cutover approval; no blind down migration |
| Total service recovery | Validate isolated target, correct DB roles/env secrets and dependent assets; approve cutover separately | Inventory estimates, revisions, receipts, accounts/permissions, branding, usage/allowances, sessions and external assets; prove no cross-business mixing or replay/double deductions |

Restored sessions/reset state may resurrect revoked credentials or spent tokens. Before a cutover, assess security-version/credential revocations, forced reauthentication and password-reset invalidation; any account changes require an explicit incident plan. Pausing writes and a recorded reconciliation boundary prevent two divergent live databases. Keep the original untouched during validation. Retention/deletion commitments still apply to restored historical records and any later approved exports.

The existing disposable PostgreSQL16 backup drill passed in CI and proves: new-empty-target restore, later source estimates preserved, and a restored backup excludes later writes. It does **not** certify managed PostgreSQL18 PITR, current network/role mappings, restoration of every table/asset, or recovery speed. Existing evidence was reused; no restore was repeated.

### Proposed targets, not current guarantees

- P1 acknowledgement: 15 minutes during agreed support coverage; named primary/backup responder and outside-app contacts required. No 24/7 SLA is established.
- Application rollback RTO: 30–60 minutes, only with retained compatible build, stable configuration and schema compatibility.
- Database recovery RTO: initially 2–4 hours for this small database, **planning allowance, not a measured benchmark**. Include provisioning, validation, reconciliation and owner approval; large incidents or unavailable staff may take longer.
- Proposed recoverable-point age target: 15 minutes for a promptly detected incident, subject to a verified healthy PITR chain and provider limits. A selected point before a destructive event necessarily excludes all later writes; without reconciliation, potential loss is every legitimate write after that point, not merely 15 minutes. Zero data loss is not promised.
- Late-discovered corruption outside the actual retention window may not be recoverable through PITR. Consider approved encrypted offsite logical backups with a business-approved retention schedule; no recurring export/storage/service has been created.

## Priorities and concrete approval plan

| Priority | Next action | Approval/change boundary |
|---|---|---|
| P0 | Read-only Recovery page: earliest/latest selectable times, actual exports, workspace tier, restore access and cost preview | No Restore/Create export/Start Recovery clicks. Share only timestamps/status, not connection secrets |
| P0 | Masked environment mapping and stable secret presence for recovery and production | Read-only verification; if shared, return a separation proposal before changes |
| P0 | Name primary/backup technical responder and agree response targets | Owner decision; no contacts were messaged |
| P1 | Verify QA dependencies/content metadata before November 20 | No network relaxation, export, upgrade or expiry sign-off without evidence |
| P1 | Scoped network/role separation, production release gates and monitoring | Requires explicit approval and rollback/compatibility plan; prior proposals remain unapplied |
| P1 | Controlled managed recovery rehearsal into a new isolated target | Separate approval for costs, data access, isolated settings and deletion/retention plan; never overwrite live |
| P2 | Capacity planning for hundreds of contractors; backup growth/retention and restore testing | Current 256 MB compute/1 GB allocation is not load-certified; no upgrade or pricing change authorized |

Minimal owner action: arrange a read-only Dashboard walkthrough with a technical responder for the two P0 evidence checks. The current connector cannot finish those checks. No request to send secrets or paste environment values is needed.

## Official references checked October 31

- https://render.com/docs/postgresql-backups — current continuous PITR/new-target/retention policy; actual account inventory unknown.
- https://render.com/docs/private-network — private topology and environment isolation.
- https://render.com/docs/postgresql-creating-connecting — external restrictions, encrypted external connections and internal URLs.
- https://render.com/docs/free — ephemeral free service storage and Free PG limitations.
- https://render.com/pricing — retrieved, but numerical current compute/workspace pricing was not exposed in the readable response; exact additional charges unverified.

Markdown backup/private-network URLs returned unsupported content types through the web tool; the corresponding official HTML was successfully retrieved and read. No provider-specific permissions or costs are invented. This report is not a launch-readiness sign-off.
