# Complex-roof correction — October 15, 2026

Recovery branch only: landscaping-multi-area-recovery-oct11. Parent 74db268.

## Report and diagnosis
Sean confirmed all 12 buildings at 455 Pinehouse Dr, Saskatoon were intended. Supplied preview/photos/PDF show excessive pitch/edge labels and crossing leaders. Added structures incorrectly reused the initial building's raster mask. The reported 22,623 ft² adds up across the listed buildings but has not been independently verified; no raw live-job geometry was available.

## Changes
- Each accepted additional building requests its own Solar Data Layers mask at that building's coordinates. Main imagery/mask and wide aerial remain unchanged. This adds a Google Data Layers request for each distinct added roof; repeat reads cache the mask. Duplicate building IDs are checked before that imagery call.
- Persist Google's building resource ID and building bounding box. Keep coordinate duplicate checks for older records.
- Do not save an added roof if its outline cannot be obtained or the connected mask extends more than 2 metres beyond Google's building bounds. Explain that it was not added and offer retry/manual measurement. This guard can require manual work for unusual connected roofs; it does not certify Google area accuracy.
- Prevent overlapping Add Roof requests from repeated clicks.
- More than three automatic roofs use one anchored numbered area tag per building in measuring, preview and saved reports, with matching numbers in the property summary. Detailed pitch data remains in the summary; small jobs retain edge/pitch labels. PDF uses the existing pixel-aligned overlay capture and suppresses leaders for these tags.
- No database migrations, account/support changes, rate/tax calculations, AI Trace, main/production changes or old-estimate geometry rewrites.

## Validation
Isolated route regression covers stable ID/area, lazy own-building mask, cached retrieval, ownership, original imagery preservation and API failure. Actual DOM/Leaflet regressions cover 12-roof label counts across measuring/preview/saved export, out-of-building rejection, duplicate IDs, unavailable own mask and successful own mask. Existing controls cover PDF capture, imagery panning/detail, saved historical reports, all industry modes and pricing. Engine checks pass for landscaping, paving, snow and pressure; rendering/JavaScript parse and public route checks pass.

## Live test still required
Deploy this recovery branch to the commercial test service. Refresh the measurement app and start a fresh Pinehouse job: saved old outlines do not repair themselves. Add the roofs in the same order, check each outline and total, then preview and PDF. Compare the two larger returned buildings (previously 3,603 and 3,387 ft²) with intended roof coverage. Do not send that estimate to a customer until areas are verified. Tests use synthetic/mocked data; no paid API calls or live measurement were made here.

Backup status carried forward: paid PostgreSQL PITR is available for three days; export download and isolated restore remain unverified. Nancy is the eventual production support recipient; no production email settings changed.

## Follow-up: pin with no visible result
Sean reported the next added roof left a pin without a visible result. The map click starts measurement, but progress/errors were written only to the status above the map, while the popup kept its original measuring text. Progress, rejection and timeout now appear in the pin popup and adjacent guide. Building requests time out after 45 seconds and mask retrieval after 60 seconds; Add Roof cannot replace an in-flight pin. Tests cover visible mask failure/timeout and pending-click protection. The exact live Google/Render failure remains unconfirmed; do not claim the feedback correction independently verifies Pinehouse measurements.

## Diagnostic follow-up
Live next-roof test returned the combined unavailable/unsafe-outline message. This does not distinguish mask retrieval from contour extraction or building-bounds rejection. Split these paths into visible AQ-MASK codes: session/reference, Data Layers, TIFF download including HTTP status where available, parsing, pixels/projection, contour and bounds. Strict errors apply only to newly added roofs; main-roof fallback behavior stays unchanged. No live root cause or corrected area is claimed. Extra tests exercise the real mask loader with HTTP/parser failures and a synthetic raster.

## Full-width measurement workspace
Sean's desktop photo showed unused margins around the app. Removed only the measurement template's 1,560px wrapper cap; retain 12px outer padding, existing map/pricing column proportions, map height and mobile stacking. This applies to all measurement industries and gives most extra width to the aerial. Customer preview/PDF widths and saved geometry are unchanged. The mask diagnostic test remains outstanding and is unrelated to this CSS adjustment.
