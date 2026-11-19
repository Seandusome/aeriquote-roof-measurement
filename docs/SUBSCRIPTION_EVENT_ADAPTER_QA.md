# Offline subscription-event adapter — November 19, 2026

Starting HEAD e022ab2f25a2ce31770adfbfbaa59f59ba4adfec. Standalone `subscription_events_qa.py` feeds the existing, unchanged `standalone_policy.evaluate`. It is NOT imported by app.py, the QA enforcement guard, a server, worker or deletion job. No Stripe SDK, HTTP webhook, credentials, event destination, checkout or payment connection exists here. No app account, allowance, saved estimate or image is written. Only explicitly marked fictional local SQLite journals are written. Enforcement remains default-OFF; existing previews untouched.

## Contract and trust boundary

These are normalized FICTIONAL domain facts, NOT raw Stripe webhook bodies. The `fictional_verified_fixture` marker is an offline interlock, not payment verification. A future upstream adapter must authenticate signed notifications, map customer/subscription/price/invoice/period to the correct business, retrieve canonical payment/subscription facts and reconcile them. Browser redirects, sign-in, `active` alone, a user-supplied flag or a subscription-created event cannot establish successful paid entitlement.

Each event has schema1, immutable receipt `id`, semantic `operation_id`, business_id, kind, aware UTC `effective_at`, explicit `previous_operation` (null only at the beginning). Payment-grant events also require fictional verified successful invoice facts, active subscription, invoice ID, subscription ID and explicit purchased period/plan facts. Actual amounts/currency, invoice settlement/credits/out-of-band payments, tax and proration reconciliation must be validated upstream before any future real use. No monetary proration is calculated here. USD29/59/99 and approved delta/renewal rules remain unchanged.

`previous_operation` is a domain causal reference, NOT Stripe event.created, a Stripe sequence number or an invented provider revision. It must be established by an authoritative reconciler before a real integration. Time is used only to validate explicit period/effective facts and defer future events, never to sort provider notifications. Missing predecessor/time remains visibly pending; stale causal branches, conflicting facts and malformed events go to review without changing the projection. There is no arbitrary last-arriving-wins. Multiple queued operations competing for one predecessor are held for reconciliation; a later conflicting branch cannot overwrite the already committed branch. This is safe holding, not a claim that arbitrary inconsistent Stripe histories automatically converge.

Receipt IDs deduplicate identical deliveries; semantic operation IDs deduplicate separate receipts for the same canonical operation. Same ID with changed facts flags review. A period and invoice can grant only once. Initial, renewal, upgrade and reactivation receipts cannot reuse an already-granted invoice. A future normalizer must canonicalize snapshots/status history and derive stable operation IDs (e.g. invoice+grant purpose, upgrade+full reversal); it must not issue new grant IDs for retries. Pending/failed attempt observations use their own attempt/status operation IDs, leave the causal entitlement head and balances unchanged, and do not prevent later verified payment success. Receipt and projection commits use one SQLite BEGIN IMMEDIATE transaction. Injected interruption before commit rolls back both; a retry applies once. This is disposable SQLite evidence, not production PostgreSQL/worker-concurrency verification.

## Calculations connected

- `initial.paid`: explicit successful first period creates the fictional paid snapshot once; included limits25/75/200. Seed extras/security/presence/legacy promises are explicit, never guessed from login or account creation.
- `renewal.paid`: contiguous approved monthly period, original UTC billing anchor, correct scheduled/effective plan, distinct invoice/period. Archives old period and resets current monthly usage exactly once. Unused units do not carry; extras persist. Original month-end anchor returns after a short month. Failed/pending attempts never reset anything.
- `upgrade.paid`: same subscription/period and renewal deadline; add only the plan-cap delta via the evaluator's attributable upgrade records. Used counts, extras, geometry/customer sentinel, original period and renewal date stay intact. Basic23 used -> Pro52 monthly remaining. Basic->Pro->Business also tested.
- `downgrade.scheduled`: records next plan, no immediate cap cut; takes effect only on confirmed next successful renewal. Conflicting renewed plan/anchor is review-required.
- `cancellation.scheduled`: explicit paid-through end must match current confirmed period; next renewal canceled, existing paid access retained until exact end. Read-only begins at that instant and ends at120 elapsed days, subject to protected longer scopes. No clock-based database write or deletion occurs.
- `reactivation.paid`: explicit new confirmed period; retained work restored only where present and eligible under old120-day/longer promises. Usage/extras are carried, not reset by reactivation; only a separately confirmed renewal resets monthly usage. On this reactivated period ending, the evaluator projection uses that period's end for the next120-day calculation. A new subscription ID may be supplied only in this explicitly reconciled reactivation operation. Different plan or prior-period upgrade attribution requires reconciliation rather than discarding usage.
- `usage.recorded`: FICTIONAL consumption for replay only. Monthly before relevant extras; base before attributable upgrade lots. Immutable per-period consumption allocations make a later reversal auditable. No real measurement/save requests are processed.
- `upgrade.reversed`: requires its existing attributable upgrade and current period, confirmed full reversal and complete usage attribution. Removes only unused upgrade delta; consumed units/usage, saved work and unrelated extras persist, never negative. Repeated reversal cannot remove again. Partial financial reversals, cross-period reversals and reversed multi-upgrade chains remain explicit review-required cases until supplied reconciliation can establish allocations; approved principles are not reopened.

No event grants permission to delete or restores deleted content. Unknown legacy deadlines remain unknown/review-required. A supplied disabled security state continues to deny actionable evaluator access. This adapter is not a substitute for app business/employee/Head Office authorization.

## Proposed Stripe mapping — researched, NOT integrated or verified

Official documentation consulted November19,2026:

| Stripe notification | Proposed normalizer action |
|---|---|
| `invoice.paid` | Retrieve associated invoice/subscription and confirm canonical settled payment + active subscription, business binding and billing reason/price/period. Then normalize initial/renewal/upgrade/reactivation facts as appropriate; the event name alone is insufficient. |
| `invoice.payment_failed`, `invoice.payment_action_required` | Record failed/pending attempt; no new benefits or allowance reset. Existing paid access follows approved paid-through facts. |
| `customer.subscription.updated` | Reconcile plan-change/cancel-at-period-end schedule. An update alone does not prove payment. |
| `customer.subscription.deleted` | Reconcile actual paid-access end; do not substitute arrival time or delete retained work. |
| pending-update applied/expired, refund/dispute notifications | Reconcile to the original invoice/upgrade/period and attributable unused units. No automatic financial reversal-to-unit allocation from event name alone. |
| Checkout success redirect/session completion | Never treat browser navigation/completion alone as entitlement confirmation. |

Sources:
- https://docs.stripe.com/billing/subscriptions/webhooks : invoice.paid plus confirmed active associated subscription; subscriptions may initially be incomplete; status alone is not proof all invoices paid.
- https://docs.stripe.com/webhooks : signatures, duplicate receipts/semantic duplicates, no guaranteed event order; event.created seconds are not a safe order or dedup key.
- https://docs.stripe.com/billing/subscriptions/pending-updates : default updates can apply before successful payment; pending updates have payment-method/collection constraints and exceptions, including resumption. Future configuration must be tested; this offline adapter still gates benefits on explicit success.
- https://docs.stripe.com/billing/subscriptions/cancel : cancellation timing is configurable; AeriQuote's approved end-of-paid-period rule must be explicitly mapped rather than assuming Stripe defaults.

No Stripe account API version, configuration or actual event payload schema was inspected. Future mapping needs a pinned/tested version, settlement/amount/currency validation, signing-secret verification, authoritative retrieval/reconciliation, account bindings, durable receipt/transaction design and restart/retry tests before integration. No claim of real Stripe compatibility or payment verification.

## Fresh evidence and historical results

Run only this focused suite:
`PYTHONPATH=. AQ_EVENT_EVIDENCE=/absolute/disposable/new-directory python3 tests/test_subscription_events_qa.py`
Then independently inspect frozen journals:
`python3 scripts/audit_subscription_event_replays.py /absolute/disposable/new-directory`
Tests use network-disabled fictional accounts.31 named tests include120 complete permutations of a five-event paid/usage/upgrade/usage/reversal chain, fixed expected balances, denial/no-grant snapshots, same-receipt competing threads, transaction-failure rollback, duplicate period/invoice safeguards, exact120-day boundaries, month-end renewals, reactivation and unknown inputs. Raw read-only SQLite assertions verify history/projection/balances; independent auditor does not import adapter/evaluator.

Earlier policy/API/browser/image-free-PDF passes remain historical on their documented sources (e022ab2 for browser fix, ab395dc for the earlier API round, a43f7d1 for policy calculations). They were not rerun, and this round is not a phone/PDF/real-Google/PostgreSQL/real-payment regression suite. No application source or enforcement flag changed.

Open operational items unchanged: Google billing case77793344 open; trial date, billing access and paid status unresolved, no extension/interruption protection confirmed. Render batch4 backup/restore COMPLETE; do not repeat/upgrade. Imagery rights, mailbox delivery, required records and backup expiry remain separate open matters. Physical-phone save/reopen pending; prior lost geometry unrecovered.
