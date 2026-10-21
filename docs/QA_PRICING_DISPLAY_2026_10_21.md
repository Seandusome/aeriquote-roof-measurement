# Pricing display QA - October 21, 2026

Recovery branch only. Main, real dealers, credits, and Ali demo account unchanged by QA.

## Live findings
- Signed into dedicated QA owner sean@shinglextra.com (AeriQuote QA).
- Reopened QA TEST Prelaunch Commercial Oct20 DO NOT SEND: 11,560 ft2 at $0.10 + 3,991 ft2 at $0.20 + 291.7 linear ft at $0.35. Subtotal $2,056.31, 5% $102.82, 6% $123.38, total $2,282.51. Notes preserved.
- Actual Single (1 page) and Expanded (3 pages) downloaded and all pages rendered/visually inspected. Imagery, both areas, line, labels and pricing present. Existing historical ShingleXtra logo preserved.
- Real keyboard rate clearing confirms existing Create guard blocks invalid saved-area rate, but row and totals misleadingly display free service and a reduced quote total.
- Restored original second-area $0.20 rate in live UI: $2,282.51 recovered, Create enabled. No changed estimate saved.

## Local fix
Commit 7a72137: invalid saved-area rate displays Rate required; invalid quote pricing replaces money preview with correction feedback and top total with Price required. Explicit zero price remains allowed and returns the normal preview.

Validation: added rendered DOM assertions fail on old source, pass on fixed source. Comprehensive test_landscaping_controls.cjs passes with Script errors: []. Six-industry test_quote_pricing_validation.cjs passes. test_estimate_save_integrity.cjs passes. Python compilation and git diff --check pass. API pricing test could not run here because Flask is absent; no backend logic changed.

## Publication blocker
Automatic approval review rejected git push, describing repository publication as insufficiently authorized. Do not retry via another API or indirect route. Obtain explicit user authorization to publish commit 7a72137 to landscaping-multi-area-recovery-oct11, which automatically deploys only aeriquote-commercial-test. Fix is local, NOT deployed or live verified yet.

After publication approval: push exact recovery commit, monitor Render test deployment to live, reload QA account, repeat invalid rate and explicit zero checks, then restore original quote without saving synthetic edits. Remaining prelaunch gaps in RESUME_HERE_2026_10_20.md still apply.

## Approved publication and live verification completed

Sean explicitly authorized recovery-branch publication and test deployment. Shell git push lacked credentials; GitHub connector published identical tree 6b125abe8e6e9a4e1f616af218a1cd9c0753031a as d9cfaf7ec1d95230777648a0874fe1b1b6d20b3e, expected-head checked against aee9b4e. The earlier publication blocker above is resolved. Main untouched. Render deployment dep-dbchjbu7bikc7399pesg LIVE at 2026-10-21T20:00:23.541821Z. No error-level logs through 20:01:33 UTC.

Fresh reload and real keyboard checks on QA Commercial: blank second-area rate displays Rate required, top and summary withhold total, Create disabled; explicit zero enables Create and displays correct intentional free-service total; original $0.20 restored and $2,282.51 recovered.

## Changed-price save/reopen and actual PDFs

Changed QA Area 2 from $0.20 to $0.30/ft2 and line from $0.35 to $0.50/ft, keeping Area 1 at $0.10. Saved revision and reloaded. Current estimate $2,774.08; prior $2,282.51 revision retained. Reopened report shows Area 1 $1,156.00, Area 2 $1,197.30, line $145.87, subtotal $2,499.17, taxes $124.96 and $149.95. Original QA-only notes retained. The line display rounds to 291.7 feet; pricing uses underlying precision as before.

Actual reopened Single (1 page) and Expanded (3 pages) downloaded, rendered, and all pages visually inspected. Correct rates, totals, both areas, line, aerial/Street View and labels. Minor existing Expanded area-callout/area-label overlap remains; no new layout fix. First Expanded download returned an unavailable file; retry succeeded.

Current saved QA revision intentionally remains $2,774.08 for next-session verification. No messages sent, no real accounts or Ali demo settings changed. Ephemeral proof: /workspace/scratch/aq-pricing-required-live-oct21.jpg and /workspace/scratch/aq-changed-price-reopened-oct21.jpg. Next: remaining industry/new-user QA; avoid repeating these completed Commercial checks.
