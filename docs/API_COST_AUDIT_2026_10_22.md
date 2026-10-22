# API cost audit and bounded optimization — October 22, 2026

Baseline GitHub checkpoint cde3390, recovery branch only. This audit and expected behavior were documented before application edits. No production/customer account access, payments, credit-policy changes or AI Trace.

## Complete active Solar call inventory

- building(): one Building Insights findClosest request. Called by perform_property_lookup for ALL six industries at baseline, by /structure for each clicked added roof (even if subsequently rejected as a duplicate), and by /locate-building for explicit automatic roof retries. Existing added-building duplicate checks defer Data Layers until an accepted distinct roof needs a mask.
- solar_layers(): Data Layers IMAGERY_LAYERS at BASE quality, 0.25 m pixels, radius bounded to100 m. Called after successful initial Building Insights; also attempted after Building Insights NOT_FOUND, by /structure-mask for a new added roof, and /locate-building after a successful automatic roof match.
- /rgb has a direct Data Layers retry with radius30 m/pixel0.5 m when the first signed RGB download fails. Existing fallback is unchanged, not a new resolution reduction.
- /rgb and /mask download URLs returned by Data Layers; these do not independently create additional Data Layers billable events for the same response.
- Five service industries ignore the automatic roof data and stage the same nine-image Static Maps mosaic. Their normal draw/edit/save/PDF workflows need no Solar data. However the customer-map renderer has an existing Solar RGB recovery path if a report Static Maps request fails; removing that recovery would be a functionality regression. Roofing Area/Linear calculations also need no Solar geometry, but the current Roofing workspace loads automatic results up front so returning to AutoMeasure works. That transition is deliberately deferred; this release leaves ALL Roofing routes/data/pitch/coverage safeguards unchanged.
- Saved-estimate editing sessions rebuild Static Maps imagery without an initial Solar lookup. They retain independently checked saved geometry.

## Other provider requests and duplication

Address preview performs Google Geocoding after650 ms of valid input; property load geocodes the same address again. Unit-address query variants can make more calls. Google mismatch guards run server-side and cannot be removed to save money. Mapbox temporary forward geocoding checks nearby same-number alternatives once per address-based successful load; dropped pins skip it. Country is currently hard-coded CA in this secondary check; not changed by cost optimization.

Working imagery uses nine640x640 Static Maps images with scale2 at zoom18. High-zoom/pan detail adds a640x640 scale2 image for each changed view (300 ms debounce); identical consecutive detail views are already suppressed. Reports fetch a separate image fitted to the complete geometry. Saved editing/reopening can request a new mosaic/report. Failed image loads/retries can repeat requests. Exact-pin/fallback, raw Solar bytes and Street View already have session caches. No new provider-content cache, TTL, resolution, map bounds, quote imagery/export path or existing cache behavior is introduced.

Safe extra cancellation: pressing Load after validated address input cancels a preview timer that has not yet fired, and invalidates late preview responses. Property lookup still validates the address independently. This avoids at most one pending Geocoding preview call per such fast click; already-running upstream requests are not assumed cancelled or unbilled.

## Verified current provider restrictions, retrieved October22

Google global terms3.2.3(b) prohibit content caching unless expressly permitted by service terms. Solar service terms20.2 permit temporary Building Insights/Data Layers storage up to30 calendar days, with a limited fixed-media exception tied to defined energy-system downstream transactions. Google Geocoding terms6.3 distinguish temporary coordinates from restricted direct end-user persistence; they do not grant blanket full-response reuse to replace chargeable requests. No new Google geocode/static/image cache is proposed. The Maps Static-specific policies URL was unavailable; current general/service-specific terms and Static Maps documentation were read instead.

Mapbox Geocoding v6 defaults to Temporary: results cannot be cached; permanent storage requires permanent=true and a credit card/enterprise agreement. No Mapbox result cache or paid storage-mode change is proposed.

Important launch review: Solar permitted uses20.1 refer to energy-system feasibility, design/install and defined downstream transactions. General roofing-treatment estimation is not expressly authorized by that wording. General Google terms also restrict creating content from map content, and map attribution/display requirements need review for Leaflet and PDFs. This audit does NOT establish that current usage, tracing, export, existing stored estimates or existing caches are licensed. Confirm applicable agreement/permissions with Google before launch. Preserve existing functionality here; do not silently disable AutoMeasure or claim a new cache compliant.

Sources:
- https://cloud.google.com/maps-platform/terms
- https://cloud.google.com/maps-platform/terms/maps-service-terms
- https://developers.google.com/maps/documentation/solar/policies
- https://developers.google.com/maps/documentation/maps-static/overview
- https://docs.mapbox.com/api/search/geocoding/
- https://developers.google.com/maps/billing-and-pricing/pricing
- https://www.mapbox.com/pricing

## Expected behavior and regression contract before implementation

The browser sends its selected business_type with a lookup. Server validates it against the six existing industry IDs. For snow/pressure/paving/landscaping/commercial only, validated address or exact coordinates create a static-only property session and Street View metadata, returning the existing fallback/center response shape. No Building Insights, Data Layers, RGB or mask is needed for normal loading. Preserve the existing report RGB recovery by obtaining the same Solar data lazily ONLY if /rgb is requested after report Static Maps failure; surface geometry/pricing never consumes those roof quantities. Persist the existing session metadata so the fallback survives worker/reload recovery. Thus normal service workflows avoid Solar entirely, but exceptional report recovery may still incur the original Solar calls. Existing nine-image aerial, zoom detail, drawing/geometry, price calculation, staged acceptance, credit deductions, retry receipts, saved estimates and PDF generation remain unchanged. Roofing and omitted business_type retain the existing automatic behavior; unknown/non-string industry values fail before upstream requests.

Prove before/after calls with a mocked URL-level provider recorder against the actual Flask routes, for both addresses and rural dropped pins across six industries and Area/Linear choices. Baseline five industries must demonstrate1 Insights+1 Layers; final expectation zero. Roofing must still request1+1 and retain area/pitch. Assert mismatched address causes zero Solar calls. Also verify the existing report RGB fallback still returns the original quality data on demand and does not change measurement credits; do not claim Solar is eliminated in that exceptional recovery. Retain Stage A no-charge-before-image-acceptance tests and test pending geocode preview cancellation. Run all existing regressions including six-industry measurements, independent geometry, pricing, save/reopen, PDF exporter and PostgreSQL concurrency. Actual authenticated browser/PDF checks depend on QA sign-in; physical devices must never be implied.

## Cost scenarios — assumptions, not invoices

Published first paid-tier USD rates per1000 events: Building Insights10, Data Layers75, Geocoding5, Static Maps2, Static Street View7, Mapbox Temporary Geocoding0.75. Respective monthly free caps10000/1000/10000/10000/10000/100000. Provider-volume tiers and other projects sharing billing accounts affect actual charges. Solar NOT_FOUND is unbilled; Street View metadata is free. Pricing is verified published data; request counts/mix below are modelling assumptions.

Planning scenario:80% service industries,20% Roofing;25% of Roofing jobs add one automatically measured garage. Two geocodes per property, one Mapbox check, one Street View image,14 Static Maps images (nine workspace+four detail+one report), no failures/reopens. Initial Solar currently1+1 for every property; added roof contributes0.05 Insights+0.05 Layers on average. After safe routing, initial Solar0.2+0.2 on average; added-roof cost unchanged.

Before marginal first-tier cost0.135/job; after0.067/job; saving0.068/job, about50.4%. Service-only job:0.13075→0.04575, saving0.085 (two Solar requests). Roofing unchanged. Full25/75/200 usage at that assumed mix:3.375→1.675,10.125→5.025,27.00→13.40 USD. These exclude free caps, volume discounts, hosting/email/support and actual account billing.

Illustrative otherwise-unused provider billing account with10000 properties/month at this mix: Insights10500→2500; Layers10500→2500 (16000 Solar calls eliminated). Applying published free caps and Static Maps volume tier gives total modelled provider cost1011.50→406.50 USD, saving605.00. This assumes140000 Static Maps,20000 geocodes,10000 Street View and10000 Mapbox requests; existing external billing-account usage could change those figures. Pending-preview cancellation savings are additional but not counted without real frequency data. No claim of measured invoice savings.

## Verified implementation checkpoint

Complete local recovery suite:61/61 commands passed after the lazy RGB recovery was included. The URL-level matrix covers26 actual Flask preparations:20 service cases at0 Insights/0 Layers versus1/1 each before, plus6 Roofing Area/Linear/Auto cases retaining1/1 and original pitch/area fields. No paid provider requests were made in these fixtures. Additional checks cover invalid industries, authoritative address mismatch, prepared/accepted/retried credit counts and on-demand RGB recovery including metadata reload without repeating Insights/Layers. Actual DOM/Leaflet tests explicitly load all five service industries with nine aerial images and correct business_type payloads; existing six-industry geometry/editing/pricing/saved reopening/Single+Expanded PDF-exporter tests pass. Pending-preview cancellation passes.

Cloud browser inventory contains only login pages, so fresh authenticated live Google imagery, generated/downloaded PDF visual inspection and physical devices remain unverified. Do not describe simulated DOM/exporter tests as actual live PDF downloads. GitHub CI (including PostgreSQL jobs) and Render's deployed commit must be checked after publishing; final results and resulting recovery checkpoint are reported in the conversation. All prior fixes and approved UI wording are retained; no credit-policy or resolution changes.
