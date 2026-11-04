# Proposed 25-measurement / $25 top-up — implementation plan

**Planning only. Currency is unconfirmed.** No checkout, gateway connection, charge, refund, live balance change or new entitlement was implemented. Existing app source remains1cd73b65. The current bank contains administrative extra measurements/estimates; it is not a payment-backed purchase system.

## Decisions needed before implementation

1. Currency and whether the displayed $25 includes any applicable tax. Keep the offer inactive until approved; record an immutable amount/currency/tax breakdown on each order.
2. Does a pack include25 new-estimate allowances as well as25 measurements? **Recommend yes**, matching existing administrative extras. Editing/reopening an estimate remains free. The pack is not two separately billed deductions for one measurement-and-estimate workflow.
3. Purchase eligibility after trial expiry/cancellation, and who may buy. Recommend business owners only initially; employees continue sharing the business pool. Purchased balances never expire or disappear on cancellation/disable; separately define when an active account may spend them.
4. Refund terms, partial refunds and already-used units. Recommend refunds only against attributable unused units initially, with manual review for used units/disputes. Never silently make a monthly or extra balance negative, erase prior work or revoke an unrelated grant.
5. Priority between existing administrative extras and purchased extras. Recommend monthly first, then existing free/admin extras, then purchased lots in purchase order. All extra balances carry forward; only monthly availability renews.

## Four small implementation stages

### 1. Record entitlements before connecting payments

Add an append-only, business-scoped allowance ledger and source lots. Distinguish legacy/admin grants, purchase fulfillment, consumption, refund revocation and reconciliation adjustments. Track measurement and estimate channels explicitly until the pack decision above is confirmed. Preserve existing save/lookup operation IDs and owner-row locking.

Migrate existing extras once as opening administrative balances, with a unique migration key. Do not reclassify them as purchases or overwrite them. Monthly renewal changes the monthly period only; it must never update purchased lots. Make current counters a transactionally updated projection of the ledger and add a reconciliation test. Record the funding source on every new debit so unused purchased units can later be refunded correctly.

### 2. Prepare server-side orders in a disposable payment sandbox

Create a server-owned order with an immutable SKU, business, quantity25, confirmed currency/amount and status. Bind payment attempts to that order; retries reuse the same order/processor idempotency key. A client success redirect cannot grant units. Do not accept client-supplied prices, balances or business ownership.

Use verified processor notifications, validated according to the processor's official integration guidance at implementation time. Validate merchant/account, test/live mode, final paid status and exact order amount/currency. In one transaction, lock the business/order, record the event and payment reference, fulfill the order once, grant the lot and update the bank. Never call a remote payment API while holding the allowance transaction open.

Deduplicate **both** event IDs and payment/fulfillment identities. Different event IDs for one payment must still grant only25. A repeated event ID with conflicting data is a reconciliation/security error, not a new grant. If separate retry attempts somehow both succeed, fulfill the order once and flag the second charge for reconciliation; do not silently keep two charges or mint an accidental second pack.

### 3. Handle retries, refunds and history

Persist pending/retryable states, failed attempts and reconciliation errors. A lost webhook response can be replayed without another grant; a worker crash must roll back the whole ledger/balance transaction. Periodically reconcile paid-but-unfulfilled orders using the same idempotent fulfillment routine.

Record refunds separately by unique processor refund ID. Full/partial refunds revoke only the approved, attributable, unused units and store the refunded money/tax/currency. If refund notifications arrive before payment fulfillment, retain that state and fulfill only the approved net entitlement (zero after a full refund). Process out-of-order events without resurrecting a refunded lot. Already-spent units, disputes, fees and discretionary refunds need the agreed policy/manual review; no automatic debt or subtraction from another business/monthly allowance.

Show owners purchase history: date, order/reference, units bought/remaining/revoked, amount, currency, tax, payment/refund status and receipt reference. Preserve financial audit history independently of estimate retention. Store processor references only, not card data. Keep employee purchase/refund permissions and Head Office support access explicit; do not broaden access to private business estimates.

### 4. Verify before any live activation

Disposable SQLite and PostgreSQL16/18 tests: monthly-before-purchased, month/anniversary renewal, long carry-forward, legacy opening balance, employee sharing/business isolation; duplicate same/different event IDs; lost responses and worker rollback; concurrent purchase and final-unit use; failed/retried and double-success payment attempts; wrong amount/currency/merchant/mode/signature; out-of-order refund/payment; repeated full/partial refunds; insufficient unused units; history/reconciliation consistency. Existing failed-imagery, receipt, stale-save, revision, draft and PDF assertions must remain.

Only after product decisions, sandbox evidence and required checks pass should a separate approval authorize live payment activation. No payment work is authorized by this planning document.
