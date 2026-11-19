# Durable fictional payment journal — November 19, 2026

Parent:12af4acf3a5d8c6af1c2cd14740a4dbabe89381a. Standalone local PostgreSQL layer feeds the existing `stripe_fixture_boundary.normalize` and unchanged `subscription_events_qa.transition`. No app import, HTTP route, signature verification, Stripe SDK/retrieval, credential, checkout, account mutation, enforcement activation or deletion. Existing app previews and checkouts untouched. Proposed API pin remains2026-10-28.endive; only recorded fictional Stripe-shaped objects used.

## Data and transaction boundary

`LocalJournal` accepts only an explicitly marked database `aq_durable_fiction` at127.0.0.1. Before EVERY transaction, it verifies actual database/data_directory/server address/port, fsync=on and synchronous_commit=on against the locally recorded target. No DATABASE_URL, hosted connection or application database configuration is read. Local marker interlock is not authentication. New QA cluster was initialized separately; its initial server target was verified BEFORE CREATE DATABASE or schema/fixture writes. Native PostgreSQL16.2 and psycopg2-binary2.9.10 were installed in a task-only package directory; no application dependency files changed. PostgreSQL required loopback TCP; Unix-domain socket creation was denied by this runtime. Server and client subprocesses ran under one launcher because separate tool executions have isolated loopback namespaces. Logs preserve the startup failures and successful local target evidence.

Tables:

| Table | Purpose |
|---|---|
| qa_business | Server-owned fictional binding and current policy projection; unique account/customer and account/subscription |
| qa_inbox | First exact raw notification bytes, SHA256, local business/account/event identity; immutable |
| qa_deliveries | Every committed delivery's exact bytes/hash/outcome, including duplicates/conflicting receipt bodies; immutable |
| qa_facts | Separately supplied simulated canonical/contract inputs and hash; first facts immutable |
| qa_task | Durable received/reconciled/pending/retry/applied/duplicate/observed_no_grant/review state and issue |
| qa_normalized | Validated normalized domain facts and semantic fingerprint; immutable |
| qa_applied | Unique business/operation result and fingerprint; immutable |
| qa_history | Append-only per-business before/after snapshots, phase/outcome/reason and hash chain |

All stateful paths acquire the business row lock before event task locks, serializing that business across process workers. Distinct businesses have distinct state/keys. Global account/event identity prevents another business from reassigning the same notification; local account/customer/subscription uniqueness prevents ambiguous registration. Supplying another business's event/contract/canonical objects fails lookup or normalization with no foreign projection/balance change. This is service-internal fictional business scoping, NOT a new application user/employee authorization layer or PostgreSQL RLS implementation.

Receipt commits raw bytes, task and history together. Reconcile commits normalized facts/task/history together. Apply commits operation uniqueness record, changed projection, final task status and before/after history together. A process dying after state UPDATE but before commit rolls the entire transaction back. No durable claimed/processing lease is left stranded: uncommitted work remains at the previous committed stage. Same event and same semantic operation deduplicate; changed raw receipt bodies or changed validated financial fingerprints are held for review. Both already-queued conflicting causal branches are held, not selected by arrival timestamp. Late competing facts cannot overwrite an already committed operation. Missing causal predecessor remains pending; stale predecessor requires review. Event.created is not causal order.

Mutable task/projection updates are audited. INSERT-only journal tables reject UPDATE/DELETE/TRUNCATE via PostgreSQL triggers. Tampering tests cover history/inbox/facts/applied records; the independent auditor verifies raw hashes and full history continuity/hash chains. This protects ordinary journal APIs/DML, not an administrator disabling triggers or rewriting database files. Binding is server-owned and not exposed to notification callers; this QA database owner is not a production least-privilege role design.

## Where real authentication/retrieval must occur — NOT implemented

Before `receive`: a future ingress must verify the exact RAW request bytes against Stripe-Signature, endpoint secret, timestamp tolerance, expected Stripe account/context, test/live mode and pinned version. It must derive the business from a unique server-owned mapping, never a client business ID, email, metadata or browser redirect. This round's `receive` is a fictional method and DOES NOT authenticate input. Preserve raw bytes; don't parse/re-serialize before real signature verification.

Before `supply_simulated_facts`: future authenticated retrieval/reconciliation must obtain canonical invoice + complete lines/payments, subscription/items/periods/pending updates, customer, exact prices/products, PaymentIntents/charges/refunds/disputes/credit notes and authoritative purchase/proration/causal history. Reconcile amount/currency/status/service periods and local immutable quote. This method only stores supplied recorded FICTION, not authenticated retrieved data. Incomplete/conflicting facts remain review; there is no automatic reviewer override, fact replacement or inferred paid benefit. A controlled reviewed release/new-reconciliation workflow remains to design before real integration.

Only after receipt COMMIT may real ingress acknowledge durable acceptance. A crash BEFORE commit cannot guarantee persistence of never-acknowledged bytes: provider/client redelivery is required and explicitly tested. A crash AFTER commit but before response retains the event; redelivery deduplicates. No claim that a provider that never retries can recover uncommitted data.

## Fresh focused results

20 named tests PASS in the final suite (8.453 seconds), using actual local PostgreSQL and separate worker processes. Earlier15-test in-round run also passed; no unrelated suite repeated.

- Worker shutdown/restart preserves received events and separately stored simulated facts.
- Abrupt `os._exit(86)` before receipt commit, after receipt commit/lost ACK, during reconciliation, after reconciliation commit, after projection write, after final history/before application commit and after application commit/lost response.
- Independent before/after SQL confirms rollback/no partial grant at uncommitted boundaries, durable queued stages at committed boundaries and exactly one eventual application.
- Raised transient reconciliation and application failures record retry and later succeed once.
- Six competing subprocess workers; SQL observed3 simultaneously blocked on locks before release. Duplicate same-event deliveries and different-event same-operation notifications grant once.
- Basic23 used ->Pro52 remaining, extras7 lookup/11 estimate, original paid period/renewal date and saved-work sentinel preserved. No repeated allowance grant or usage reset.
- Conflicting raw receipt before processing held; conflicting financial operation after application cannot regrant; both queued causal branches held. Missing canonical objects/incomplete subscription/wrong currency/refund facts held without benefit change.
- Wrong-business processing/supplied facts and duplicate binding registration cannot alter another business. Exact raw body retained. Journal DML tampering rejected.

Additional actual POSTMASTER tests: twice stopped the new local server with `pg_ctl -m immediate`, restarted and verified crash recovery. Reconciled-not-applied event survived exactly; committed application survived second restart; repeated processing left one operation. These are real local PostgreSQL restart results, not a simulated browser/Stripe event or hardware power-loss claim.

Independent auditor imports neither app, normalizer, adapter nor evaluator. Read-only raw SQL audit PASS across40 fictional businesses,45 inbox events,60 committed deliveries,45 facts,34 normalized records,29 committed operations and230 history rows (both in-round suites + additional restart case). It checks unique operations, status/result references, event/business fingerprints, raw hashes, per-business history chains and continuity, no-change denied/duplicate/observed transitions, preserved original usage/extras/work/period, nonnegative balances and exact52 constants.20 latest named tests are the current suite count, not40 tests. Full SQL rows, per-test before/after records, worker exit logs, fixture inputs, target proofs, PostgreSQL logs and new fictional pg_dump are retained in evidence. New dump TOC verified; no claim of a new dump restore test. Completed Render backup/restore was NOT repeated.

## Reproduce / preserve

Task-specific setup and shutdown/restart launchers are included verbatim in the evidence archive. They use only the new task-local cluster, never change hosted connections, and stop it in finally. This runtime needs server and clients under the same parent execution network namespace. On a working local PostgreSQL target, create the marker/config from the documented verified disposable setup, initialize a NEW fictional database once with `LocalJournal.initialize`, then run:

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:/absolute/task-only/python-packages AQ_LOCAL_PG_CONFIG=/absolute/local-target.json AQ_DURABLE_EVIDENCE=/absolute/new-results python3 tests/test_durable_fixture_payments.py`

`python3 scripts/audit_durable_fixture_payments.py /absolute/local-target.json /absolute/new-audit`

The existing source fixtures and `scripts/fixture_payment_worker.py` are in the full source bundle. Setup/restart helpers, new QA database dump, snapshots and logs are in the separate evidence ZIP. Never aim this module at hosted or customer data. New data directories/database and old evidence are retained; no destructive reset/cleanup.

## What remains before actual Stripe test-mode verification

- Separate authorization for test account/credentials/connection and event delivery; inspect actual account, prices/products, payment/tax/billing configuration. Pin actual SDK/retrieval/destination version and verify real payload schema.
- Raw-body signature/timestamp/context validation, server-owned customer/business mappings and canonical authenticated complete retrieval. Fixture markers do not satisfy these.
- Real immutable purchase/proration requests, authoritative historical period/causal reconciliation, tax/discount/credit/zero/multiple-payment handling (currently review-only), and explicit financial reversal review/attribution.
- Production-grade least-privilege roles, durable delivery acknowledgment/dispatcher/retry/backoff/monitoring, bounded retrieval timeouts and manual review/release design. CLI workers currently process explicitly named fictional tasks, not a deployed queue service. Reuse the now-tested transactional stage design rather than claiming a ready webhook endpoint.
- Real Stripe TEST events/test clocks: initial/renewal/SCA/failure then success, paid upgrade23->52, downgrade/cancel/reactivate, duplicate/delayed/out-of-order events and restarts/concurrency with independent PostgreSQL assertions. Existing actual local crash/concurrency evidence does NOT verify Stripe's real behavior.
- Keep application enforcement OFF and existing previews untouched until separately authorized. No live app wiring or paid launch approval.

Google billing case **#77793344** unresolved; no trial extension/protection confirmed, exact expiry/access/paid status unresolved. Imagery licensing remains open separately. Phone save/reopen and earlier lost geometry status unchanged; mailbox, field accuracy, billing-record retention/tax and backup-expiry questions remain open. No push, deployment, hosted-setting/credential changes, real payment, email, deletion or Render QA. Prior Render backup/restore remains complete.
