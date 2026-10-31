# Monitoring and deployment safety - approval proposal, October 31

**Prepared, not applied.** No monitoring account, SDK, paid service, credentials, production settings or branch rules created/changed. No telemetry endpoint or new app feature implemented. Current recovery fixes may deploy only to recovery; production remains untouched.

## Current detection gaps

| Failure | What exists | Missing proof/protection |
|---|---|---|
| Server outage / deployment | Render service status, deploy events and inherited notifications | Actual recipients/delivery unknown; TCP health proves a listening port, not database/quote readiness |
| Failed property measurement / save | UI status, server error responses, transactional guards, safe logs | No central reason-coded incident aggregation or proactive owner alert |
| Invalid or inconsistent pricing | Independent server rejection before writes and allowance changes; regression fixtures | Expected400 rejections are not centrally categorized; latent logic errors need independent synthetic quotes, not uptime checks |
| PDF generation | Fixed `AQ:pdf-generation-failed` console event and retry UI | Browser-local; no central capture/alert. Render server logs cannot observe a client-only failure |
| Login/reset/security | Rate limits, versioned sessions, expiry/single-use tokens and safe diagnostics | No verified burst/attack notification destination |
| Database | Managed status and read-only archiver metadata | No bounded application readiness endpoint, verified actual recovery points or restoration drill on managed PG18 |

Existing safe logging excludes free text, URLs/queries, raw paths, bodies, headers, exception values and source lines. This does not automatically sanitize a new SDK's independent request/session capture or historical/platform logs. User-entered support reports can contain private information and must not be copied into a monitoring event.

## Small-company recommendation

1. **Existing Render notifications first:** verify service/workspace failure notifications reach Sean and an appointed responder. Test a controlled QA failure only after approval. Native notifications cover failed deploys and unhealthy services; they do not prove PDF or pricing correctness.
2. **Independent availability check:** UptimeRobot Free is officially available for commercial use, with50 monitors and5-minute checks. Use one non-sensitive public health endpoint after an approved bounded readiness implementation. Current `/health`404 and `/healthz`302 are unsuitable. Free plan has team/notification-seat limits; confirm owner/responder routing before relying on it. A free Render service also cold-starts, so production hosting and alert thresholds need approval together. No account/monitor created.
3. **One hosted error destination:** evaluate GlitchTip with QA-only, fixed-code events. Published Hobby & Trial is$0 for1,000 events/month and30-day retention; use it for evaluation, not assumed production entitlement. Published Small is$15/month for up to100,000 events and unlimited team members, with90-day retention. Currency, tax, quotas, spend cap, alert features and data-processing terms must be confirmed before approval; no CAD conversion or purchase implied. Hosted service reduces self-hosting maintenance. No SDK installed or account created.

Use manual, allowlisted events rather than automatic exception/request capture: release SHA, event enum, severity, count, coarse industry and random correlation ID. Never transmit passwords, tokens, URLs, query strings, emails, addresses, customer notes, quote payloads, geometry, headers/cookies, screenshots or replay recordings. Disable session replay, automatic breadcrumbs, locals, network-body and default-PII capture. Authentication event data must not identify a submitted email. Validate outbound serialized payloads with fake secrets before enabling any collector; server-side filtering is required as well as browser filtering. Keep raw errors suppressed.

Suggested initial alert rules (not configured): database/readiness outage or new5xx burst;5 PDF failures/10minutes; repeated save failures distinct from expected409 conflicts; unexpected pricing/geometry rejection spike grouped only by reason enum. Deduplicate and rate-limit; recovery notifications should close incidents. Quota exhaustion/dropped events must be observable. Human reports of incorrect quotes or lost data are P1 regardless of automated thresholds. Sean plus a named primary/backup responder need independent contact channels and an agreed response window. No responder has been invented or contacted.

## Concrete release changes ready for approval

- `docs/proposals/production-ci-gate.patch` is an **unapplied** patch adding main/PR/manual triggers and branch conditions to the existing complete recovery/PostgreSQL workflow. It does not deploy anything. Current active workflow still runs only on recovery. Validate on a reviewed staging PR after approval; do not treat skipped/neutral checks as successful required tests.
- `docs/proposals/production-release-settings.json` records proposed values: production Render Auto-Deploy **Off**, protected main with required `recovery` and `postgres_integrity` checks, reviewed PRs, no force pushes/deletion, restricted bypass. These are proposals, not provider API payloads or applied settings.
- Main currently reports unprotected and is linked to an old production service release. First establish actual production domain/service and dedicated database. Prevent On Commit deployment before promoting any code. “After CI Checks Pass” helps but is not explicit owner approval.
- Require Sean's written approval of an exact full commit and environment, then a designated maintainer manually deploys it. Record approval, successful checks, Render deploy ID, database non-secret ID, schema compatibility, environment continuity and rollback target in a release manifest. No deploy hook/token in repo or report.
- A Git checkpoint preserves source, not a database backup or indefinitely retained Render artifact. Keep a compatible known-good build and recovery instructions; verify retention under the chosen production plan. Earlier pre-security builds can reintroduce logging leaks; do not blindly roll back.

## Safe rollback and verification

Pause new releases; verify a compatible target's startup/schema/environment requirements and its correct database mapping before approval. Application rollback must keep the current customer database and later customer writes. Never restore an old database to make an older app work. Render Dashboard rollback disables auto deploy; API rollback does not. No actual rollback performed. Use a new isolated database for separately approved data recovery, reconcile later writes, and obtain approval before switching services.

After approval/configuration, test: failed checks block release; an unauthorized person cannot approve/deploy; a synthetic outage and repeated PDF failure notify both contacts without secret payloads; a rollback in an isolated environment keeps newer estimates/revisions and valid sessions as intended. Only then sign off operations. Required RPO/RTO, backup verification, coverage and billing/licensing are separate release blockers.

## Official sources checked

- https://render.com/docs/notifications
- https://render.com/docs/health-checks
- https://render.com/docs/deploys
- https://render.com/docs/rollbacks
- https://help.uptimerobot.com/en/articles/11604710-who-should-use-uptimerobot-s-free-plan
- https://uptimerobot.com/pricing/
- https://glitchtip.com/pricing/
- https://glitchtip.com/documentation/

Pricing is a published observation, not a quotation or authorization. Sentry was considered, but its official pricing could not be retrieved in a supported format during this audit; no third-party pricing was treated as verified. All production/infrastructure implementation awaits separate approval.
