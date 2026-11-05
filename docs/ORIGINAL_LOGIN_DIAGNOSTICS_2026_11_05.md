# COMPLETE — Original Head Office login VERIFIED; diagnostics OFF; PAUSED

November5,2026. Sean performed the authorized single normal sign-in; no agent retry, session injection or password/account correction.

## Captured successful attempt

Original service srv-db01g1p42hec73ehu1lg / aeriquote-roof-measurement, deployed diagnostics-only source **2e116ed43db395d705a847f730fc2e522401c084**. At21:55:25–26UTC (15:55Regina), one correlated request **41c3abc912644c3e81959fd444b86b30** emitted exactly:
received → owner_found → owner_active → owner_verifier_pass → session_created → response_redirect.

Access log confirms POST /dealer-login returned302 at21:55:26UTC. Browser reached authenticated measuring workspace with DEALER MANAGEMENT and LOG OUT. Clicking normal DEALER MANAGEMENT loaded https://aeriquote-roof-measurement.onrender.com/head-office/dealers with headings AeriQuote / Admin, Overview and Customer Accounts; access log200 at21:57:07UTC.

This establishes account lookup, active-status acceptance, password verifier success, session creation, successful redirect and Head Office authorization for this attempt. It does **not** identify the causes of earlier failures, validate every earlier submitted email or imply a password reset was needed. Diagnostics were observational; no password or account correction made. Do not describe this as a proven fix of the historical failure.

## Diagnostics cleanup — VERIFIED OFF

Immediately after capture, merged ONLY AERIQUOTE_ORIGINAL_LOGIN_DIAGNOSTIC_UNTIL=0 (replace:false). Render automatically deployed exact same2e116ed4 as **dep-dbmfn7qfngtc73f8mcag**, LIVE21:57:32UTC. Dashboard Environment field independently read as exactly0/OFF and rehidden. No duplicate trigger or new source commit for cleanup. DefaultOFF/expiry guard remains in source; disabled runtime flag makes current logging inactive.

After cleanup LIVE, refreshed existing signed-in Head Office dashboard: same /head-office/dealers URL and positive Admin/Overview headings, HTTP20021:58:19UTC on new instance hbpkk. Session remains usable across cleanup deploy. No additional login needed or submitted. Cropped dashboard proof captured without account-list rows.

Read-only database confirmation: original account58279332-0996-4bdd-9a6c-e202f40c5c0c / sdusome@diitalk.com active, Head Office role true. No credential values/hashes/cookies/bodies logged or stored. Existing secrets and DATABASE_URL preserved by merge-only config updates. Recovery auto-deploy independently rechecked no/off. Original OnCommit setting unchanged. Spexi/payments/two-session save task remain paused.

## Source/checkpoint boundary

Main remains the reviewed **single-app.py** diagnostics commit2e116ed4, based on originalc049a04. No recovery/top-up/PDF feature deployed; existing recovery branch work unchanged. This checkpoint document is on diagnostics/original-login-nov05 only, so saving it does not trigger original main deployment.

Current containing documentation commit is the final checkpoint. Original login and dashboard confirmed for this attempt; earlier failures remain unexplained. Diagnostics OFF verified. Pause; no more testing/account repair/deployment authorized by completion.

---

Historical preparation note below is superseded where it says logging enabled or attempt pending.

# Original service temporary login diagnostics — controlled attempt pending

Approved by Sean November5: prepare/test/deploy temporary diagnostics only on original service, exact sdusome@diitalk.com, defaultOFF; enable briefly for one user-performed normal login, inspect stage, then disable. No credential reset/account correction authorized.

Base original source/main c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a. Reviewed diagnostics commit **2e116ed43db395d705a847f730fc2e522401c084**. GitHub compare: one file app.py,62 additions/15 deletions; only password_ok/dealer_login AST changed. No recovery/top-up/PDF code. Local56 behavior/scoping/expiry/privacy cases plus employee fallback, lookup/session errors PASS. Every custom log line only AQ_LOGIN_DIAGNOSTIC + fixed allowlisted stage + random32hex request ID. No emails/passwords/hashes/cookies/bodies/exception text logged. Authentication/database/account behavior parity tested in disposable SQLite/Flask.

Main fast-forwarded with expected-head lease from c049a04 to reviewed2e116ed4; original OnCommit auto-deployed. Initial **dep-dbmfkhec6qcc73ef5ebg** reached LIVE with switch absent(defaultOFF), verified environment keys. Then merged only AERIQUOTE_ORIGINAL_LOGIN_DIAGNOSTIC_UNTIL=1793916427 (2026-11-05T22:07:07Z). Tool automatically triggered **dep-dbmfl5mi0phs739e5ppg**, exact same2e116ed4; LIVE21:53:08UTC. No duplicate deploy trigger. Code gates exact original RENDER_SERVICE_ID srv-db01g1p42hec73ehu1lg + normalized exact email; invalid/expired/>30min deadline disables logging.

Current state: **diagnostics enabled until22:07:07UTC at latest** (automatic expiry safety). User normal sign-in handoff prepared on originalLoginTab at https://aeriquote-roof-measurement.onrender.com/dealer-login. Secure email-only fill visually verified exact sdusome@diitalk.com. Password blank/unread. No diagnostic event as of21:54:09UTC, no actual login submission yet. User is instructed enter existing password privately and DEALER LOGIN once. Do not submit on their behalf or ask for password in chat.

Immediately after user attempt: inspect original page and logs filtering AQ_LOGIN_DIAGNOSTIC on srv-db01g1p42hec73ehu1lg in confirmed Shingle Guard tea-daaurjp5efls7391kvj0; correlate one random ID, identify last stage without guessing. Then **merge only AERIQUOTE_ORIGINAL_LOGIN_DIAGNOSTIC_UNTIL=0 with replace:false**, observe automatically triggered same-commit deployment, waitLIVE and verify OFF. Do this cleanup even if attempt inconclusive. No password/account repair or schema/binding changes without explaining evidence first. Source remains defaultOFF after cleanup; removing temporary code can be a separately reviewed cleanup if desired.

Original real account/database bindings preserved. No recovery deployment or role change; recovery remains isolated. Spexi/payments/two-session save test paused. This note is on diagnostics/original-login-nov05 branch only; main remains reviewed single-file2e116ed4. Do not push documentation to main while OnCommit enabled.
