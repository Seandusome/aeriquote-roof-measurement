# Default-OFF subscription access enforcement — disposable local QA

## Scope and activation

`subscription_access_qa.py` is registered immediately after existing login/auth-version/employee checks and before allowance-maintenance/business routes. Default `app.config['SUBSCRIPTION_ACCESS_QA']` is False. No environment flag or client header turns it on. The OFF path returns before policy/DB access. Nothing was enabled in a preview or hosted service.

The ON path ALSO requires app.testing, a callable `SUBSCRIPTION_QA_POLICY_PROVIDER`, a matching absolute `SUBSCRIPTION_QA_DATABASE` and an adjacent .qa-marker containing AERIQUOTE_SUBSCRIPTION_DISPOSABLE_QA_V1. DATABASE_URL must be empty. This is a local experiment interlock, not a production authorization boundary. Provider is trusted Python QA configuration, never request JSON/headers. It returns explicit standalone-evaluator inputs for the authenticated business; wrong/missing/ambiguous inputs yield QA unknown diagnostics and preserve EXISTING access, never bypass existing authentication/ownership.

The new `/qa/subscription-policy` and `/qa/subscription/estimates/<id>/download` routes return404 with flag OFF. Download is a frozen saved JSON attachment owned by current business, not a new estimate or a new PDF renderer. Existing public pages/layout/JS/policies were not changed. Existing Codespace checkout/preview untouched.

## Server behavior when explicitly enabled

- Paid-active/cancellation-pending: existing handlers continue through paid-period end. No cancellation scheduler/payment/renewal process added.
- Known120-day retained window or longer protected full-content promise: saved estimate list/single/versions and owned JSON download allowed; save/create, editing-session, job field changes, fresh property/measurement/image sessions, profile writes and draft actions denied403 before handler execution. Draft GET is blocked too because existing draft endpoint can purge expired rows. Root shell can load, but existing measurement controls are not redesigned/hidden; server remains authoritative.
- Saved aerial export rebuild is a read operation only when incoming roofs exactly match the frozen active geometry of an OWNED current estimate or revision. Numeric int/float representation normalized; altered/unsaved/foreign-only geometry denied. Original renderer remains unchanged. One test stubs renderer output to verify this authorization without Google calls; this is NOT an actual imagery/PDF pass.
- At exact expiry, estimate reads/downloads, related image routes and PDF/Print profile preflight denied403; diagnostic state endpoint remains available. No row or image deleted. Previously downloaded data/offline printing cannot be revoked.
- Longer lightweight-only promise: only allowlisted wording/customer/measurement/pricing JSON survives in HTTP responses; stored imagery/provider/session fields excluded. Mutations remain blocked. Existing PDF/Print profile preflight denied because full-content media expired. This is not a redesigned lightweight estimate UI.
- Successful reactivation in explicit inputs restores known retained access (including longer prior promise beyond day120); repeated requests never reset usage/grants. No code accepts/validates payments or mutates subscription records. Provider must supply authoritative period/presence/protected scopes; real adapters remain unimplemented.
- Unknown payment, legacy clock, wrong-business policy, provider failure or ambiguous evaluator result: state unknown header, no new restriction/deadline/grant. Existing access remains unchanged by approved rule. This intentionally preserves older behavior rather than treating unknown as paid or expired.
- Actual complimentary flag or non-paid legacy/dealer plan retains existing entitlement handling. Head Office cannot use QA estimate/export paths. All existing business WHERE scopes, X-AeriQuote-Account guards, owner/employee/auth-version denials continue first and cannot be overridden by a paid snapshot.

## Verification

Run only in a disposable process:
`python -B -m unittest discover -s tests -p test_subscription_enforcement_qa.py -v`
Requires existing project Flask==3.1.2 dependency. Test harness verifies a new empty temporary target BEFORE importing the full real app; DATABASE_URL and provider/email credentials are empty, urllib external requests prohibited. Startup migrations run only against that NEW fictional database. Before each request-test baseline, initialization completes. No Codespace/Render/customer database opened.

13 focused full-Flask application tests PASS. 86 requests have independent before/after snapshots of ALL business tables; every expected status matched and every snapshot stayed equal. These include denials and permitted reads/unchanged save retries/reactivation retries. Separate active changed-edit test creates exactly one revision and preserves all other tables, including allowances and grants. Fixture accounts include active owner, active/disabled/foreign employees, another business, complimentary, legacy dealer and Head Office.

Tested direct API saves, metadata edits, editing sessions, drafts, image/property actions, reads/versions, export preflight and QA saved download. Boundaries: paid-end inclusive read-only, expiry minus1microsecond, exact expiry, longer promises and reactivation. Headers/body cannot spoof paid status or enable OFF flag. Disabled HTML download redirects302 per existing auth; API denial401. No app auth behavior weakened to alter that expectation.

Initial fixture setup used an outdated column-count insert and incomplete payload; corrected fixtures to explicit columns and existing independently priced valid geometry fixture. Auth redirect test expectation corrected to existing302. These were setup/test issues; original validators/auth were preserved. Raw initial/final logs retained. Final tests have no failures. Existing utcnow deprecation warning is unrelated and unchanged.

No browser tests run this round: prior bundled-browser absence/system Chromium socket-permission restriction remains reported. NO actual Single/Expanded PDF rendering or phone pass claimed. Existing client export preflight and map authorization verified server-side only, using a renderer stub for image response. No Google request or key used. No PostgreSQL concurrency or Stripe verification. Earlier evaluator/industry suites remain historical and were not repeated.

## Limitations / before any production work

This gate uses explicit per-business QA policy snapshots. A real adapter must prove payment/retention/usage provenance and handle differing per-record legacy promises; it must not reuse mutable created_at or infer success from account status. Unknown means diagnostic passthrough, not a safe replacement for paid entitlement data. Filtered lightweight JSON is not full original media/PDF recovery. Routes/allowlist/owned geometry projection need review if application endpoints change. This local QA feature is NOT paid launch readiness.

No deletion jobs, Stripe, allowance grants/resets, real payments/emails, public UI changes, credentials or hosted changes. Backup lifetime, required record retention, imagery rights, mailbox delivery and tax setup still unresolved. Phone save/reopen pending; historical lost geometry unrecovered.
