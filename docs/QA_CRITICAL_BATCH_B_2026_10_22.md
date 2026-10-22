# Approved critical fixes — Batch B, October 22, 2026

Starting checkpoint b734d96 (Batch A): both GitHub workflows and actual disposable PostgreSQL tests passed; Render dep-dbd5j13ncjis73ef72sg LIVE. No main/production/customer account operations.

## Monthly paid allowances

Basic/Pro/Business now have independent per-business, per-period lookup and estimate counters with plan ceilings 25/75/200. Existing stricter Head Office restrictions remain effective; a zero legacy limit cannot make a paid plan unlimited. Existing lifetime usage/history is retained. First deployment period is conservatively seeded from existing lifetime lookups and existing estimate count, because historical per-billing-period data does not exist. A fixed migration boundary avoids repeatedly seeding lifetime totals after a denied request rolls back. Later periods begin fresh without modifying prior records. Extra credits remain separate and carry forward. Revisions and idempotent retries remain free.

Owner locks serialize period initialization and deductions across employees. Editing branding/profile cannot move billing anchors/reset usage. Paid accounts enforce limits even on the named recovery service; its existing trial/legacy testing bypass and Head Office authority remain intact. Complimentary accounts still use their approved 200/month Edmonton calendar rules.

## Billing information still provisional — no Stripe connection

There are no trusted paid subscription activation dates, provider billing anchors, payment states, cancellation/proration or renewal webhook records. The implemented temporary boundary is the account-created UTC monthly anniversary, explicitly labelled account_anniversary_provisional in database/API metadata. Jan 31 clamps to the last day of February and returns to Mar 31; exact timestamp boundaries are respected. This is not a claim that signup date equals the eventual Stripe billing date. Before paid launch, trusted billing integration must set/migrate actual paid-period anchors and reconcile activation/upgrade/downgrade/cancellation/failed-payment rules; no Stripe connection or credit purchases were implemented.

## Tests

New test_subscription_periods.py uses only disposable local SQLite or guarded localhost aeriquote_qa PostgreSQL. It tests all three limits, exact boundaries, leap/short months, first-denial rollback and later renewal, separate estimate usage, old-record preservation, eight concurrent final-credit requests, business separation, profile tampering, expired sessions and paid-plan recovery-bypass rejection. Existing test_account_credits.py verifies complimentary/bonus rules, employees, free revisions, CSRF and account controls. Complete recovery suite and PostgreSQL CI are required before the next batch. Live paid-account boundary manipulation was not performed.
