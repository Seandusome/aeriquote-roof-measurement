# Roofing safeguards QA — October 20, 2026

Recovery branch only. Main, real dealers, credit grants, complimentary settings and existing measurement safeguards unchanged. QA owner: AeriQuote QA / sean@shinglextra.com. Warranty preference remains OFF.

## Actual live checks before map-focus fix

- Fresh 455 Pinehouse Drive, Saskatoon lookup returned 1,178 ft² provider main-roof area. Scope mismatch correctly showed unverified area, review required, no quote total and disabled estimate creation.
- Added the right-hand second roof. Its automatic result was excluded and required FIX ROOF. Both roofs blocked the estimate.
- FIX ROOF for the second roof opened an empty targeted replacement with default 5/12 and disabled Save before points. Saved an illustrative four-corner synthetic trace: 5,436 ft² displayed. Two roofs retained; main remained unverified/blocked.
- EDIT ROOF reopened those four saved corners, not the original detected candidate. Cancel preserved 5,436 ft² and the main-roof blocker.
- Found a usability defect: FIX ROOF for the main house retained the previous second-roof map viewport. Target ownership was correct, but the viewport could encourage tracing the wrong roof. Map focus correction below addresses this.
- Manually navigated and saved a separate illustrative main QA polygon: 5,092 ft² displayed, assumed 5/12. Second roof remained 5,436 ft²; both corrections unlocked estimate creation.
- Saved `QA TEST Pinehouse Roof Safeguards Oct20 DO NOT SEND`, with notes explicitly identifying synthetic traces and assumed pitch, NOT a verified customer measurement. Current revision 2026-10-20 21:07:52 UTC. Total 10,528 displayed ft²; $509.24 + $543.59 = $1,052.83 subtotal; $52.64 + $63.17 tax; $1,168.64 CAD total.
- Downloaded ACTUAL Single and Expanded PDFs. Poppler rendered and visually inspected all three pages. Both QA outlines, all eight edge dimensions, two pitch/area labels, separate roof/pricing rows and total retained. Placeholder image chosen deliberately. Polygons are deliberately synthetic; do not use as customer roof measurements.
- Reloaded and reopened current saved revision through history. Both areas, pitch/source, notes and $1,168.64 persisted.
- Raw Single: /workspace/scratch/da5b930b-e7d9-4156-8484-8082f54643c7/b8621abf-f8eb-4b00-9392-aafe30c05e19. Expanded: /workspace/scratch/da5b930b-e7d9-4156-8484-8082f54643c7/4b559a22-078a-4f27-b996-bec7d2e9907e. Renders /workspace/scratch/93dfcfceb87a/pine-*.jpg.

## Map-focus correction

- Starting a targeted correction now fits the selected roof's available boundary; if no boundary is available, centres on its provider coordinates at zoom 19. Existing saved geometry and area stay unchanged.
- Stale main-roof guidance now says FIX ROOF, matching the visible button.
- Controls regression passed with a new assertion that switching from second-roof edit to main-roof Fix centres the main roof and preserves the saved second roof. All existing controls/Leaflet/PDF/safeguard assertions passed with zero script errors. Python compile and isolated complex-roof route tests passed.
- Live verification after deployment is still pending at this checkpoint. Do not call local regression a live test.

## Remaining accuracy limit

Pinehouse whole-building AutoMeasure remains unresolved. Google partial-unit scope is not a whole-building area. No thresholds relaxed, no clipping/scaling, and no accuracy certification from synthetic QA traces. The guard continues to require dealer correction before quoting.
