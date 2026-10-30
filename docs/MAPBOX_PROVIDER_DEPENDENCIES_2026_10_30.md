# AeriQuote — provider dependency inventory, October 30, 2026
Read-only inspection of recovery HEAD 22360c196a72deed73440de913e83b96775be69e. Source app.py blob e35719018a15c456d87de84e5004915790f9065b. Line numbers below refer to this exact file, not a later tip. Deployment entrypoint is app:app (render.yaml); archived app (19).py/app (21).py are not treated as live entrypoints.

## Runtime path inventory
| Function / route, app.py location | Current dependency / behavior | Future migration scope, not implemented |
|---|---|---|
| home L4066; key env L40–42 | Google key injected into client; Mapbox token server env | Remove mandatory Google aerial-key assumption only in approved adapter paths; protect server credentials |
| google_geocode_first L4142; /address-preview L4179 | Google Geocoding JSON, normalized addresses and expected-region/street checks | Separate address provider decision; preserve matching/confirmation and dropped-pin validation |
| /mapbox-test L4067; client L1969 | Mapbox Geocodingv6 forward, Canada filter, ambiguity warning | Existing geocoding call is not imagery permission; retain or separately audit US applicability, storage and pooled billing |
| performLoadProperty L1940; /property L4293; perform_property_lookup L4364 | prepare_only idempotent lookup, Google geocode unless exact pin; Street View metadata; routes five surfaces/manual-QA roofing to static imagery | Preserve staging and identity-bound receipts; replace image sourcing only after required pixels decode |
| preparePropertyImagery L1900; installPropertyImagery L1928 | Offscreen Leaflet staging; old workspace retained until imagery succeeds, current inputs still match and /property/accept succeeds | Provider readiness must be explicit; partial raster tiles or placeholder images must not falsely acknowledge coverage |
| /property/accept L4343 | Locked business-scoped acceptance; exactly-once lookup deduction | Keep behavior and monthly allowances unchanged; no provider retry charging shortcut |
| loadStandardWideAerial L921 | Nine /wide-aerial calls at z18; continuous3×3 mosaic,640logical px each, blob overlays | Smallest initial adapter can preserve raster-overlay footprint; optional native XYZ backend needs atomic readiness contract |
| refreshAerialDetail L909; schedule L920 | moveend debounce300ms, /wide-aerial highzoom refresh; sequence/token/base-layer stale-response guards | Retain cancellation, remove redundant late responses, request budgets; do not alter measurements |
| loadSingleWideAerial L963 | One /wide-aerial Google static overlay | Replace through same adapter, not ad hoc fallback |
| staticMapBounds L987 | WebMercator world256×2^zoom; logical640px dimensions | Replace implicit camera assumptions with explicit bounds/logical+physical dimensions; retina is not new geography |
| loadFallbackAerial L988; /fallback-meta L4946; /fallback-map L4952 | Google Static Maps; server byte cache; direct browser Google fallback nearL1006 | Adapter must cover both server and client branches; no silent Google escape path in proposed Mapbox mode |
| loadExactPinAerial L1872; /exact-pin-meta L4900; /exact-pin-map L4906 | Google static fixed coordinate centre/zoom; direct browser fallback L1887 | Preserve confirmed latitude/longitude and exact footprint; no silently reversed pair or nearest-building substitution |
| /wide-aerial L4927 | Google Static640×640 scale2,zoom15–20; no persistent wide-cache in route | Licensed static backend or mapped tiles; preserve resolution, quotas and business ownership |
| Area L1193–1408; Linear L1409–1450 | Leaflet geographic coordinates; local area/length plus saved independent areas; native touch/map-pan locking | Keep engine, valid-point order, edits/Cancel, quantities, rates and five surface industries |
| Manual Roofing L1443–1769 | Manual roof planes, confirmed pitch, local projected area, overlap/completeness safeguards | Keep planes/pitches; image provider gives no verified roof pitch or architectural features |
| manual_roof_qa_enabled L4057 | Double opt-in env + explicit QA business IDs | Preserve gate; not globally enabled or renamed |
| building L3278 | Solar Building Insights roof segments/geometry/pitch | Preserve AutoMeasure code but do not call it as Mapbox imagery replacement |
| perform_property_lookup L4394+ | Automatic roof path; Solar layers; manual_solar/manual_static fallback if building missing | Separate licensed launch decision; no Solar calls in proposed Mapbox manual path |
| /structure L4419 | Solar BuildingInsights for added building; lazy mask reference | Retained automatic feature only; garage/manual additions must not accidentally enter it |
| /structure-mask L4434 | Solar Data Layers mask download/cache | Keep unreachable in manual-only adapter mode; assert zero upstream Solar calls |
| /locate-building L4459 | Retry building, Solar layers, Street View metadata | Must not be a hidden provider-failure fallback in Mapbox mode |
| /rgb L4978 | Solar RGB/cache; legacy surface_static fallback may fetch BuildingInsights and Data Layers, mutate imagery centre; retry Data Layers at lower pixel density | Critical hidden dependency. Proposed adapter must fail closed rather than invoke this fallback. No current behavior changed |
| /mask L5021 | Solar mask/cache, manual-session rejection | Preserve manual guard and historical data; no new substitute mask inferred |
| loadCustomerWideAerial L2250 | Select saved-geometry extent, /wide-aerial one image, same computedMercator bounds | Preserve exact saved geometry and fit; do not create imagery-derived replacement quantities |
| buildInteractiveCustomerMap L2301 | Leaflet customer map, attributionControl:false; wide image with potential /rgb fallback; saved areas/linear overlays/labels | Explicit provider provenance/attribution required; canvas+CORS decode and complete-image checks |
| buildManualCustomerSnapshot L2225; /manual-report-map L4472 | Google Static path commands bake saved manual outlines into640×420 scale2 image; X-AeriQuote-Map-View feeds local labels | Adapter must reproduce background+saved overlays in one verified camera. Keep layout, dimensions and saved pitch areas |
| buildExactPinCustomerSnapshot L2167; /exact-pin-report-map L4567 | Google fixed centre image and outlines | Keep stable exact-pin footprint/trace alignment |
| buildSavedHistoricalSnapshot L2417; /saved-estimate-report-map L4526 | Rebuild all saved polygons/lines on freshly requested Google static image, return view header; canvas dataset.mapView/labelBoxes | Critical all-industry saved/PDF path. Preserve geometry/pricing; imagery provenance and historical capture rights need explicit plan |
| resumeSavedEstimateWorkspace L2595; /api/estimates/id/editing-session L4881 | Authorized saved bounds, no re-geocoding; Google key prerequisite, reconstructed session and nine-image load | Saved-estimate editing must work with provider-independent metadata, no remeasurement or allowance deduction |
| performEstimateHistorySave L2490; /api/estimates L4688 | Frozen quote+pricing, idempotency/account binding/version guards; stores Street View data URL, not a frozen aerial photograph | Keep existing data immutable; any future provider provenance schema/migration needs separate approval |
| street_view_info L4195; /street L5034 | Google Street View metadata/image, date and byte cache; current saved Street View data reused | Mapbox Satellite does not replace Street View. Separate legal/display/storage/redistribution decision |
| buildExpandedEstimatePDF L2888 | html2canvas approved map pixels; fit proportions, saved-view label projection; original Street View proportions | Keep design/pricing; change source image contract only; wait for decoded non-tainted pixels |
| captureSinglePageEstimate L2944; downloadEstimatePDF L3006 | html2canvas/jsPDF, freezes map pixels, SVG/canvas overlays, historical-money and incomplete-roof export guards | Preserve safeguards and approved aspect fixes; verify no double outlines, blur, attribution loss or missing tile export |
| QA vector L2976 and qa_vector_pdf.js | Image-free saved geometry, QA-only | Unchanged; does not legalize input tracing or substitute a launch licence |

## Persistence and provider-specific assumptions
- property_sessions.py: FIELDS persists Google RGB/mask/Street URLs and camera/mode metadata; strips query key, caches remain memory-only. Recovery injects current Google key and repopulates empty image caches. TTL3600 seconds and dealer_id isolation. This module needs provider-aware credentials/metadata for a future adapter; do not store tokens in payloads.
- saved_estimate_edit.py: collects frozen polygon/line coordinates for bounds; provider-independent. Keep.
- measurement_integrity.py and pricing_integrity.py: server geometry/pricing validation independent of imagery transport. Keep.
- account_credits.py:25/75/200 provisional anniversary periods; complimentary200 Edmonton-calendar-month; shared business usage and audited grants. Keep.
- The saved quote has industry/points/planes/structures/pitches/rates/pricing. Current aerial reopening regenerates photographs; it does not guarantee original imagery date. Street imagery is a distinct stored artifact. Historical Google rights are not converted by using Mapbox later.
- Internal measureSource values such as google/auto/hybrid and session modes are historical semantics. Do not globally rename them during provider replacement.
- Existing imagery caches, URLs, direct fallbacks, render attribution, source keys and projection assumptions must all be inventoried before enabling any new provider. This document inventories live entrypoint code; fixture/test/archive copies are not production integrations.

## Industry routing matrix
| Workflow | Initial imagery | Measurements | Report/history/PDF |
|---|---|---|---|
|Snow,Pressure,Paving,Landscaping,Commercial|surface_static → wide static mosaic, exact-pin/fallback as needed|Independent service polygons + saved linear|Live customer static/Leaflet; saved-report rebuild; shared Single/Expanded|
|Roofing QA manual|manual_roof_static; static only; double-gated|Roof planes + confirmed pitch + garage sections|Manual/exact-pin baked image; historical saved geometry; shared PDFs|
|Roofing automatic retained|Solar Insights +Data Layers/masks; static display fallback paths|Automatic geometry/review guards, manual additions|Solar or static customer paths; historical/export guards|
All six preserve customer/company profiles, taxes, currency labels, seasonal pricing and security. No provider result may silently replace the contractor's property, saved coordinates or priced quantities.
