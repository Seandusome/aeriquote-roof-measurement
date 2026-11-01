# Expired-authentication recovery — completed November 1, 2026

Started from checkpoint b05890ae on recovery. No runtime code defect reproduced; no application changes or deployment. Only fictional QA data in the dedicated isolated database was used. Physical-phone touch testing remains pending.

## Live workflow and exact scope

Original workspace tab5 contained unsaved Paving changes: Area1=6,125ft² at$0.10, replacement Area2=2,193ft² at$0.17, Linear188.2640110545814ft at$0.10 and extra service QA recovery verification$37.25. Customer QA EXPIRED LOGIN NOV1, phone306-555-0148, email expired-login-qa@example.invalid, notes FICTIONAL QA ONLY - preserve unsaved work after reauthentication. These were new work since the saved8,940ft²/$1,013.24 revision.

A normal LOG OUT in separate same-origin tab6 cleared browser authentication while leaving original tab5 open. CREATE CUSTOMER ESTIMATE in tab5 returned the real unauthenticated/401 response with instructions to keep that page open and sign in in another tab. Work remained in memory; no tab5 refresh or navigation occurred. This deliberately exercises authentication-loss recovery. A naturally elapsed cookie/signature lifetime, tab closure, browser crash and reload persistence were NOT tested and must not be marked passed.

Owner personally signed back into tab6. Both tabs' rendered account IDs matched fictional owner c417b9a2-51ea-4816-84da-1e597a7de98d. Retried CREATE CUSTOMER ESTIMATE in original tab5. Saved to the same owner's existing property, without duplicate property or estimate. Read-only PostgreSQL validation asserted the exact QA database hostname dpg-dbj4f7lg1s2s73eob8t0-a before every connection and checked stored values using boolean comparisons only. All exact customer fields/notes/extra service, Area quantities/rates, Linear precision, total area8,318 and total$1,155.94 passed. Browser privacy redacts text-field values in DOM evaluations, so exact customer-value assertions rely on this post-save database check and visual PDFs, not comparisons of redacted browser strings.

| Stage | Estimate count | Revision count | Save receipts |
|---|---:|---:|---:|
| Before authentication loss |1|18|21|
| After rejected401 save |1|18|21|
| After same-account login and retry |1|19|22|
| After Back to Dealer View and unchanged CREATE retry |1|19|22|

Exactly one new revision and receipt, no duplicate estimate and no write on401. Existing history retained. No changes to either account's password/settings, plan, allowances, connection, credentials or isolation controls.

## Allowance evidence boundary and charged fixture

Live QA owner has no monthly/paid usage or bonus rows; its recovery allowance bypass remains unchanged. Zero unchanged live counters cannot prove real charged-plan deductions. A new reproducible disposable SQLite experiment, check_charged_recovery.py, uses real Flask password login, a complimentary account with199/200 estimates already used, and the same pending operation before/after401. First successful recovery creates1 estimate/1 receipt and advances used allowance199→200. Unchanged retry, wrong-account409 and a second reauthentication/retry do not change either account's records or usage. Exact stored fictional customer/quote/price also pass. No replacement live account was created. This proves the charged recovery transaction on disposable SQLite; deployed PostgreSQL charged-account recovery is still unverified.

Existing test_workspace_account_binding.py, test_failure_recovery.cjs and test_failure_recovery.py also PASS (business isolation, expired access, stable operation identity, lost responses, concurrency and rollback). No redundant full workflow rerun: application source is unchanged from previously passing7e01cec2 workflows41350107603 /41350107613, including PostgreSQL16/18.

## Recovered PDFs

Actual Single(1page) and Expanded(3pages) downloaded separately, rendered with Poppler and all4pages visually inspected. Both preserve customer name/phone/email, two active Areas, independent Linear, rates, extra service and totals. No stale2,815/6,227ft² Area2 outline or Roofing overlay. Expanded continuation page contains marketing material rather than clipped content. Single remains readable with all pricing visible.

Independent Decimal reference:6125×0.10 +2193×0.17 +188.2640110545814×0.10 +37.25 → subtotal$1,041.39;5%$52.07;6%$62.48; total$1,155.94. Both layouts agree. Results/byte hashes/Git blob hashes/page counts are in results.json. This report/evidence-only checkpoint does not deploy.

## Remaining

Physical iPhone/Safari/Messenger touch; naturally timed authentication expiry; recovery after closing/refreshing an unsaved tab; wrong-account re-login and charged allowances in a live deployed browser remain unverified. Wrong-account/charged cases passed controlled disposable tests only. The original QA browser session remains signed in with the successfully saved recovered estimate. Main, production and customer data untouched; auto-deploy Off; temporary login diagnostics remain disabled.
