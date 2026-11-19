# Stripe fixture normalization/reconciliation boundary — November 19, 2026

Parent: 774ab43585d98ea5a2b4771cce70393980c6b8ed. This adds a standalone module, recorded fictional JSON, focused tests and independent SQL/JSON auditor. Existing adapter/evaluator/application files are unchanged. No module is imported by the application. No Stripe SDK/network/key/configuration, webhook route, live enforcement, UI, deletion or hosted change. Enforcement stays OFF. Separate local worktree; prior checkout/uncommitted files, databases, existing preview and backups preserved.

## Version and explicit trust boundaries

Proposed API pin: **2026-10-28.endive**, the current stable version in official Stripe documentation on November 19. Future retrieval requests AND snapshot destination must explicitly match it; SDK pin/actual payload compatibility remains to verify. This is a v1 snapshot-shaped fixture boundary, not a thin-event parser. No real Stripe payload was captured. `recorded_fictional_canonical_objects_v1` and `evt_fixture_` are offline interlocks, NOT authenticity verification.

`normalize(notification, binding, contract, canonical)` is pure. The binding is a locally trusted exact business/account/customer/subscription/item and three-price/product catalog. The contract is a separately recorded local reconciliation decision: grant purpose, invoice, purchased period, original anchor, causal predecessor, effective payment time, expected lines and settled amount. It is NEVER accepted from webhook metadata or a browser. Canonical records are separately supplied simulated retrieval results. The function does not retrieve, authenticate, create that contract, establish ownership or establish causal order. A malicious caller controlling these trusted inputs can fabricate fiction; this is intentionally not a deployable payment boundary.

Only notification object ID/type, test mode, version and supplied account context are hints. Its amount, status, metadata and customer claims grant nothing. Event.created is ignored for ordering. Ordinary own-account Event.account can be absent; independent retrieval account context must match the local binding. Supplied foreign account rejected. Wrong invoice/customer/subscription/item/price/product/currency/service period/anchor/billing reason fails closed to review. Missing fields, malformed shapes, incomplete pagination, multi-item subscriptions, duplicate lines and ambiguous catalog fail closed.

Canonical successful path requires invoice.status paid, exact nonzero settled amount, remaining zero, one complete InvoicePayment allocation with paid status, linked successful PaymentIntent with matching customer/USD/amount_received, active subscription/no pending update, and matching captured unrefunded/undisputed charge. invoice.paid alone is insufficient (can mean out-of-band paid). No browser redirect or subscription update proves payment.

Pending/failed/incomplete payment records produce observation-only events when internally consistent, never a grant/reset. Conflicting settlement statuses go to review. Refund/dispute/reversal notifications always review here, including full reversals: monetary-to-unit attribution must be reconciled before using the existing adapter's explicit attributable reversal operation. No guessing or deduction of previously saved work.

## Financial scope, deliberately conservative

USD integer cents, quantity-one licensed monthly prices Basic2900 / Pro5900 / Business9900. Exact catalog has all three distinct price IDs and products. Full-period initial/renewal invoices match full plan price and exact service line period. Subscription item current_period_start/end (not removed subscription-level period fields) and original billing_cycle_anchor must match independently recorded contract.

Upgrade requires subscription_update reason, exact existing period/anchor, old/new price pair, one negative credit and one positive debit with identical effective-to-period-end proration windows, exact pre-recorded quote lines and positive net total. Does NOT invent Stripe rounding, billing mode or proration formula. Recorded half-period example is independently checked: -1450 +2950 =1500 cents; allowance add50; Basic23 used ->52 remaining; extras7/11 and period/renewal unchanged. Usage comes from the existing offline adapter's fictional usage ledger, not Stripe. The local quote ID is NOT a Stripe Quote object.

Nonzero taxes, discounts, account credits/balances, credit notes, shipping, overpayment, alternate collection, third-party on_behalf_of, multiple payments, partial allocations and zero invoices intentionally require review. This does not decide how real taxes/discounts should work; customer-facing approved tax wording remains unchanged. Real test integration must extend and verify these cases, not relax checks blindly.

## Delivery and history

Stable semantic operation invoice:<invoice-id>:<purpose>; immutable receipt event.id. Validated canonical/binding/contract digest is included in the normalized event, so a changed valid quote under another receipt cannot silently become the same financial operation. Same receipt with changed notification is review; different receipts with identical canonical facts deduplicate in the existing adapter. Missing predecessor queues pending. Stale/conflicting branches held for review. Distinct future reconciliation decisions must not be fabricated from event.created or notification arrival order.

FixtureReplay is an IN-MEMORY raw-receipt ledger plus the existing durable marked-fictional SQLite ReplayStore. `normalized` means parsed, NOT necessarily applied; receipt statuses in SQLite are authoritative for this experiment. Boundary audit records original notification, local contract, result and independent before/after projection; inputs.json records full supplied canonical records. Boundary memory is not a restart-safe inbox. Real authenticated inbox/reconciler transactions, crash/restart coordination and PostgreSQL worker concurrency are still unimplemented. The adapter's own prior transaction tests remain historical, not repeated here.

Out-of-order tests use explicitly recorded fictional subscription state for each reconciled operation. They do not show a live current Stripe subscription can retrieve an old snapshot. A late old invoice against a newer current subscription period is explicitly held for history reconciliation. Future integration needs authenticated retained historical facts / invoice service periods plus current retrieval and serialized local history; missing history stays unknown. Six paid-delivery permutations tested through adapter, with fictional usage already pending; fixed final75 monthly remaining, old23 usage archived, extras preserved, four applied operations once.

## Newly tested on this branch

17 named tests; 23 fictional SQLite journals independently audited; 160 recorded boundary decisions (55 normalized,105 review). Initial-run test-helper root-return bug corrected; logs retained. Canonical validation includes73 invalid single-field cases and10 invalid upgrade cases; exact counts come from recorded JSON. Missing objects, malformed shapes, altered receipt/financial facts, stale snapshots, old/new receipts, success after pending, and refunds/unknown/redirect events covered. Final checks network-disabled. Independent auditor imports neither normalizer, adapter nor evaluator; reads raw SQL and JSON, asserts denial before/after equality, no duplicate applied operations, exact remaining52/75/72, original usage/extras/work sentinel and half-period financial constants. No app, browser, phone, PostgreSQL, real Google, PDF or prior complete adapter suite repeated.

Run focused evidence into a NEW directory:

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. AQ_BOUNDARY_EVIDENCE=/absolute/new-dir python3 tests/test_stripe_fixture_boundary.py`

`python3 scripts/audit_stripe_fixture_boundary.py /absolute/new-dir tests/fixtures/stripe_boundary_fictional.json`

## Exact requirements before a real Stripe TEST-mode trial

1. Separately authorize test-only Stripe credentials/connection and event delivery setup; inspect actual test account/account ID, existing prices/products and tax/billing configuration without exposing secrets. Nothing in this round changes them.
2. Pin SDK/API/destination version to2026-10-28.endive and validate actual captured schema against these proposed field paths; implement bounded authenticated canonical retrieval and all pagination. Preserve separate test/live accounts; reject live mode.
3. Verify raw-body signatures, endpoint secret, timestamp/replay tolerance and authenticated account context. Durable raw receipt inbox + serialized per-business reconciliation, transactional idempotency/financial fact conflicts/restart semantics required. Do not acknowledge durability before storage succeeds.
4. Establish unique server-owned business/customer/subscription/item/price bindings and immutable purchase/upgrade requests, quoted amounts, period/anchor and authoritative causal history. Do not trust metadata, event.created, browser redirect or arbitrary local previous_operation supplied by a client.
5. Retrieve invoice+all lines+all InvoicePayments, linked PaymentIntents/charges/refunds/disputes/credit notes, customer/subscription+all items/current pending update, prices/products; reconcile paid totals, USD, actual tax/discount/balance/payment allocation and historical service periods. Current subscription state alone cannot establish old invoice history. Fail closed on missing/conflicting facts.
6. Verify actual pending_if_incomplete/payment behavior and proration preview/billing-mode/rounding rules, successful upgrade settlement, pending/failed preservation, downgrade renewal, cancellation paid-through and successful reactivation with real test events. Test amounts including tax, credit, zero invoices and multiple payments before accepting them. Existing unsupported cases remain review-only.
7. Real test-mode scenarios: initial/renewal with test clock/month-end, SCA/pending/failure then success, paid upgrade23->52, downgrade, cancel/reactivate, duplicates/replays/delayed/contradictory callbacks, lost response/restart, concurrent workers, partial/full refund/dispute review and attribution. Independently verify PostgreSQL receipts/history/balances. None verified by fictional fixtures.
8. Keep application enforcement OFF and no live wiring until separately approved. Test trial is not paid launch. Licensing, mailbox, tax and required-record/backup-expiry questions remain open; no deletion integration.

## Official sources consulted (November19,2026)

- https://docs.stripe.com/api/versioning — stable2026-10-28.endive; explicit request/destination version.
- https://docs.stripe.com/webhooks — signature/raw body, duplicate deliveries and no guaranteed order; retrieve canonical resources. No webhook implemented.
- https://docs.stripe.com/api/events/retrieve — event catalog: invoice.paid includes out-of-band; invoice.payment_succeeded successful attempt.
- https://docs.stripe.com/api/invoices/object — integer amounts, payments list, parent, credit/balance fields. Invoice period_start/end are not substituted for service line periods.
- https://docs.stripe.com/api/invoice-payment/retrieve and https://docs.stripe.com/api/invoice-payment — exact InvoicePayment -> invoice/PaymentIntent allocation fields; pinned response example.
- https://docs.stripe.com/api/payment_intents/object — status/customer/currency/amount_received/latest_charge.
- https://docs.stripe.com/api/invoice-line-item/object — exact pricing/parent/service period/proration fields.
- https://docs.stripe.com/billing/subscriptions/prorations — negative/positive proration behavior; preview/confirm amounts; not automatic refund/collection.
- https://docs.stripe.com/changelog/basil/2025-03-31/deprecate-subscription-current-period-start-and-end — item-level billing periods.
- https://docs.stripe.com/billing/subscriptions/pending-updates — payment-gated updates constraints, must validate chosen configuration in test mode.

Open operational carry-forward: Google billing case77793344 unresolved; no confirmed extension, exact trial deadline/billing access/paid status still unresolved. Imagery licensing open and separate from Google billing. Render batch4 backup/restore complete; do not repeat/upgrade. Phone save/reopen pending; lost geometry unrecovered. Existing historical results remain source-specific. No push/deployment, app/hosted settings, credentials, payments, real email or deletion changes.
