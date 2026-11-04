# Proposed 25-measurement / US$25 top-up — implementation plan

**Stages1–2 records and disposable simulations implemented but undeployed; provider/live checkout remain future work; owner purchase/history UI is now disposable-QA-only.** Sean authorized the payment-free source-lot/reconciliation stage after this plan was recorded. Source3544d880 adds legacy administrative openings, grant/debit movements and disposable simulated purchases. Read [implementation and QA evidence](QA_EXTRA_LEDGER_2026_11_04.md). No checkout, gateway connection, charge, refund or real balance change. Live recovery remains194c435b. This is not an activated payment-backed purchase system.

## Confirmed pricing and entitlement decisions — November 4

- All AeriQuote prices are **USD**.
- Pack: **25 extra measurements with estimates included for US$25**. Estimates associated with those measurements are included, not a separately priced purchase. Editing/reopening an estimate remains free under the existing safeguards.
- **Canadian customers:** add applicable tax to the USD subtotal.
- **US customers:** no tax under the current billing policy.
- Keep tax handling configurable by customer jurisdiction and effective policy; do not hard-code a permanent US exemption or a single Canadian rate.
- Each order records **currency, subtotal, tax and total**. For this pack the subtotal is USD25.00; total equals subtotal plus the applicable configured tax. Retain the order's tax jurisdiction/rule snapshot so later configuration changes do not rewrite history.
- Purchased extras **carry forward without expiry**. Monthly renewal must never erase them.
- The pricing clarification itself authorized documentation only; the subsequent stage1 request separately authorized the payment-free records layer. Checkout, payment connections and live payments remain inactive.

## Approved eligibility, spending and refund policies — November 4

- Spend monthly allowances first, then granted extras, then purchased extras in purchase order. Employee use shares the business pool; only the active owner may purchase.
- Spending purchased extras requires an active paid or complimentary subscription. Cancellation holds the purchased balance without deleting it; reactivation restores use. Purchased extras never expire.
- Refunds initially require an authorized manual review and apply only to attributable unused purchased units. No automatic refunds, negative balances, unrelated-lot deductions or money movement.
- Payment-free stage2 now implements disposable order/event and refund-decision simulations plus a database writer fence. This supersedes the earlier unapproved-policy caveats in stage1 notes. See [stage2 evidence and controlled cutover](QA_PAYMENT_FREE_EVENTS_2026_11_04.md). No hosted activation or deployment.

## Disposable owner purchase UI — implemented, undeployed

Source1972004b adds owner-only `/qa/purchases` with prominent simulation labeling, USD25/25-unit pack, configured tax/total, monthly/granted/purchased balances, active-subscription/nonexpiry explanation and business-isolated purchase history. Pending/failure/retry/success controls use the tested event ledger, never a browser success flag. One pending order per business, stable identities and locked transactions handle double clicks, refresh/replay and lost responses. No hosted activation/provider/charge. Read [screen implementation, screenshots and QA](QA_SIMULATED_PURCHASE_SCREEN_2026_11_04.md). This supersedes the earlier statement that all owner history UI remained unimplemented; live payment/receipt history integration still remains future.

## Four small implementation stages

### 1. Record entitlements before connecting payments

**Stage1 status:** opening/granted/simulated-purchase lots, deductions, independent reconciliation and immutable history are implemented but undeployed. Stage2 adds typed manual-refund simulation links and the approved spending policy, without payment movement. Simulated order/refund mutators reject hosted databases. The tested controlled cutover/rollback procedure below is mandatory before any separately authorized deployment.

Add an append-only, business-scoped allowance ledger and source lots. Distinguish legacy/admin grants, purchase fulfillment, consumption, refund revocation and reconciliation adjustments. Preserve the current measurement and estimate safeguards while honoring the confirmed pack:25 extra measurements with associated estimates included. Do not spend another purchased measurement simply to save, retry, revise or reopen its estimate. Preserve existing save/lookup operation IDs and owner-row locking.

Migrate existing extras once as opening administrative balances, with a unique migration key. Do not reclassify them as purchases or overwrite them. Monthly renewal changes the monthly period only; it must never update purchased lots. Make current counters a transactionally updated projection of the ledger and add a reconciliation test. Record the funding source on every new debit so unused purchased units can later be refunded correctly.

### 2. Prepare server-side orders in a disposable payment sandbox

Create a server-owned order with an immutable SKU, business, quantity25, currencyUSD, subtotalUSD25.00, configured tax, total and status. Bind payment attempts to that order; retries reuse the same order/processor idempotency key. A client success redirect cannot grant units. Do not accept client-supplied prices, balances or business ownership.

Use verified processor notifications, validated according to the processor's official integration guidance at implementation time. Validate merchant/account, test/live mode, final paid status and exact order amount/currency. In one transaction, lock the business/order, record the event and payment reference, fulfill the order once, grant the lot and update the bank. Never call a remote payment API while holding the allowance transaction open.

Deduplicate **both** event IDs and payment/fulfillment identities. Different event IDs for one payment must still grant only25. A repeated event ID with conflicting data is a reconciliation/security error, not a new grant. If separate retry attempts somehow both succeed, fulfill the order once and flag the second charge for reconciliation; do not silently keep two charges or mint an accidental second pack.

### 3. Handle retries, refunds and history

Persist pending/retryable states, failed attempts and reconciliation errors. A lost webhook response can be replayed without another grant; a worker crash must roll back the whole ledger/balance transaction. Periodically reconcile paid-but-unfulfilled orders using the same idempotent fulfillment routine.

Record refunds separately by unique processor refund ID. Full/partial refunds revoke only the approved, attributable, unused units and store the refunded money/tax/currency. If refund notifications arrive before payment fulfillment, retain that state and fulfill only the approved net entitlement (zero after a full refund). Process out-of-order events without resurrecting a refunded lot. Already-spent units, disputes, fees and discretionary refunds need the agreed policy/manual review; no automatic debt or subtraction from another business/monthly allowance.

Show owners purchase history: date, order/reference, units bought/remaining/revoked, currency, subtotal, tax, total, payment/refund status and receipt reference. Preserve financial audit history independently of estimate retention. Store processor references only, not card data. Keep employee purchase/refund permissions and Head Office support access explicit; do not broaden access to private business estimates.

### 4. Verify before any live activation

Disposable SQLite and PostgreSQL16/18 tests: monthly-before-purchased, month/anniversary renewal, long carry-forward, legacy opening balance, employee sharing/business isolation; duplicate same/different event IDs; lost responses and worker rollback; concurrent purchase and final-unit use; failed/retried and double-success payment attempts; wrong amount/currency/merchant/mode/signature; out-of-order refund/payment; repeated full/partial refunds; insufficient unused units; history/reconciliation consistency. Existing failed-imagery, receipt, stale-save, revision, draft and PDF assertions must remain.

Only after product decisions, sandbox evidence and required checks pass should a separate approval authorize live payment activation. No payment work is authorized by this planning document.
