# Payment-free extra allowance source records — November 4, 2026

Resumed **27c8d2a4**. Final application/test source **3544d880342ab0143f37a9a8bac75820dd62dc4c**. **Undeployed.** Live recovery stays **194c435b / dep-dbl5m4lbedkc73ekek60**, auto-deployOFF. Main, production, customer data, real balances and database connections untouched. No checkout, payment-provider integration, charges or refunds.

## Implemented

New `extra_allowance_ledger.py` adds business-scoped source lots, append-only movements, one-time opening markers, simulated orders and nullable policy records. Head Office administrative grants and extra deductions now update their ledger records and the existing balance projection in the **same caller-owned transaction**. Monthly counters/limits and receipt/stale-save logic are unchanged.

- Existing remaining balances are captured lazily, under the owner lock, as one **granted administrative opening lot**. This records the opening amounts without changing counters, duplicating units, rewriting old grant audits or inventing purchases/past deductions. Unequal measurement/estimate balances remain unequal. Repeated/concurrent initialization does nothing after the first record.
- New administrative grants have unique business/source references. The existing Head Office audit and permission/CSRF safeguards remain. Duplicate references grant once; changed quantities for the same reference are rejected.
- Each extra deduction records its source lot, channel, negative unit and lookup/save operation reference. Existing lookup/save receipts, owner locks and transaction boundaries prevent retries from deducting twice. Legacy unkeyed internal use receives an explicit unkeyed reference; its historical retry semantics were not changed.
- Monthly allowances are still spent first. No extra movement is written for a monthly use. Measurement and included-estimate entitlements are tracked separately to preserve the current engine; saving/retrying/reopening an estimate does not debit another purchased measurement.
- Purchased lots have **no expiry**. The bank/lot data survive renewal and a ten-year clock advance.
- `reconciliation()` reads movement sums independently of mutable counters, reports granted/purchased remaining units, and flags negative lots, projection drift or purchased lots without a matching simulated order. Deductions fail closed on those inconsistencies; there is no automatic repair, reclassification or balance reset.
- Opening records, lots, movements and simulated orders reject UPDATE/DELETE through SQLite/PostgreSQL triggers. Policy configuration remains separate and mutable only through internal disposable-test configuration.

## Simulations and unapproved policies

`fulfill_simulated_pack()` is an internal fixture/service function, **not an HTTP endpoint**. It refuses hosted PostgreSQL/non-temporary SQLite: only a temporary SQLite database or loopback PostgreSQL database named `aeriquote_qa` is accepted. A successful simulated fulfillment creates one source lot and immutable simulated order atomically. Same business/order/details replay returns the original record; different details fail. An independent business may use the same order reference without sharing records or units.

Recorded pack: **25 extra measurements with estimates included, USD25.00 subtotal**. Every simulated order retains currency, subtotal cents, tax cents, total cents and a versioned jurisdiction/rule snapshot. Tests use an explicitly fictional Canadian tax configuration and current US-zero policy; unknown Canadian jurisdiction is blocked rather than guessed. This does not change taxes on contractors' customer estimates or configure real billing rates.

Purchase eligibility and refund policies default **NULL/unapproved**. No production purchased spending or refund behavior is enabled. Disposable tests may explicitly select `simulation_only` eligibility and a source-priority option. If granted and eligible purchased units coexist without an explicit priority, extra spending is refused rather than assuming admin-first or purchased-first. Existing grant-only business behavior remains available. No refund function was built; storing a fixture policy cannot move money or revoke units.

## Validation

New `scripts/test_extra_allowance_ledger.py` runs in SQLite and PostgreSQL16/18 CI. It covers:

| Case | Result |
|---|---|
| Legacy17 measurement/9 estimate opening, eight initializers | PASS; bank unchanged, one opening, all classified granted |
| Eight duplicate administrative grants; changed payload; rollback | PASS; one grant only, mismatch rejected, no partial records |
| Eight duplicate simulated pack fulfillments | PASS; one25-unit pack, one order/lot, estimates included |
| USD25, US zero tax, configurable Canada tax, unknown jurisdiction | PASS; immutable subtotal/tax/total/rule snapshot; unknown rule rejected |
| Monthly-before-extras; unapproved eligibility; source-priority configuration | PASS; no assumed production policy |
| Rollback, renewal and ten-year advance | PASS; no expiry, lost units or partial entries |
| Last purchased unit consumed by eight requests | PASS; exactly one success, no negative lot/bank |
| Owner/employee save and lookup retries | PASS; one debit/receipt, one saved estimate, free replay/reopen; other business isolated |
| Interrupted save after deduction | PASS; movement, bank, counter and receipt roll back; retry charges once |
| Immutable history, projection drift and orphan purchase | PASS; edits rejected, inconsistencies detected/fail closed |
| Hosted simulation guard | PASS; rejected before any write |

Existing account credits, carry-forward, subscription periods, property acceptance, normal trial and failure recovery suites rerun locally PASS. Python compile/release-file checks PASS; the new module is required in release packaging. Assertions were preserved.

Backup drill now checks source history **and** bank: restored snapshot contains7 units in each channel, while the untouched source retains the later grant and9 units. SQLite PASS. PostgreSQL16/18 restore assertions are included in final CI. The old-version probe verifies **read compatibility**, not permission to run old writers against a ledger-tracked bank.

Exact final source **3544d880**: application **41913755304 SUCCESS**, recovery **41913755397 SUCCESS** including PostgreSQL16/18 ledger and backup/restore checks, browser **41913755807 SUCCESS (10/10 jobs)**. All required workflows completed; no unresolved automated failure. CI was tracked directly. The intentionally injected interrupted-save500 in the unit log is a passed rollback test, not a CI failure.

## Isolation and operating limits

All new identities/jobs were fictional, providers mocked, databases temporary or guarded loopback CI PostgreSQL. No hosted QA account/job/balance was modified. The dedicated QA binding was verified earlier today as dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa / PostgreSQL18.6; this batch did not change it. Recovery service/deploy/auto-deploy were independently read through Render. No deployment occurred. Four original untracked recovery/asset copies were retained unchanged.

Before any future deployment, define a controlled cutover/rollback process: older application writers do not append ledger movements. After an opening is recorded, an older writer changing only the bank will cause reconciliation failure on the new version. Do not auto-rebase the ledger or erase that discrepancy. No hosted backfill was run; opening capture occurs only on the first locked grant/extra deduction when this source is eventually authorized to run.

Remaining: approve subscription eligibility, refund rules and mixed-source priority before enabling any purchased use outside disposable simulation. Live fulfillment, checkout, payment notifications, refunds, owner-facing purchase history and reconciliation UI are not implemented. Dense Single PDF readability, owner desktop review and physical-phone testing remain pending and unchanged.

Recommended next task: review those policy/cutover decisions, then test a payment-free order/event state machine with duplicate/out-of-order notifications. Do not connect a payment provider or deploy without separate authorization. Canonical checkpoint is the documentation commit containing this report; pause after saving it.
