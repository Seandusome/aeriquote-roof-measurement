# Tax-rounding correction — November 3, 2026

Resumed checkpoint47be65f9, applicationf8c3d20a. Fixed source **194c435b377dbcb23ad24a422c63763fcd931ed4**; app.py blob661a1f0b514e04c0a7b3b67945b7ec588ea449fe. UNDEPLOYED. Roofing next-action/pitch-confirmation usability is preserved. Live recovery remains efb2d29ba72306ef718c62f1de86070af1e33ef7; auto-deploy OFF. Main, production, customer data, database connections, allowances and imagery integrations untouched.

## Exact difference and agreed rule

The original rejected request is preserved in `qa/roofing-next-action-2026-11-03/after-phone-and-failure/390-save-requests.json`. Subtotal/tax base367.30, GST5%, additional tax6%. The old browser computed tax as binary18.3649999999999984368; multiplying by100 produced1836.4999999999998. Adding Number.EPSILON was too small to change that result, so Math.round returned18.36. The server independently uses Decimal:367.30×5/100=18.365, rounded ROUND_HALF_UP to18.37. Additional tax22.04; correct total407.71. The server correctly rejected the old407.70 request.

The browser now follows the existing server rule: exact decimal operands; round each priced line to cents; sum rounded lines; round discounts and tax base at the existing stages; round each tax half up; sum cent components. Tax-included pricing uses the same rule and the existing residual tax-base policy. There is no tolerance adjustment or policy change.

## Changes

- Added a small native BigInt decimal-arithmetic helper. Decimal strings/numbers (including scientific notation) are converted to integer coefficients/scales, with exact products, sums, percentage calculations and included-tax division before cent rounding. Return values remain the existing JSON numbers; no BigInt enters saved payloads.
- priceCalc now uses that helper for monetary stages, including exact addition of individual roof-section quantities before pricing the combined roof line. Line amount displays use the same operand-based rounding, including saved/reopened report lines. This also avoids multiplying decimals in binary before attempting to repair rounding.
- Removed the obsolete intermediate binary subtotal computation. Measurement geometry, rates, taxes, pricing modes, allowance behavior and schemas unchanged.
- Server pricing_integrity.py and its strict validation/tolerances are unchanged. Original bad payload remains rejected. Historical saved pricing is not rewritten; reopened estimates/PDFs retain their frozen saved pricing.
- Test adapters load the real helper. The browser test now waits for the actual saved-workspace restoration state (sessionToken, cleared savedEstimateEditContext and savedPropertyEditActive) before reopening again. A prior attempt raced that async restoration and saw temporary Homeowner text; no timeout increase, relaxed customer assertion or application recovery change was used.

## Regression and independent validation

- New exact367.30/5% regression fails against the unmodified old source (40770 versus expected40771 cents), then passes with the fix. Literal adjacent cases367.29/367.30/367.31, just below/at/above half-cent line/tax/extra boundaries, decimal products, scientific notation, zero and summed roof quantities pass. Existing expectations preserved.
- **1,894 actual-JS versus independent server-Decimal cases PASS**, across all six industries, regular/discount/included modes,0/5/6/7.25/12.5% rates, nearby tax bases, fractional extras and roof-section sums. Includes the exact original submitted payload with unchanged geometry/rates and expected18.37/407.71. Quantity tolerance is unchanged; monetary comparisons are exact.
- Existing **70 actual-client → Decimal → isolated real API fixtures PASS**, including all industries/modes/periods, manual pitch, rounded line items, intentional zero, and forged-price rejection without history changes. Invalid-amount/tax/discount API regression PASS.
- Existing manual-Roofing DOM safeguards, six-industry pricing guards, saved editing and surface workspace regressions PASS. No default5/12 acceptance or Save/Cancel change.
- Actual Chromium1440 and390 flows PASS: load, trace, pitch/save/confirmation, edits/Cancel, adding/deleting, save and history reopen. Preview, captured POST, stored payload, reopened report and both real PDF exporters agree. No uncaught JS errors or horizontal overflow. The previously failing phone fixture is unchanged; no expected amount, rate or geometry was altered to avoid the boundary.
- Four actual PDFs downloaded (Single1page and Expanded2pages at each width); all six final pages rendered and visually inspected. Both roof sections, pitches, fictional customer and prices retained. PDF export preserves the saved geometry/pricing/customer snapshot.
- Independent WGS84+Decimal verifier PASS for both stored browser snapshots. Desktop quantity1360.321795525055ft²×0.27 →367.29, GST18.36, additional22.04,total407.69. Phone quantity1360.3812171202785ft²×0.27 →367.30,GST18.37,additional22.04,total407.71. Small geometry differences come from browser map pixel rounding; the original phone geometry was preserved. Existing WGS840.6% tolerance is not survey-accuracy evidence.

Evidence (stage screenshots, requests, stored snapshots, four PDFs, six renders, logs and reconciliation) is in `docs/qa/tax-rounding-2026-11-03/`. All jobs/accounts/providers in these checks were fictional/disposable and loopback-only with normal Basic fixture allowances. No live QA job/account was changed. Existing untracked PDF copies preserved.

## Required workflows

All required workflows completed SUCCESS on exact source194c435b377dbcb23ad24a422c63763fcd931ed4:

| Workflow | Run | Result |
|---|---|---|
| Validate AeriQuote application |41726151088|PASS|
| Validate landscaping recovery |41726151080|PASS, including new boundary regression, PostgreSQL16/18 and backup/previous-app compatibility drill|
| Isolated browser crash/recovery |41726151121|PASS10/10 jobs, including previously failed roof-exports|

CI roof-export log confirms both desktop and phone saved/reopened successfully and exported Single+Expanded PDFs, with407.69 and407.71 totals respectively. No unresolved automated failure remains on the final source; original failed-source evidence is retained as history. New focused boundary verification is part of the required recovery workflow. No checks or assertions were removed or weakened.

## Pause / next session

The prior rounding blocker is resolved and all final-source required workflows pass. Preserve the Roofing usability improvements and the historical rejected payload as regression evidence. No deployment is authorized in this batch. Continue only on Sean's instruction; next review is the saved Roofing before/after layout. Owner manual desktop review and physical-phone testing remain pending. Isolated QA binding unchanged: dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa.
