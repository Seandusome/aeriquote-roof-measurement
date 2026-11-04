# Complete top-up journey — disposable QA only

Resumed checkpoint95864e93 / source1972004b. Final tested source **c033b5744f291c26c1d3bed20f1a3f149597bdcd**. No deployment or hosted data access. Recovery remains194c435b / dep-dbl5m4lbedkc73ekek60; auto-deployOFF. Main, production and customer data untouched.

## Customer wording

Purchase-screen **Granted → Bonus**; explanatory order is now monthly, bonus, then purchased. Removed “Configured applicable Canadian tax.” The jurisdiction, numeric tax and USD total remain visible. Simulation labeling and active-subscription/nonexpiry explanations remain. Internal append-only source origin `granted` is unchanged: this is wording, not reclassification or a balance migration.

No financial application defect reproduced; no allowance, payment-event, pricing, save, tax calculation, geometry or PDF implementation changed. Added focused integration coverage and fixture support only, plus the requested wording. A test correction uses the version from the acknowledged save response for guarded revisions; the estimate-list endpoint intentionally does not supply it. No validation or stale-save safeguard weakened.

## Journey design

Temporary loopback SQLite fixture, fictional Basic paid business, active subscription evidence, no complimentary/recovery bypass. Monthly25 and Bonus3 are exhausted through the real normal consumption function in each channel, not by resetting balances. This is test setup, not28 external imagery requests or28 customer jobs. The disposable-only purchase form creates one pending order and grants its25-unit pack only after simulated success.

The owner buys. A real employee login loads and traces a fictional Landscaping job containing two areas plus a line, enters rates/customer details and saves it. The owner logs in, replays the employee's accepted property/save operations, reopens the job, downloads Single and Expanded, saves one guarded customer-detail revision, repeats its acknowledgment, reopens and downloads both revised layouts. Existing history/revision integrity assertions are retained. The original saved revision remains identical.

Each logical purchased measurement has an included estimate entitlement. The two existing audit channels each go25→24 once: **one measurement used, one included estimate used**, not two purchased measurements. The customer-visible purchased measurement balance remains24. Save retries, acceptance retries, revisions, reopening and all four PDF downloads must leave it there. Independent purchased-source negative movements must be exactly one lookups row and one estimates row, each-1. Exactly one order fulfillment, one active estimate and one revision.

Failed prepared and direct property requests return503 and do not consume units. Another business cannot accept the employee's prepared property or read the estimate; its own Bonus3/purchased0 stays intact. Employees cannot buy or inspect owner purchase history; existing owner-only/CSRF/business-isolation assertions still run.

Cancellation retains24 purchased units in both channels and blocks a new property preparation403. Reactivation allows normal property preparation200. That new preparation is deliberately not accepted, preserving the final24 and avoiding a second measurement charge. It uses the same real allowance check in a rolled-back preparation savepoint. Actual post-reactivation spending is separately covered by the earlier order/event consumption suite; this journey confirms access restoration without intentionally spending another unit.

## Evidence and final results

- SQLite HTTP journey: PASS monthly/Bonus exhaustion, owner/employee receipt sharing, failed-load rollback, one purchased debit per channel, revision/replay/reopen free, cross-business404 and cancellation/reactivation.
- PostgreSQL16/18: PASS on final sourcec033b574; [exact CI excerpts](qa/topup-journey-2026-11-04/postgres-results.log)..
- Desktop real Chromium complete journey and independent WGS84/Decimal reconciliation: PASS; [12-stage balance trace](qa/topup-journey-2026-11-04/topup-stages.json) and [CI/WGS84/Decimal log](qa/topup-journey-2026-11-04/browser-results.log)..
- PDFs: Four PDFs / six rendered pages downloaded, rendered and visually inspected. Both initial and revised customer details match; two659ft² areas at0.10 plus62.04996065ft at0.10 give subtotal138.00, tax6.90+8.28, total153.18. Service quote is CAD per the fictional Canadian contractor profile; the AeriQuote software pack remains USD25+tax. [Independent proof](qa/topup-journey-2026-11-04/independent-pricing-and-render-review.json), [revised Single](qa/topup-journey-2026-11-04/topup-revised-single.pdf), [revised Expanded](qa/topup-journey-2026-11-04/topup-revised-expanded.pdf); original files and all six final PNG renders in the evidence folder..
- Exact-source required workflows: Exact final sourcec033b574: application **41924392656 SUCCESS**; recovery **41924392724 SUCCESS** including SQLite and PostgreSQL16/18; browser **41924392757 SUCCESS (12/12 jobs)** including the complete top-up journey. Every required workflow completed on the final source; no unresolved automated failure. CI tracked directly. [Workflow summaries](qa/topup-journey-2026-11-04/final-workflows.json)..

The browser journey exercises the actual trace/save/reopen/download controls and existing measurement/PDF assertions. No fabricated “passed” result from PDF mocks. The separate purchase-screen suite still tests1440/390/320 responsive widths, double submissions, pending/failure/retry/success and lost success responses with zero uncaught errors. The new complete measurement/PDF journey is desktop1440 only.

## Remaining limitations / next useful task

Payment fulfillment and subscription status changes are simulated in disposable QA; no provider, checkout, real charge/refund, tax setup or hosted balance change. Fictional provider imagery is used; no Google/Solar/Mapbox/commercial service calls. This does not establish real-world measurement accuracy or live billing integration.

Owner desktop visual review and physical-phone touch testing remain pending. Dense Single PDF readability is unchanged; this bounded job uses ordinary content rather than pagination stress. No reactivation second acceptance is charged in this journey, as explained above. The existing controlled writer cutover/rollback procedure remains required before any future separately authorized deployment.

Next: Sean reviews the saved purchase/journey evidence; any provider sandbox or recovery deployment needs a separate scoped instruction. Save checkpoint and pause. Four pre-existing untracked copies preserved.
