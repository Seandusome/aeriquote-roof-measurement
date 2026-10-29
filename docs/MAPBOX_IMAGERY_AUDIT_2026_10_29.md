# AeriQuote — Mapbox imagery pricing and commercial licensing audit
October 29, 2026 (America/Edmonton). Research only; no application, imagery-provider, customer, pricing or database changes.

## Decision
**Pursue a written Mapbox sales quotation and property-specific evidence; do not approve integration or commercial launch yet.** Ordinary request charges look economically manageable under the stated assumptions. Commercial tracing and satellite-PDF rights are not supplied merely by paying for requests. Additional licence pricing, minimums and exact coverage remain unknown.

## Verified checkpoint
Recovery HEAD 51c3ce16fdde1cf04f4ddd7fcf6861823a51e852; tree 9aae043b1d5f2aaa87064c5fa5227e49fe376350. GitHub runs 40950579858 and 40950579865 completed successfully. Render test deployment dep-dbhqsn8u01pc73apej80 was LIVE for this exact commit. Branch protection remains absent; no administrative change made.

Read IMAGERY_PHASE2_2026_10_29.md, IMAGERY_LAUNCH_FEASIBILITY_2026_10_29.md and latest RESUME_HERE_2026_10_28.md. Re-read actual current app.py through GitHub blob e35719018a15c456d87de84e5004915790f9065b (1,519,393 bytes). The stale local checkout was not used as current source.

## Published request prices — USD
Source: https://www.mapbox.com/pricing (retrieved October29). Separate monthly product meters; graduated bands, not a flat rate on all usage. Free allowance is shared by the platform account, not separately granted to every AeriQuote subscriber. Order pricing can supersede public rates.

| Monthly requests | Raster Tiles / 1,000 | Static Images / 1,000 |
|---|---:|---:|
| Raster 0–750,000; Static 0–50,000 | Free | Free |
| Raster 750,001–2,000,000; Static 50,001–500,000 | $0.25 | $1.00 |
| Raster 2,000,001–4,000,000; Static 500,001–1,000,000 | $0.20 | $0.80 |
| Raster 4,000,001–20,000,000; Static 1,000,001–5,000,000 | $0.15 | $0.60 |
| Above these published volume cutoffs | Sales quotation | Sales quotation |

Raster Tiles is appropriate for raw mapbox.satellite XYZ imagery in Leaflet. Do not confuse it with style-rendered Static Tiles or GL JS map-load billing. Static Images supplies standalone estimate photographs; an image request does not additionally incur the underlying tile meter in this model. Navigation and unrelated products are excluded. No compulsory paid geocoding replacement is assumed.

## Explicit usage assumptions and reproducible calculations
These are planning assumptions, NOT measured AeriQuote Mapbox telemetry. No token was generated or used for imagery calls.

Subscriber mix: 62% Basic, 30% Pro, 8% Business. Expected measurement utilization: 80%,75%,65%. Per subscriber:
- Revenue: .62×29 + .30×59 + .08×99 = **$43.60/month**.
- Expected completed properties: .62×25×.80 + .30×75×.75 + .08×200×.65 = **39.675/month**.
- Full allowance: .62×25 + .30×75 + .08×200 = **54/month**.

A model measurement is one completed property job; multiple sections/lines on that property are not multiplied into separate imagery sessions. This modelling convention does not change application allowance accounting.

Base **60 raster requests/job**:
- 16 initial visible/prefetched tiles;
- 24 additional tiles during pan/zoom/edit exploration;
- 8 retry/reload requests, including failed/abandoned lookup traffic allocated to successful jobs;
- 12 averaged over saved-estimate reopenings.
An approximately 640px view can cross several 256px tiles per dimension. Buffering, retina configuration, viewport and repeated zoom levels affect counts. No assumed durable image-cache discount.

Base **1.8 Static Images requests/job**:
- 1 initial estimate photograph;
- .3 preview refresh/retry;
- .3 historical reopen;
- .2 PDF re-export.
Downloading both layouts may reuse one permitted image response, or may refetch. Model one provider photograph per render, not a charge per PDF page. Whether persistent reuse is licensed remains unresolved. Heavy scenario doubles tiles to120 and uses3 static requests/job.

| Subscribers | Usage | Measurements/month | Revenue/month | Raster | Static | Total API | API/job | Revenue share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
|100|Expected utilization|3,967.5|$4,360.00|$0.00|$0.00|$0.00|$0.0000|0.00%|
|100|Full allowance|5,400|$4,360.00|$0.00|$0.00|$0.00|$0.0000|0.00%|
|500|Expected utilization|19,837.5|$21,800.00|$110.06|$0.00|$110.06|$0.0055|0.50%|
|500|Full allowance|27,000|$21,800.00|$217.50|$0.00|$217.50|$0.0081|1.00%|
|1000|Expected utilization|39,675|$43,600.00|$388.60|$21.42|$410.02|$0.0103|0.94%|
|1000|Full allowance|54,000|$43,600.00|$560.50|$47.20|$607.70|$0.0113|1.39%|
|5000|Expected utilization|198,375|$218,000.00|$1,897.88|$307.08|$2,204.95|$0.0111|1.01%|
|5000|Full allowance|270,000|$218,000.00|$2,542.50|$436.00|$2,978.50|$0.0110|1.37%|

Fractional job/request totals are cohort expectations, not possible individual invoice counts. Round only final money; component rounding can differ from rounded total by one cent. The financial JSON stores raw values.

Independent Python Decimal calculation reproduced JavaScript totals and verified tier boundaries at750k/2m/4m raster and50k/500k/1m static. Example: 1,000 expected subscribers use2,380,500 tiles and71,415 statics: $388.60 + unrounded$21.415 = rounded **$410.02**.

At5,000 subscribers, full usage creates16.2m raster and486k static requests, inside displayed bands. Heavy usage creates23.805m expected or32.4m full tiles, **above20m: quotation required**. Do not extrapolate the last tier as a verified rate. Heavy static costs alone are$526.10 expected or$698 full. Illustrative extension of$.15/1k beyond20m would yield total$4,209.35 expected / $5,670.50 full, but these are explicitly unquoted sensitivities, not published bills.

## Business-plan stress and licence headroom
At the first paid bands, no free-tier allocation, base imagery marginal cost/job is60×.25/1000 +1.8×1/1000 = **$.0168**. Full monthly quantities therefore cost Basic$.42, Pro$1.26, Business$3.36. Heavy120/3 gives$.033/job: $.83/$2.48/$6.60 (half-up rounding). At200 jobs, Business earns$.495/job; ordinary request charges alone do not threaten the$99 plan under these assumptions. Coverage failure, repeated exploration and separate licence fees could change that conclusion.

If imagery is allocated a hypothetical20% of revenue, not a promised profit margin:
- Business$19.80 monthly budget less base$3.36 leaves **$16.44/business/month**, or$.0822/job, for licensing and any additional image delivery overhead.
- Mixed platform expected licence headroom after request charges:100 subscribers$872;500$4,249.94;1,000$8,309.99;5,000$41,395.05 monthly.
- At full usage: $872/$4,142.50/$8,112.30/$40,621.50.
These headrooms are limits under a chosen budget, not supplier prices. If plan currency differs from USD, exchange rates must be applied; comparison assumes USD plan revenue. Taxes, payment fees, support, hosting, existing Google address/Street View costs, monitoring and development are excluded. Add measured hosting/PDF compute and existing non-Mapbox bills for an all-in company budget. No subscription prices or allowances changed.

## Current contractual provisions
The legal portal now links **Product Terms updated October20,2026**:
https://www.mapbox.com/legal/product-terms
https://cdn.prod.website-files.com/609ed46055e27a02ffc0749b/6ad79764a359d21b46049ea4_Mapbox%20Product%20Terms%20%28October%2020%2C%202026%29.pdf

Retrieved original PDF and extracted text; SHA256 e92f762d954e30fb637b24863898779ad9bbe167fd927d735266bfacb0c55ec2. No reliance on older2023 clause numbering.
- §1.2: additional licences must be explicit active-Order line items; prepaid services do not substitute.
- §1.2.3: specified production categories include analytics and real estate; ask Mapbox to classify AeriQuote.
- §1.6: commercial tracing/derivation is outside the noncommercial/OpenStreetMap exceptions.
- §1.7: PDFs are printed media; default print permissions are limited to Streets v8+ and specified Japan uses. §1.7.4 allows purchased rights.
- §§1.9–1.11: restrictions cover storage, API access, redistribution and end users.
- §1.4: attribution/logo obligations apply.
- §2.8.1: same-device caching up to30 days; proxy/screenshot distribution is restricted. Server-rendered customer output requires express rights.
- §2.8.2: imagery may not enhance other imagery.

MSA portal: https://www.mapbox.com/legal/msa
Current linked form v8.3.5, September12,2025; §§1.2,8.3 and definition6 address application access, termination/deletion and substantial independent application functionality. PDF SHA25681d64af9d67db45e9f9cd06444944c7510606908a8c27ec1e677a65101c6d774. The executed agreement/order must be checked; this public form is not evidence of AeriQuote's negotiated terms.

Official imagery guide explicitly names a **Commercial Satellite licence** for commercial derivative vector datasets:
https://docs.mapbox.com/data/tilesets/guides/imagery/
The imagery marketing FAQ is more broadly restrictive; neither page grants AeriQuote's full workflow.

Practical conclusions (our interpretation, requiring contract confirmation):
| Requirement | Status |
|---|---|
| Leaflet satellite display | Technically supported; application licence/attribution still apply |
| Paid contractor manual tracing | Separate express commercial permission required |
| Permanent derived polygons/lengths/quantities | Must be included in negotiated rights, including after termination |
| Satellite photographs and overlays in customer PDFs | Explicit satellite print/static-digital permission required |
| Customer forwarding, redistribution, historical reopening | Scope, retention and survival rights unresolved |
| Independent businesses/employees under one SaaS account | End-user application model exists; OEM/seat/business scope needs written acceptance |
| Commercial Application licence | Possible required category; not automatically every B2B app merely from the heading |
| Custom OEM agreement | May be the contract vehicle; no proof a particular named package is mandatory or sufficient |

Do not apply a permissive print-help page or a Streets exception to satellite imagery. §2.8.1's limited on-device permission and HTTP cache headers do not grant indefinite server archives. Ask separately about browser cache, server proxy, permitted snapshots, immutable historical PDFs and termination.

## Coverage and measurement suitability
Sources:
- https://docs.mapbox.com/data/tilesets/reference/mapbox-satellite/
- https://www.mapbox.com/imagery
- https://www.mapbox.com/blog/updated-aerial-imagery-for-the-u-s-canada-and-europe (April23,2024)
- https://www.mapbox.com/blog/670k-sq-km-of-updated-aerial-imagery-for-the-us-and-europe (November2025 update)
- https://www.mapbox.com/blog/mapbox-adds-10-million-sq-km-of-new-30-cm-satellite-imagery (January7,2026)

The product blends satellite and aerial sources; high zoom is not proof of native detail. Documentation lists regional30–60cm and selected7.5cm+ coverage; marketing mentions selected5cm imagery. The2024 announcement includes Canadian cities but provides no per-property guarantee. The2025 aerial update lists U.S. cities including Chicago/Denver, generally10–20cm. January2026 adds30cm satellite mosaics in selected areas; published<5m accuracy is not a property-specific survey certification. Sources and imagery change; no guaranteed update schedule.

| Requested region / representative check | Verified | Still needed |
|---|---|---|
| Saskatoon: prior QA vicinity2301 Ave C North | General global coverage | Actual native GSD, date, aerial vs satellite, shadows, alignment |
| Calgary / Edmonton residential+garage | Canadian city aerial programme exists | Local footprint, source/capture and actual-property pixels |
| Toronto / Vancouver | Same national city programme evidence | Exact roof/parking sample metadata and pixel review |
| Warman / other small Canadian towns | No town-specific high-res guarantee found | Footprints, current capture, garage/drive detail |
| Rural Saskatchewan | Global layer only establishes broad coverage | Aerial availability, age, native detail and accuracy |
| Chicago / Denver urban | Named in2025 aerial update | Actual sample dates/source/positional check |
| Seward,Nebraska / rural Nebraska | No property-specific high-res proof | Town/rural source and detail; do not equate supplier's own coverage with Mapbox's delivered layer |

**No Mapbox property pixels were downloaded or visually verified in this batch.** No live measurement-accuracy, roof-edge or PDF suitability pass is claimed. Government-image inspections in the previous report are not Mapbox evidence. Request approved samples/access and native metadata before a pilot. Public claims differ by source/version; do not advertise uniform5/7.5/30/50cm coverage.

Our engineering assessment: fine roof edges, small garages, narrow sidewalks and curb runs need strong source detail and complete visible boundaries. Larger snow/landscaping/parking areas may tolerate coarser pixels but still need field/control-point checks. Trees, shadows, relief displacement, ortho errors and old captures can make even high-resolution imagery unusable. Flat photographs do not provide roof pitch; contractor confirmation remains necessary. No invented boundaries or silently incomplete quotes.

## Current-code compatibility — verified inspection, not implementation
Mapbox currently appears in app.py as a **geocoding ambiguity check**, not as an aerial raster or Static Images provider:
- MAPBOX_ACCESS_TOKEN environment lookup, line42.
- /mapbox-test, lines4067+: Geocodingv6 forward; country=ca,limit5.
- Client invokes this address check near line1969.

Existing Leaflet maps near491 and2310 use aerial image overlays/bounds, with server and direct Google Static Maps paths near1006/1887. Areas/lines/roof sections use geographic coordinates; imagery need not replace geometry/pricing engines. Retain all six industry workflows, saved quantities, confirmed roof pitches, account isolation and monthly allowances.

Required future adapter scope, subject to separate approval:
1. Add licensed satellite XYZ display or static overlays while preserving exact Mercator bounds/zoom semantics. Mapbox style rendering and traditional256px maps can have different zoom conventions; current staticMapBounds uses256×2^zoom. A one-level adjustment may be required; treat this as an adapter risk to verify, not a measured defect. Independently validate extents rather than blindly copying zoom.
2. Replace all aerial output paths, not just initial display: manual roof maps, correction images, wide aerial, exact pin, fallback and customer report images. Keep attribution, north-up orientation and source native resolution.
3. Rework saved-estimate image provenance/reference only after reviewing migration/retention risks. Historical Google photographs do not become Mapbox-licensed by changing provider.
4. Keep overlay composition from exact saved geometry locally; do not simplify measurements to fit Static Images URL limits.
5. Preserve PDF proportions, dimensions and layout; verify provider attribution fits. No redesign proposed.
6. Keep AutoMeasure code intact. Mapbox imagery alone does not replace Solar building geometry, masks, height or roof pitches.

Hidden dependencies: Google geocoding near4142, Street View metadata/image near4195, Google-key prerequisite on saved editing-session near4893, and Solar BuildingInsights near3280/DataLayers near4267. /rgb near4985 can still request Solar on legacy surface_static report fallback; manual_roof_session blocks that recovery. An imagery-only substitution does not make the whole app Google-free or legalize historical imagery. No change made to those paths.

Potential replacement can preserve measurement engine, pricing/taxes/security, but it is not a URL-only switch. Estimated small adapter/pilot1–2 engineer-weeks plus1–2 weeks for six-industry save/reopen/Single/Expanded regression and imagery alignment, contingent on contract and QA access. This is a planning estimate, not vendor evidence.

Technical references:
https://docs.mapbox.com/api/maps/raster-tiles/
https://docs.mapbox.com/api/maps/static-images/
https://docs.mapbox.com/help/glossary/zoom-level/
Raster is XYZ-compatible and supports512px@2x; Static Images supports WebMercator,1280px dimensions plus@2x,0–22 zoom and8192-character URLs. Current Standard Satellite is not supported by Static Images; satellite-v9 is documented. API camera pitch is perspective tilt, not roof pitch. No need to add Navigation, route products or terrain to calculate contractor-confirmed roof surface areas.

## Next decision gates and unsent inquiry
1. Send only after Sean approves the inquiry below, via official https://www.mapbox.com/contact . imagery@mapbox.com is published for imagery questions, not evidence of sales authority.
2. Obtain a written contract/quote explicitly covering commercial derivation, multitenant usage, PDFs and historical rights. Ask which licences are additive and whether minimums include API spend.
3. Obtain property-specific aerial source/date/nativeGSD/accuracy and representative samples for each region above.
4. If licence economics and quality pass, approve an isolated adapter pilot and independent geometry/control-point/PDF tests. No implementation now.
5. Continue government-region alternatives in parallel; no supplier comparison justifies a rushed unauthorised launch.

### Draft — not sent
Subject: Commercial satellite tracing and customer PDF rights for AeriQuote

Hello Mapbox Sales,

I’m Sean Dusome, founder of AeriQuote, a Canada/U.S. contractor SaaS for roofing, snow removal, pressure washing, paving, landscaping and commercial properties.

We are evaluating Mapbox Satellite through Leaflet and the Static Images API. Contractors would manually trace service areas, roof sections and lines; permanently save their geometry and quantities; and distribute branded customer PDFs containing aerial imagery and overlays. Roofing pitch is contractor-confirmed, not inferred from imagery.

Please confirm in a proposed written agreement:
1. Which Commercial Satellite, Commercial Application, print/redistribution or OEM rights are required, including exceptions to Product Terms §§1.6–1.10.
2. Whether independent businesses and employees can share our SaaS integration, retain derived measurements permanently, forward PDFs to customers, and reopen historical estimates.
3. Permitted image caching, snapshot storage, attribution, retention and post-termination rights, including already-distributed PDFs.
4. Current aerial coverage, capture dates, native resolution and positional accuracy for Saskatoon, Warman, rural Saskatchewan, Calgary, Edmonton, Toronto, Vancouver and representative U.S. urban/rural properties.
5. All annual minimums, seat/business/property fees and API charges. Our plans are $29/25, $59/75 and $99/200 monthly measurements. Please quote pooled SaaS usage at 100, 500, 1,000 and 5,000 subscribing businesses, including full allowance use.

We have not approved a Mapbox imagery integration or commercial launch. Could you provide a suitable evaluation path and complete pricing?

Thank you,
Sean Dusome

## Verification and limits
- Current remote source inspected; no secrets or customer records accessed.
- Independent JS/Python Decimal financial results and tier-boundary checks passed.
- No application regression suite run: no application changes; existing base CI success verified.
- No account creation, API keys, paid imagery, supplier contact, live-provider measurement tests or deployment trigger performed.
- Documentation-only commit; update branch using expected-HEAD lease, never main.
