# AeriQuote — technical briefing for a 15-minute licensing discussion

Source inspection: recovery checkpoint 3c4e563, October 27, 2026. This is a description and permission request, not a claim that any use is licensed. No integrations were changed for this review.

## Product and workflow (2 minutes)

AeriQuote is contractor SaaS for Roofing, Snow Removal, Pressure Washing, Paving & Sealcoating, Landscaping and Commercial Properties. Contractors load an address or exact coordinates, draw service boundaries/lines or use existing automatic roofing data, review quantities and rates, enter customer information, then save and distribute a branded estimate/PDF. It is not an energy-system design application.

## Current technical use (4 minutes)

- **Google Geocoding API:** server-side address preview and authoritative property validation, including ambiguity/street-number checks. The inspected measurement workspace uses this flow rather than a Places Autocomplete SDK.
- **Google Maps Static API:** server-proxied satellite images displayed as georeferenced Leaflet image overlays. Normal service-property loading assembles nine 640×640 images at scale 2; higher zoom/panning can request detail imagery. Report imagery is separately fitted to saved geometry. Some manual roof report paths send confirmed outline coordinates as Static Maps path parameters.
- **Google Street View Static API and metadata endpoint:** property photograph, availability and capture-date caption, optionally included in estimates/PDFs.
- **Google Solar API Building Insights and Data Layers:** existing ordinary Roofing loading/AutoMeasure, roof areas/segments/pitch, automatic additional-building/retry paths, RGB/mask imagery and recovery. Normal five-industry manual property loading skips Solar. An existing report-imagery failure recovery can still call Solar; do not describe those industries as universally Solar-free.
- **QA-only manual Roofing:** an existing flag plus account allowlist permits manual roof tracing with explicit section pitches and scope confirmation. Its manual session routes are Solar-free; default ordinary Roofing and AutoMeasure code remain intact. It is not enabled for paying customers by this review.
- **Mapbox Geocoding v6:** separate nearby/same-number address verification, currently configured for Canada. Leaflet is the drawing/display interface; Solar rasters also use GeoRaster/Leaflet. The inspected code does not use Mapbox satellite tiles as the normal background.

## Measurements, storage and export (3 minutes)

Contractor-drawn latitude/longitude vertices are used to calculate polygon areas and line lengths. Manual pitched sections use ground area divided by cos(pitch); Solar roofing uses supplied geometry/pitch with independent consistency guards. The server stores estimate snapshots, coordinates, quantities, pitches, pricing, customer fields and revisions. It also persists some session/provider metadata and selected Street View image data. Not every aerial is stored permanently: reopening may rebuild imagery from saved coordinates.

Customer previews overlay saved measurements on aerials. Existing Single and Expanded PDFs rasterize report imagery, overlays, labels, customer/business branding and financial totals with html2canvas/jsPDF. Some manual roof images contain outlines baked into the requested Static image. PDFs are intended for contractor distribution to customers. Existing session caches, stored imagery, attribution and retention behaviour all require contractual review, not just display rights.

## Specific written permissions needed before commercial launch (6 minutes)

1. May a commercial contractor SaaS display these Google satellite/raster products inside Leaflet, alongside the separate Mapbox address-verification service? Which products, attribution rules and interface restrictions apply?
2. May contractors trace roofs, lawns, parking/service areas and lines from that imagery, calculate quantities, and retain/reopen/export those coordinates and derived measurements?
3. May branded customer PDFs embed imagery and overlays, and may customers retain/forward them? What attribution, resolution, fixed-media, distribution and retention limits apply?
4. Is general roofing estimation using Solar Building Insights/Data Layers permitted under our applicable agreement? If not, is a written exception or alternative commercial agreement available? We need an explicit answer covering area, individual planes, pitch, detached garages and non-energy estimates.
5. What session caching, database persistence, backups and saved-estimate imagery regeneration are authorized? What must be removed or re-requested, and on what timeline?
6. Who can give a binding written scope determination, and what agreement, SKU, pricing and technical changes would it require? Please distinguish partner guidance from permission granted by the contracting/licensing authority.

Do not treat avoiding Solar, paying for requests, a partner call or an image-free PDF contingency as resolving the separate tracing/derived-data/display/export permissions. Obtain written confirmation before launch. Nearmap discussions remain a separate potential licensing path; no provider access or rights are assumed here.
