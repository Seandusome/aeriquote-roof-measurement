# Final pricing consistency review - November 10, 2026

Started at `adb214c00c11da34c7a7b1ca1cd0dca0f4661ede`. Corrected application commit: **`5d53cae5ae2f5b91b67155721c4f4b661d82527d`**, local `qa/customer-copy-09e795d0`. Undeployed and not pushed.

## Confirmed

| Plan | Advertised USD/month | Default monthly lookups | Default monthly new estimates |
|---|---:|---:|---:|
| Basic | 29 | 25 | 25 |
| Pro | 59 | 75 | 75 |
| Business | 99 | 200 | 200 |

Prices agree across public pricing, comparison table, homepage and upgrade selection configuration. These are configured/advertised prices, not verified live Stripe prices: Stripe is not connected.

`account_credits.SUBSCRIPTION_LIMITS` defines 25/75/200 for both monthly usage channels. `paid_usage` returns the corresponding allowance. Source review confirmed paid plans use these monthly counters for property acceptance and new property-estimate saves. Existing property saves/revisions return through the existing-estimate branch without another new-estimate allowance. Head Office overrides, complimentary access and subscription eligibility remain separate controls. No fresh boundary/exhaustion audit was attempted within this short review.

In a fresh disposable SQLite fixture, each fictional Basic/Pro/Business plan was signed in using normal authentication. Recovery-service bypass was disabled and complimentary access off. All three returned the correct default paid allowance and HTTP200 for the employee-management page. Each received the same AutoMeasure/Area/Linear UI. No live account was inspected or changed.

## Actual feature discrepancies and corrections

- **Advanced tools on Pro:** no plan-specific tool entitlement/gate was found. Area/linear, multiple measurements, roofing review/manual tools and native PDF capabilities are shared. Removed unsupported Advanced/Expanded capability exclusivity from plan cards and FAQ. Comparison now shows shared area/linear tools on all plans.
- **Team accounts on Business:** `/dealer-employees` GET and POST check owner role, not plan. Basic and Pro owners can access employee management too. Employees share the owning business allowance and cannot manage owner settings/other employees. Removed Business-only team claims; the comparison table and FAQ now explicitly describe shared employee access across plans. Did not add a gate or change account roles. This session exercised page access, not new employee creation; POST authorization was source-reviewed.
- **Business dashboard / usage reporting:** no separate Business-only customer dashboard/permission gate was found. Head Office dashboard is an administrative role feature, not a Business subscription benefit. Removed the unsupported plan benefit rather than claim it exists or add a feature.
- **Estimate allowance:** public cards/table say 25/75/200 customer estimates as well as measurements; upgrade/home cards now show the same counts. Added a plain explanation that these count new property estimates, not revisions of saved estimates.
- **Extra pack:** public planned offer agrees with disposable order/ledger constraints: 25 lookup units and 25 included estimate units, USD2500 cents plus configured tax, purchased lots have no expiry, active paid/complimentary access needed for use, retained on cancellation. Upgrade now links to the same offer terms. No conflicting pack price was found. Purchases are unavailable; real fulfillment is not wired. Simulated SK tax is not an approved live tax policy.

Only three HTML files changed. No permissions, prices, counters, measurement, pricing, PDF, payment or account code was changed.

## Verification

Actual Chromium141 at verified widths1440 and390: public pricing, account upgrade, and homepage summaries all passed price/allowance/card wording checks, branded estimates, exact roofing/manual explanation, no horizontal overflow, no JavaScript errors, and zero external/payment requests. All three upgrade selectors still work; checkout remains explicitly disabled.

Comparison-specific browser assertions confirm all three plans show area/linear tools and shared employee logins, and no Business dashboard row remains. Desktop comparison/cards and phone upgrade screenshots were visually inspected and saved in `docs/qa/pricing-consistency-2026-11-10/`, alongside results.json. Existing passing extra-offer and payment-simulation evidence was reused; real payments were not attempted. Temporary server stopped and disposable runtime removed by the supervisor.

## Policy decisions for Sean

1. **Choose the paid-plan model before charging customers:** keep tools and employee logins shared, with plans differentiated by volume (what code currently does), or separately authorize specific Pro/Business restrictions and define precisely which tools/team limits to enforce. Copy alone cannot create exclusivity. Current corrections describe existing behavior and impose no new restriction.
2. Decide whether to build a distinct Business dashboard later; it is removed from current promises.
3. Stripe must establish actual billing periods, eligibility and tax policy before real paid subscriptions/extras. Current monthly periods use the existing account-anniversary/provisional configuration until connected to billing. No changes made here.

Hosted QA stays on Google; Auto-Deploy remains OFF from the preceding direct verification. No deployment, push, merge, shared-setting changes or real-account changes. Payments inactive. Mapbox PDF visual verification remains pending at its separate checkpoint. Stop after this review.
