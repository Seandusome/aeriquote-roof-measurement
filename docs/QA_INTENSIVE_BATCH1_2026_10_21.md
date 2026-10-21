# Intensive prelaunch bug hunt — batch 1, 2026-10-21

Branch: landscaping-multi-area-recovery-oct11 only. No main or real customer account modifications.

## Confirmed and fixed

Server accepted a saved estimate whose top-level total disagreed with pricing.total; accepted inconsistent tax component totals; accepted negative/nonfinite linear and area quantities, malformed pricing/measurement snapshots, invalid saved service area quantities/rates, and roofs flagged for remeasurement. Reject these before revision writes or allowance consumption. A regression first reproduced the mismatched-total failure against the prior code, then passed after the fix. Explicit zero-priced service remains permitted.

The four extracted-function industry engine runs were stale after recurring-price support: load the application's real estimatePeriodValue helper rather than bypassing it.

## Validation

45 workflow checks completed: 41 passed initially; four industry engine runs failed on the missing test helper. After fixing the harness, all four passed (Landscaping, Paving, Pressure Washing, Snow). Other 41 checks did not require rerunning because production source was unchanged after they passed. Includes real Flask routes with temporary SQLite/test dealer, allowance/account isolation, save integrity, rounding, measurement edges, permissions-related recovery checks, and DOM regressions. git diff --check passed. Dependencies installed in isolated QA virtualenv; no production dependency change.

## Deployment / browser

Code checkpoint pushed for the test service. Post-deployment browser smoke verification pending at this checkpoint; do not claim it passed yet. Earlier PDF and monthly quote verification remains documented separately.

## Limits and next batches

This validation checks snapshot numeric validity and total consistency, not independent polygon recomputation or a complete server price recalculation. Legacy minimal payloads remain compatible. Further coverage needed for geometry-to-quote mismatches, all six industries, interruption/repeated clicks, mobile layout, employee access and authentication/recovery. Existing known display issues: history lacks recurring suffix, blank linear helper can show fallback rate despite blocked quote, combined Landscaping helper wording, expanded imagery callout overlap. AI Trace remains removed.

## Deployment recovery

Post-checkpoint inspection found previous documentation-only commits had omitted source files from their Git trees; Render failed because requirements.txt was absent. Restore complete tested local source tree plus all retained remote checkpoint documents. Use explicit full tree entries (base-tree preservation was not reliable through this connector). Previous working deployment continued serving traffic. This correction touches recovery only.
