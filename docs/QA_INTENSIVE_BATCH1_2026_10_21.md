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

## Verified live result

Commit c5367155cd775a7ed6165b1275fa9d1e56c7fd23 deployed LIVE on test service, deployment dep-dbcif27avr4c73c75sog, 2026-10-21T20:59:29Z. Fetched GitHub tree and confirmed app.py, scripts and requirements.txt identical to tested local commit; checkpoint documents retained.

Actual browser, QA account AeriQuote QA (sean@shinglextra.com): reopened existing 2301 Avenue C North Landscaping job, edited Price covers from month to season, created estimate, reloaded page and reopened saved current history. New revision persisted at20:59:59. Area16,372ft² @0.10 =1,637.20; line463.2ft displayed @0.70 =324.27 (unrounded underlying length); subtotal1,961.47; taxes5%=98.07 and6%=117.69; total CAD2,177.23 per season. Prior monthly version retained. Downloaded actual Single page PDF after reopening, rendered with pdftoppm, visually verified aerial/outlined area/line, street imagery, both measurement rows, all prices/taxes, seasonal total. PDF is rasterized so pdftotext yields no text; verification was visual. Screenshot captured. Malformed API tests performed locally only; no malformed live requests, no real customer or Ali demo account changes.

Remaining browser testing and geometry recalculation coverage listed above are NOT claimed passed. Batch complete; continue next batch from this checkpoint without repeating completed tests.
