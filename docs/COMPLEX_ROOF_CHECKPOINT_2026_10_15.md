# Complex-roof correction — October 15, 2026

**Latest policy (October 16):** See TESTER_FIXES_2026_10_16.md. Main-roof outline/coverage heuristics are advisory and preserve AutoMeasure area/outline; they must not force all ordinary roofs into manual remeasurement. Extra-roof strict checks and the per-roof pitched replacement workflow remain. Bounding-box clipping remains rejected.

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

## Confirmed bounds rejection and scoped mask tracing
Sean's live next-roof result was AQ-MASK-BOUNDS: mask loading and contour extraction succeeded, but the connected contour extended outside Google's selected building bounding box. The underlying raster is a regional rooftop/non-rooftop mask, not per-building IDs; fetching a fresh mask alone does not isolate adjoining rooftop pixels. Additional-roof tracing now restricts candidate seed/flood-fill pixels to the matched Building Insights geographic bounds before extracting the actual mask contour. Empty intersections still fail, no rectangle is substituted, the outer boundary guard remains, and Google area is unchanged. Main-roof tracing is unchanged. Synthetic regression uses an entirely connected regional raster to verify selected-building isolation and rejects an empty intersection. Live Pinehouse outline/area review remains necessary, especially attached buildings whose Building Insights coverage may differ from the intended roof scope.

## Whole-roof correction workflow (supersedes scoped mask clipping)
Sean's live photo after 5158c6b showed the second outline cutting through the condo roof. Clipping was inadequate and must not be treated as a geometric or area fix. No actual Google response for this live job has been exported, so the precise provider coverage/alignment remains unverified.

- Remove bounding-box clipping from the active extra-roof path. Keep raw mask extraction; if the component exceeds the matched building bounds, or provider ground-area coverage is below 95%, or mask footprint differs from the provider's roof footprint by over 25%, flag the result for remeasurement. These are conservative review thresholds, not an accuracy certification. Preserve provider ground areas/coverage ratio for diagnosis. Apply these review checks to an available main-roof contour too.
- A flagged roof contributes zero area, shows Needs remeasurement rather than a clipped completed outline, and blocks creating a customer estimate until corrected. Other measured buildings remain intact.
- Each Roofing property-summary row offers REMEASURE THIS ROOF. Trace the intended roof boundary and explicitly confirm the pitch. Save replaces that row's area with footprint divided by cos(pitch), preserves its building ID/order, leaves other buildings/rates/taxes untouched, and does not increment roof count. Cancel leaves the previous measurement intact. A single trace uses one confirmed pitch; different slopes may need separate roof-section traces using the existing added-roof tool. This is a manual correction, not a claim of automatic multi-pitch condo measurement.
- Dealer/customer labels say dealer traced, confirmed pitch; snapshots retain corrected geometry, measurement source, chosen pitch and previous automatic area. Preview/PDF use existing pixel-aligned rendering. Traced outlines/labels use the manual colour.
- No automatic scaling from incomplete provider statistics and no fabricated rectangular roof perimeter. Initial retrieval failures still show the diagnostic codes.

Validation: real DOM/Leaflet tests exercise partial-coverage rejection, corrected-roof area/pricing, explicit pitch confirmation, unchanged neighbouring roof and roof count, customer source/area, snapshot data, cancellation and property reset; existing imagery/PDF and all-industry regressions remain required. Backend tests verify provider coverage fields. Live Pinehouse coverage, outline and PDF review still required.

Full browser-width workspace remains enabled across industries. Paid web hosting, branded reconnect/loading UI and automatic unsaved-draft recovery are agreed pre-launch work, deliberately deferred. Saved accounts/estimates persistence and paid PostgreSQL PITR status remain as previously documented. Main/production untouched.
