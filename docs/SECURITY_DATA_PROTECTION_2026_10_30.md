# Production security and data protection - October 30, 2026

Started at verified recovery HEAD `2eb0de1a5ec2ea8863e1c8fbfbeee4bc71d45f2a`. Both starting GitHub workflows passed, including PostgreSQL. Recovery Render was LIVE `f3065e2` (`dep-dbig6k3bc2fs73bkt6q0`). Main service remains old `c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a`. No production or database settings changed. This is not a commercial launch approval.

## Completed application fix: sensitive logging

Confirmed baseline: loopback Gunicorn access logs included reset query tokens; unexpected Flask exceptions printed sensitive exception text and source lines. Browser handlers also logged raw Error objects that can contain provider URLs or private payloads.

`safe_logging.py` now installs a process-wide LogRecord boundary. It retains safe fixed application messages and Gunicorn lifecycle codes. Other free-text messages and arguments are suppressed, retaining severity, random event ID, exception category and traceback module/line locations without source lines, exception values, locals, chained exception text, raw URLs or credentials. Access records retain an allowlisted method, coarse route category, status, bytes and duration; queries, raw paths/record IDs, headers, referrers, user agents and request bodies are not emitted. This intentionally suppresses arbitrary diagnostic prose rather than guessing every possible password/key pattern.

The application installs the boundary without changing authentication or request handling. A minimal `gunicorn.conf.py` installs it before master/worker startup, using Gunicorn's default repository-root config discovery. It changes no workers, timeouts, ports or process behaviour. Custom deployment commands must not bypass this config with an alternate `--config` or working directory without retaining equivalent protection. Existing recovery command was reproduced locally. Release-file checks require both new files.

All 13 application-owned browser diagnostics now use fixed literal text; no raw error object is sent to the console. The real PDF failure function was executed in a Node VM for Single/Expanded across all six industries, with a secret-bearing thrown URL: only `AQ:pdf-generation-failed` logged, existing customer error message and button recovery preserved. Other browser error paths are statically guarded against raw diagnostic arguments. No imagery request, calculation, correction workflow, PDF design, pricing or allowance logic changed.

Testing: six distinct fictional credential/customer canaries, dict/format arguments, unknown object messages, chained exceptions, stack info, reset queries, headers/cookies/referrers, JSON body and unknown secret-bearing path. Real Gunicorn normal/preload processes and pre-Flask worker boot failure logs contained none of the canaries. Invalid reset links still return400, server exceptions500, lifecycle/access status and duration remain visible. Existing password reset/session/employee regressions must pass unchanged. Old operational audit now reports both logging-exposure findings false; support and readiness gaps remain separately visible.

Scope: application-owned Python logs and current Gunicorn logging, plus explicit browser console calls. This is not a scrubber for historical logs, Render's independent HTTP/proxy/build logs, browser Network panels, external services, arbitrary future direct prints/custom logging pipelines or user-entered support messages. No historical logs or credentials were read, deleted or rotated. Never deliberately add raw payload logging or attach a collector that bypasses this boundary. Verify any future monitoring SDK cannot collect URLs, locals or customer data independently. Authentication and provider response bodies were not redesigned.

## Actual database verification - read-only

Only Render resource metadata and two system-only SQL SELECTs were used. No application tables, customer records, passwords, credential values, user queries or active-session details were read.

| Question | Evidence / limit |
|---|---|
| Instance | AeriQuote-named database `dpg-db019ijncjis7383g3a0-a`, available, paid `0.1c-256mb`, 1GB, HA off |
| Engine | Actual read-only connection: PostgreSQL18.6, primary (`pg_is_in_recovery=false`) |
| Archive configuration | `archive_mode=on`, `wal_level=replica` |
| Archiver activity | 4,352 successful WAL archives, zero recorded failures; last success `2026-10-30T21:43:16.921356Z`; counters reset `2026-10-02T20:32:25.426736Z` |
| Automated recovery | Paid plan is eligible for Render's continuous managed backups; active WAL archiving is corroborated. Base-backup inventory and end-to-end recoverability NOT exposed by connector |
| Frequency | Render describes continuous backup/PITR; no verified base-backup schedule or instance-specific cadence |
| Retention / actual PITR points | Published workspace policy: Hobby3days, Pro+7days; workspace plan and this instance's exact available recovery timestamps unverified |
| Logical exports | Published retention7days. No existing export inventory/timestamps verified or new export requested |
| Safe target | Render supports paid-plan PITR into a NEW instance; newest10minutes excluded. No recovery was performed or resource created |
| QA versus production DB | Service env mappings/environment groups are not readable through current connector. Separation cannot be established from matching names or database inventory |
| Credentials / env risks | Shared credential values, production/test URL identity, pooled env group membership, stable session-secret configuration and least-privilege app role unverified; no credential values requested or printed |
| Network | Metadata permits `0.0.0.0/0` external access. This is broad network exposure, NOT anonymous database access; database authentication still applies. Restrict after approving access paths and testing connectivity |

WAL archive success is not proof of a usable base backup, retention window or restore. No evidence of customer data loss was found or sought. The previous isolated PostgreSQL16 logical restore drill remains useful but cannot certify this managed PostgreSQL18 instance. Actual recovery page and masked environment mapping are the next authorized Dashboard checks; do not send screenshots containing connection URLs/keys. Do not change the allowlist or rotate shared credentials without verifying dependent services first.

## Simplest monitoring and deployment plan - approval required

1. Verify existing Render failure/unhealthy-service email destinations for Sean and a named technical responder; test delivery. Current service setting inherits unknown workspace defaults. This detects platform failures, not every bad quote or browser PDF failure.
2. Add an approved bounded HTTP readiness endpoint (database reachability, no private data) and external uptime alert. Neither current `/health`404 nor `/healthz`302 is a valid database readiness signal. TCP-only checks remain unchanged today.
3. Use one centrally managed error destination with an allowlisted browser event collector for fixed `AQ:` codes only, and aggregate server5xx/save failures. No Error objects, request URLs, screenshots, bodies, tokens or customer information. Suggested starting repeated-PDF threshold: 5 failures/10minutes, deduplicated, tune after synthetic tests. No per-error email storm. No collector or new paid service installed today.
4. Before production promotion: protect main, require full regression/PostgreSQL checks and reviewed approval; extend the full workflow's branch gate only with separate approval. Set production auto-deploy Off and manually deploy exact approved release (or an approved GitHub deployment-environment gate). “After CI Checks Pass” alone does not give human approval. Current On Commit production settings are unchanged.
5. Keep an approved release manifest: full commit, deploy ID, database non-secret ID, schema compatibility and safe rollback target. Git checkpoint alone is not a retained Render build artifact or database backup. Retain an artifact policy appropriate to the production plan; skip pointless docs deployments.
6. Assign Sean as business decision-maker, a named part-time engineer as primary responder and a backup. A part-time person still needs a coverage/response agreement; names, contacts, alert receipt and escalation fallback are pending. No messages or invitations sent.

Rollback must preserve the current customer database and newer records. Check target environment/start settings, session-secret continuity and schema compatibility before an approved rollback. Dashboard rollback disables auto deploy; API rollback does not. The pre-fix `f3065e2` has the documented logging exposure, so it is not a fully secure fallback unless an equivalent logging boundary is preserved. No rollback, release promotion, branch rule, monitoring service, production setting or database change was performed.

## Verification and remaining work

Evidence under `docs/qa/security-data-protection-2026-10-30`.
- Original74-command full local suite PASS after logging fix; updated75-command suite includes executable browser diagnostic test. Final results stored in regression summary.
- New real-Gunicorn secret-canary test PASS; actual normal/preload/boot-failure processes, no physical-device claim.
- SQLite recovery/previous-app compatibility drill PASS, original source preserved.
- Application `6e9457f`: validation run41133925154 SUCCESS; full recovery run41133925126 SUCCESS, recovery job124331538669 and PostgreSQL job124331538352 SUCCESS. New secret-canary regression and all PostgreSQL concurrency/native restore steps passed.
- Render recovery deployment `dep-dbih23ui0phs739e0at0` LIVE exact application6e9457f, completed21:51:12Z. Production main remains unchanged. Final docs checkpoint uses `[skip render]`; same application remains live without an unnecessary redeploy.

Remaining launch gates: verified managed recovery window/backup and QA-production mapping; scoped network/credentials; alert receipt/central PDF monitoring; human-gated production release; named responder; commercial imagery permissions; actual billing integration and physical-device scenarios already recorded. Do not turn this narrow security fix into unrelated development.

Official sources: [Render backups](https://render.com/docs/postgresql-backups), [PostgreSQL18 archiver statistics](https://www.postgresql.org/docs/18/monitoring-stats.html#MONITORING-PG-STAT-ARCHIVER-VIEW), [Render deploys](https://render.com/docs/deploys), [rollback behaviour](https://render.com/docs/rollbacks), [notifications](https://render.com/docs/notifications). Gunicorn default config loading also verified against installed23.0.0 source and executable process tests.
