# Intensive prelaunch bug hunt — batch 3 (2026-10-21)

Resume point25a571ce863827b5427e80183a300c21fa4120e5. Recovery branch only: landscaping-multi-area-recovery-oct11. Main, real customer accounts and Ali demo untouched. AI Trace stays removed.

## Confirmed defects and fixes

1. Prior server accepted a forged one-dollar total when submitted subtotal/taxes/total agreed, even though measured quantities and rates implied a different price. Reproduced against the prior checkpoint validator. New pricing_integrity.py independently computes Decimal line charges, subtotal, discounts, additional services, included/added taxes and final amount from the measurement snapshot and rate inputs. Every submitted calculation field, top-level quantity/amount, extra-service description/amount, industry, pricing mode and recurring period must agree. Missing pricing inputs fail closed. Recurring periods label the computed amount; they never multiply visits/months.
2. Fractional line charges could be summed before rounding, so subtotal could differ from the sum of displayed service rows. Browser now rounds each service row, then sums those charges; independent server uses the same explicit financial policy via separate Decimal implementation. Historical saved values are not rewritten.
3. reviewAutomaticRoof skipped absent outlines entirely. A real-function regression failed before the fix. Missing outline now removes quotable automatic area and requires remeasurement; original provider area is retained across repeated review. Complete building footprint data, coverage, roof section areas/pitches and area/outline scope are checked. Server independently enforces completeness even if client warning flags are removed. Duplicate automatic building IDs, missing sections, changed pitches and underreported surface area are rejected. Historical automatic previews rerun completeness review before customer output.
4. Head Office owner-email edit could collide with an existing employee email, despite signup collision checks. Real isolated route returned302 (incorrect acceptance); now returns400 and keeps original email. No existing accounts edited outside isolated tests.

## Automated results

Final full workflow:51/51 commands passed (unique evidence file batch3-verified-results.json in scratch). Includes account permissions/isolation, quotas, password recovery, signup/onboarding, imagery/PDF DOM tests, multi-area/linear controls and saved editing. New CI checks:70 actual browser-price-calculator fixtures across six industries, three tax modes, recurring periods, extra services, discounts, legacy combined measurements, manual pitch and intentionally free service; independent Decimal comparison plus actual isolated Flask save routes reject manipulated totals and preserve record/revision state. An additional500 seeded arithmetic comparisons (seed31, random linear quantities/rates, taxes, discounts, extras) found zero browser/server mismatches.

Automatic tests cover complete main+detached garage, partial building footprint, absent outline/sections, changed section pitch/area, duplicate building ID, unflagged underreported area, and legitimate manual replacement. Integrated isolated account test exercises real signup -> owner creates employee -> case-insensitive login -> permissions -> mocked recovery email -> new password/old-session rejection -> disable/reactivate; owner access remains intact. No real password or external email changed/sent.

Initial failures: first pricing regression run43/47; three old tests expected fractional unrounded subtotals and one used incomplete synthetic automatic roof data. Updated assertions to displayed line cents and fixtures to complete roof metadata. Subsequent49/50 run identified repeated automatic review overwriting the cached original area; fixed preservation and corrected synthetic outline centres. Final51/51 passed after all production changes. git diff --check passed.

Provider semantics checked against primary Google reference: https://developers.google.com/maps/documentation/solar/reference/rest/v1/buildingInsights/findClosest (wholeRoofStats is segmented coverage, potentially less than the full building; buildingStats ground area represents the complete footprint). No automatic scaling of missing roof portions is used. Existing footprint/coverage thresholds are review safeguards, not proof of survey accuracy.

## Browser evidence so far

Existing isolated AeriQuote QA account. Real remote browser mouse, not touch or physical device. Dragged a saved line endpoint:463.2ft ->450.1ft; quote creation remained disabled. Cancel restored463.2ft and2,540.69 per-season total. A first pointer attempt hit the map rather than a handle and only panned the view; not counted as a successful point drag. Actual handle was located from rendered DOM hit bounds before the successful drag.

New-code deployment, live save/reopen and actual PDF verification pending at this checkpoint.

## Unverified / limits

No physical iPhone/Android available; touch placement, finger drag, pinch, rotation, mobile keyboard and native print/download remain unverified. Actual live employee/password-reset email flows not performed; integrated account tests use isolated Flask storage and mocked delivery. Provider outputs cannot independently establish an absent building or omitted section that is missing from all supplied geometry; Pinehouse coverage remains a manual-review case. PostgreSQL concurrency/cross-table identity races and arbitrary complex roof coverage are not proven by SQLite/fixtures. Historical incomplete records may require property reload/remeasurement; no unsafe preview/PDF is permitted merely by clearing a warning. Source measurements and rates remain authorized job inputs; server verifies their math/geometry consistency, not an externally mandated selling price.
