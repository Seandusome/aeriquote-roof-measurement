# Quote-pricing safeguards — October 20, 2026

Recovery branch only; synthetic local QA data. Main, real dealers, account grants and existing saved quotes unchanged. Browser live verification remains blocked by native retained credential-data protection; do not bypass it or claim live UI/PDF QA for this change.

## Defects reproduced
- Blank/negative job rate could silently fall back to dealer default through currentJobPrice; no quote-creation validation rejected it.
- Discount percentages above 100 and negative taxes could create negative totals; optional extras and commercial rate paths silently coerced invalid values to zero.
- Estimate POST accepted negative/non-finite amounts and quantities without validating them before updating history.

## Fix
- Validate active pricing inputs before creating a new report and before saving history. Visible corrective message next to Create Estimate; invalid inputs disable Create after summary update. Entry-point guards also reject direct button/function invocation.
- Require explicit finite non-negative active rates. Explicit 0 is allowed for intentional free services. Optional blank extra-services amount remains 0. Tax inputs require explicit 0–100%; discounts in Discount mode require explicit 0–100%.
- Saved area rate edits retain blank/null or negative invalid input instead of silently coercing to zero; synchronisation preserves that state until corrected.
- Reject non-finite/negative calculated amounts.
- Real Flask estimate POST validates supplied amounts, quantities, pricing totals, tax ranges and active discount before allowance consumption or estimate/revision writes. Historical reports and saved prices are not rewritten; no historical recalculation introduced. This is input validation, not certification of customer measurements or automatic tax calculation.
- Existing rounding, area/line math, quote source selection, Pinehouse safeguards, imagery, shields and paid plan behavior unchanged.

## Verification
- test_quote_pricing_validation.cjs tests all six industries, blank/negative/non-finite rates, tax/discount limits, optional extras, explicit zero, blank-area synchronisation and actual save/report rejection before network writes.
- test_estimate_pricing_api.py uses real Flask routes and isolated temp database: invalid values return 400, existing estimate and revision history unchanged, explicit free quote allowed.
- Controls DOM regression additionally tests clearing actual saved-area input, invalid state/disabled Create, explicit zero recovery and excessive discount correction.
- Existing save-integrity unit fixture now explicitly stubs valid pricing; independent pricing validation tests cover the new guard. New tests added to recovery CI.
- Compilation and whitespace check pass. Full final suite/deployment results to follow once finished.

Next live QA: use AeriQuote QA sean@shinglextra.com. On a labelled QA job clear a rate, enter a negative rate/tax, set discount 101%, and verify estimate creation is blocked with useful correction messages. Restore valid rates/taxes, save, reopen and inspect actual Single/Expanded PDFs. Never use a real dealer/customer for invalid-input tests.
