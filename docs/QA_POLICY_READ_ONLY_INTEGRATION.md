# QA-only read-only account/policy integration

This is a separate diagnostic program, not an AeriQuote route/plugin. `qa_policy_view.py` never imports app.py, starts its startup migrations or registers with its Flask application. It listens ONLY on127.0.0.1, serves a marked fictional view/JSON, and has no mutation controls or write endpoints. It is NOT production authorization, a multi-user admin tool or an authenticated business data endpoint. Never use it with a customer database.

## Run in disposable local QA

1. From source root, create a NEW EMPTY directory using `qa_policy_fixtures.create(path)`. It verifies the empty target and writes the fictional marker before opening its new SQLite file. It refuses existing files. No DATABASE_URL, Render config or credentials are read.
2. `python qa_policy_view.py --fixture-root /absolute/new/fixture --port 0` prints its loopback-only URL. It accepts only marked, digest-matching fictional account data and the fixture's explicit account allowlist.
3. For guard comparison/tests, use existing project dependency Flask==3.1.2 from requirements.txt. Run `python -B -m unittest discover -s tests -p test_qa_policy_view.py -v`. No payment/provider dependency is needed.

Read-only connection is SQLite URI mode=ro, immutable=1 with query_only=ON and an authorizer rejecting writes, attachment and changing PRAGMAs. Database SHA256 is checked before opening. Fixtures are sealed/static; immutable reads are intentionally not for a changing production database. Missing/invalid/unmarked targets are refused. Fact files and fixture marker/digests are QA provenance controls, NOT a production security/authentication boundary.

## Mapping and explicit unknowns

- Read account status/plan from dealers, per-period usage from account_subscription_usage, extra bank from account_allowances and selected retained estimate from estimates. These columns follow the actual app read schema; the fixture is a selected-column mirror, not a complete deployed database/migration test.
- The application currently has no authoritative payment-confirmed period, cancellation, reactivation or retention-deadline schema. Those facts live in an explicit FICTIONAL QA facts.json sidecar, labeled as such in the view. They are not fabricated from an active account, plan code, created_at, last login, mutable estimate created_at or provisional account_billing_periods row.
- Exact period-start matching selects verified-period counters; no fallback to lifetime or another provisional period. Missing usage/bank/upgrade inventory is flagged, not assumed zero. No upgrade grant or allowance mutation occurs.
- Full/lightweight content presence is explicit QA inventory plus a matching estimate-row existence check. A row/payload alone does not prove actual imagery exists or licensing/retention rights. There is no imagery-provider call, measurement or PDF test.
- Missing payment/retention facts return unknown and gap messages without calling the evaluator. Unknown legacy deadlines remain null/review-required within the evaluator. Each QA result explicitly says deletion_authorized=false and enforcement_enabled=false, INCLUDING expired cases. Calculations are never a deletion command.

## Comparison with current source

The probe executes the exact AST/source body of `require_dealer_login` from app.py in fictional Flask request contexts and read-only connections. It preserves its active/disabled-account and auth-version logic; no full app import/startup, login or endpoint action occurs. GET/POST probe results are AUTH-GUARD COMPONENT observations only, not actual estimate-save/PDF or complete-route verification. Source-body SHA256 recorded in results.

`account_credits.paid_usage(... initialize=False)` also runs as the existing read-only application calculation against fixtures. No period/counter rows are initialized. Independent file hashes before/after prove no fixture mutation.

| Case | Evaluator | Existing guard component | Conflict |
|---|---|---|---|
| Active, confirmed fictional period | paid_active | allows | Consistent for this scope, not payment verification |
| Cancellation pending | paid_active, renewal scheduled=false; paid-end deadline shown | allows | Guard has no cancellation/renewal scheduling model |
|120-day retained window | retained_read_only | GET and POST pass guard | No subscription read-only guard implemented |
| Expired | expired | GET and POST pass guard | No subscription expiry enforcement implemented |
| Reactivated, longer promise | paid_active, retained full content eligible | allows | Access coincides, but app has no payment-linked reactivation logic |
| Unknown legacy | review_required, expiry unknown | allows | App cannot reconcile protected retention deadlines |
| Missing payment or retention | unknown | allows | Active flag/plan/provisional period is not confirmed payment or retention evidence |
| Disabled account | denied | denies | Existing security denial remains separate from billing policy |

The provisional usage reader returns account_anniversary_provisional limits/usage even for missing payment facts. Do not treat that output as successful renewal, grant authority or entitlement correctness. These are documented gaps, not enforcement changes or proof of a completed payment system.

## Evidence and limits

Nine focused integration tests cover all required states, mapping, unknowns, guard comparison, provisional usage, rejected writes, sealed-target allowlisting, GET-only HTTP and escaped HTML. They fingerprint every fixture file before/after each test. Preserved fixture includes fictional accounts, balances, estimates, revisions and drafts. No real account work is read or modified.

Local browser layout inspection was attempted but BLOCKED: bundled Playwright Chromium was missing, and installed /usr/bin/chromium failed at startup with `socket() failed: Operation not permitted (1)`. HTTP/HTML functional assertions pass; no browser visual or mobile-layout pass claimed. Static self-contained HTML and JSON are preserved for review. Original40 evaluator tests remain historical on a43f7d1, evaluator unchanged; not repeated this round.

No enforcement, public UI/policy changes, Stripe, deletion jobs, payments, real emails or hosted/credential changes. Existing Codespace checkout and all earlier application fixes untouched. Open external dependencies remain actual backup lifetimes, required record retention, imagery rights and mailbox delivery. Physical phone save/reopen pending; historical lost geometry unrecovered.
