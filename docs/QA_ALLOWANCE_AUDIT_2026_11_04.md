# Allowance readiness and undeployed PDF review — November 4, 2026

Resumed **caa6bb59** / application **1cd73b65e973cfd135da9f7cabbc6f4510fe68c3**. New test/CI source **2163766624a2ca0471af609ad780c39a5ceeb1de** changes no application code. Live stays **194c435b377dbcb23ad24a422c63763fcd931ed4** / **dep-dbl5m4lbedkc73ekek60**. No deployment, payment integration, charge, refund, environment change, connection change or real balance change. Auto-deploy OFF. Main, production and customer data untouched.

## Verified state and isolation

GitHub recovery HEAD initiallycaa6bb59. Local app.py blob **f51edd16cc0163dbfdb669ffd8e7e8ac5da7765f** matches that checkpoint/application. Exact-source application41732984453, recovery41732984504 and browser41732984587 independently re-read: allSUCCESS; browser10/10.

Render connector and signed-in dashboard show the same recovery service/live194c435b. Initial dashboard session had expired; Sean restored sign-in. The exact recovery instance **t99jq** then asserted parsed DATABASE_URL host **dpg-dbj4f7lg1s2s73eob8t0-a**, database **aeriquote_recovery_qa** and runtime RENDER_GIT_COMMIT194c435b before opening a connection. A **read-only transaction** returned that database/PostgreSQL18.6. No credentials printed; no business records or balances read/changed on hosted QA. Independent database metadata reports available PostgreSQL18 in Ohio. Auto-deployOFF rechecked through the connector.

All new test data: fictional identities in temporary SQLite or CI's disposable loopback **aeriquote_qa** PostgreSQL16/18. SQLite's development bypass was explicitly disabled using the existing policy-only fixture adapter; no live QA bypass or external provider/payment was used. Four pre-existing untracked recovery/asset copies were retained without modification and excluded from commits.

## PDF review — retained, undeployed

Reviewed the saved wrapping-fix report, original Expanded reproduction and final large-amount/continuation renders. The fix keeps descriptions complete and amounts whole/aligned; exact-source checks above passed. No PDF code changed today.

**Remaining readability issue:** dense Single PDFs scale the entire rasterized report down to fit one landscape Letter page. The saved stress fixture is complete but too small for comfortable paper reading. Its pricing body is approximately **4.2–4.3pt** by inference from the exporter scale, compared with about7.1pt in the ordinary fixture. These are sizing estimates, not embedded-font metadata: the PDF is a raster image. See `qa/allowance-audit-2026-11-04/pdf-readability.json`. Expanded carries this content across4 legible pages with intact descriptions, amounts and totals.

Recommendation: use Expanded for dense estimates now. A focused product/layout decision should choose a minimum readable size and whether to automatically select Expanded or present one clear recommendation before download. Do not silently remove text, shrink amounts, split monetary values or redesign the layout in this audit. Raster PDFs also lack selectable/searchable report text; a vector/text exporter is a separate future decision. Physical-phone and Sean's desktop review remain pending.

## Allowance audit results

Current implementation: `account_credits.consume`, paid subscription usage by account anniversary, complimentary usage by Edmonton calendar month, separate lookup/estimate bonus columns. Employees share their own business's allowance; another business is isolated. Owner locks serialize consumption with saved lookup/save receipts.

**Important distinction:** the existing nonexpiring bank is populated by administrative grants. Payment-backed purchase fulfillment, purchase history, refund attribution and webhook handling do not yet exist. Thus carry-forward/debit behavior is tested on that existing extra bank; actual purchased-payment lifecycle remains unimplemented, not falsely marked passed.

| Requirement / case | Evidence and result |
|---|---|
| Monthly before extras | PASS Basic25/Pro75/Business200 and complimentary200, both measurement and estimate channels; bank stays25 until base exhausted |
| Extra carry-forward / no expiry | PASS bank24 remains after renewal and a ten-year clock advance; no expiry/reset column or renewal write targets extras |
| Renewal boundaries | PASS existing anniversary/leap/short-month tests and complimentary Edmonton boundary; unused bank retained |
| Rollback / provider failure | PASS rolled-back use leaves bank unchanged; direct and prepared503 property loads consume nothing |
| Abandoned/failed imagery | PASS prepared but unaccepted imagery is free; successful acceptance is the debit boundary |
| Lost response / duplicate acceptance | PASS eight simultaneous owner/employee accepts of one operation debit one; replay/re-prepare does not debit again |
| Distinct-request concurrency | PASS last monthly+last extra permits exactly2 of8; last extra permits exactly1 of8 acceptances, remaining403 without overspend |
| Save retries / reopening | PASS eight owner/employee identical saves create one estimate and one extra-estimate debit; new-key unchanged save, revision/replay and owner/employee history reopen are free |
| Stale / invalid saves | PASS stale409 and invalid-geometry400 preserve revisions/banks/counters |
| Isolation / tampering | PASS same operation name in another business uses its own token/balance; cross-business confirmation/read denied; disabled employee denied; profile cannot mint bank or reset monthly usage |
| Normal trial | PASS existing real trial signup fixture:3 successful measurements/estimates, failed provider free, caps enforced, revision/reopen/retry remain free |
| Actual purchases / refunds | NOT IMPLEMENTED; proposed plan below, no live or sandbox payment calls |

Added `scripts/test_allowance_carryforward.py` with deterministic clocks and PostgreSQL loopback guard. Wired into recovery SQLite and both PostgreSQL jobs without weakening/removing any assertions. Existing account-credit, subscription-period, property-acceptance and normal-trial suites rerun locally PASS. New audit locallyPASS and PostgreSQL16/18PASS. No reproducible application defect found, so no application fix or policy change was made.

The existing bank has no per-debit funding ledger or purchase-lot attribution. Administrative grant auditing/duplicate browser submission already exists, but it is not a substitute for payment fulfillment/refund reconciliation. A newly initiated Load Property with a new operation intentionally consumes another measurement after successful acceptance; reopening saved/history data does not. Whether the same property should remain free across independent new lookups is a separate product policy, not evidence of an idempotency defect.

## CI and proposed next task

Final audit source21637666: application **41907790323 SUCCESS**; recovery **41907790368 SUCCESS**, including the new carry-forward/concurrency audit on SQLite and PostgreSQL16/18. Every new audit step executed and passed. App.py is unchanged from1cd73b65, whose required browser41732984587 remains10/10PASS; browser CI was not retriggered by this Python-test/workflow-only change. No unresolved CI failure.

Read [small top-up implementation plan](AERIQUOTE_TOPUP_IMPLEMENTATION_PLAN_2026_11_04.md). Pricing clarified after the audit: all AeriQuote prices USD;25 extra measurements with estimates included forUS$25; Canada adds applicable tax; US tax0 under current billing policy. Tax remains configurable and orders record currency/subtotal/tax/total. Purchased extras carry forward without expiry. Eligibility, refund policy and grant-versus-purchase spending order remain decisions before implementation. Recommended engineering next step: an isolated, payment-free source ledger/reconciliation layer that preserves existing grants and receipts, followed by duplicate/out-of-order payment-event simulations. No checkout or live payments until separately authorized.

Evidence: `docs/qa/allowance-audit-2026-11-04/`. Canonical checkpoint is the documentation commit containing this report. Keep live194c435b/auto-deployOFF and pause for Sean's next instruction.
