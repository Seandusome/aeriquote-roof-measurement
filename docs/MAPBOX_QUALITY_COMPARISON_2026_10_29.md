# AeriQuote — final October29 Mapbox imagery quality comparison
Research and visual inspection only. STOP after reporting; no further development tonight.

## Outcome
**Insufficient evidence to approve Mapbox imagery for AeriQuote's six-industry measurement workflow.** This is an access/evidence limitation, not proof that Mapbox imagery is poor. Continue licensing discussions only to obtain current property-specific samples, source metadata and a written commercial licence/quote.

## Starting verification
Recovery branch landscaping-multi-area-recovery-oct11 HEAD3cecc95c3e08366d4bb2637d78bfb6c11bcd09d9; tree711690abb3e6ee322c71270f21df06fa9e0817e6. Read MAPBOX_IMAGERY_AUDIT_2026_10_29.md and latest RESUME_HERE_2026_10_28.md.
GitHub40962376994 and40962377015 both completed SUCCESS. Render test dep-dbhs3om0tbcc73afnqjg LIVE for exactHEAD. No manual deployment.

## Authorized inspection route and concrete limitations
1. Opened official https://www.mapbox.com/imagery in cloud browser. Its interactive page logged Failed to initialize WebGL.
2. Followed its visible Preview style link, without extracting/reusing credentials for independent API calls. Official satellite-streets-v11 preview remained blank, with console ReferenceError: L is not defined. Reloaded once; remained blank. Saved screenshot. No property navigation controls became available.
3. Opened official2024 aerial update article and followed its separate visible satellite-streets-v12 preview link. It returned Not Authorized - Invalid Token. Saved screenshot; no token alteration, bypass, account creation or API key generation.
4. Inspected the article's actual published Reno before/after images in the rendered webpage. Captured the page screenshot including labels/context. A subsequent attempt to open the observed larger public CDN image was rejected by this browser's site-safety policy. Stopped; did not retry by another channel or raw-download workaround.
5. No existing imagery-authorized developer session was established. The application has a Mapbox geocoding environment reference; that alone does not establish imagery/tracing authorization. Did not retrieve or use its secret.
6. No Google, Spexi, government or Vexcel-direct pixels substituted as Mapbox evidence.

The first preview failure is a browser/runtime/library limitation. The second is a rejected public example token. Neither establishes an AeriQuote defect, missing imagery at any location, global Mapbox outage or poor coverage. Raw URLs containing public preview credentials are omitted from documentation; no account credentials exposed.

## Property-by-property result
| Requested location | Genuine Mapbox pixels inspected at exact property? | Status and remaining verification |
|---|---|---|
|1715 2nd Avenue North,Saskatoon,SK|No|UNVERIFIED: roof/garage/drive/vegetation, capture, nativeGSD and alignment |
|2301 Avenue C North,Saskatoon,SK|No|UNVERIFIED: parking/service areas, roof/outbuildings, source/date and overlay alignment |
|1340 Southdale Crescent SW,Calgary,AB|No|UNVERIFIED: no parcel identification or roof-edge quality pass |
|Representative Edmonton residence|No|UNVERIFIED: prior government2025 Edmonton sample is not Mapbox; no address silently substituted |
|Warman,SK residence|No|UNVERIFIED: prior SGIC2021 sample is not Mapbox |
|Rural Saskatchewan property|No|UNVERIFIED: no exact parcel selected/claimed; date/nativeGSD and aerial-versus-satellite unknown |
|Representative U.S. residence|No individual parcel|UNVERIFIED at property scale; actual Reno,Nevada residential neighborhood example was viewed, with limitations below |

No precise coordinates were guessed for the three supplied addresses. A geocoding query without subsequent imagery inspection would not verify quality.

## Actual permitted public-preview evidence
Source page: https://www.mapbox.com/blog/updated-aerial-imagery-for-the-u-s-canada-and-europe
Article dateApril23,2024; publication date is NOT the image capture date.
- Actual rendered Reno neighborhood example shows rows of houses/roof footprints, curving streets and development blocks. Roads, open tracts and neighborhood layout are recognizable.
- In the roughly385px-wide displayed image, individual roof boundaries are small. Cannot confirm detached garages, precise eaves, complex planes, sidewalks, driveway edges, tree obstruction or contractor-grade detail.
- No scale, per-image nativeGSD, acquisition day, control points or georeferencing accompanies this screenshot. No accuracy calculation performed. Enlarging a screenshot cannot add source detail.
- The side-by-side depicts different development states; it is useful evidence of freshness risk. It does not prove the current service still serves either image.
- No same-property Google image was available for a controlled comparison; no Google-versus-Mapbox quality ranking made.

Evidence files:
- [Official Reno webpage preview](qa/mapbox-quality-2026-10-29/reno-published-example.jpg): genuine publicly rendered Mapbox article imagery, contextual screenshot; not a current-property service capture.
- [Blank official preview](qa/mapbox-quality-2026-10-29/preview-unavailable.jpg).
- [Invalid-token response from second official link](qa/mapbox-quality-2026-10-29/official-link-invalid-token.jpg).
Screenshots are research evidence with source context, not licensed reusable customer-PDF imagery. Mapbox/source copyright remains with owners. No API tokens committed.

## Six-industry assessment
| Workflow | Evidence needed | Current decision |
|---|---|---|
|Roofing|Complete visible roof boundaries, garage separation, complex-section visibility; confirmed contractor pitch; source alignment/control check|Not verified |
|Snow Removal|Parking/drive/sidewalk edges, obstacles and current site layout|Not verified |
|Pressure Washing|Small paved strips, sidewalks, drives and visible boundaries at usable scale|Not verified |
|Paving & Sealcoating|Parking/drive perimeter, islands and narrow segments|Not verified |
|Landscaping|Lawn/bed boundaries, tree occlusion, recent changes|Not verified |
|Commercial Properties|All relevant service structures/areas and large-property extent consistency|Not verified |

These are our acceptance criteria, not a claim of vendor inadequacy. No tracing or commercial-derived data was produced. A visually sharp image is not sufficient evidence of spatial or measurement accuracy; roof displacement/shadows can mislead even when native pixels are small.

## Coverage, licensing and cost findings preserved
Do not overturn the preceding audit. Mapbox's layer blends satellite and aerial sources. Vexcel partnership announcements do not prove every requested Canadian property has current high-resolution aerial coverage. Resolution, age and source may vary spatially and by zoom. Supplier Vexcel's own catalogue is not equivalent to Mapbox's delivered footprint.
Official references:
- https://docs.mapbox.com/data/tilesets/reference/mapbox-satellite/
- https://docs.mapbox.com/data/tilesets/guides/imagery/
- https://www.mapbox.com/imagery
- https://www.mapbox.com/legal/product-terms
- https://www.mapbox.com/pricing

Current audit's ProductTermsOctober20,2026 §§1.6,1.7,2.8.1 commercial tracing/PDF/caching restrictions remain. API free tiers do not supply these permissions. Separate CommercialSatellite rights, possible CommercialApplication classification, multi-tenant geometry storage, PDF forwarding, historical images and post-termination terms require written agreement. No new licence grant or price found in this visual task.

Prior API-only60tile/1.8static model unchanged: expected100/500/1000/5000 subscribers $0/$110.06/$410.02/$2204.95 monthly; full allowances $0/$217.50/$607.70/$2978.50. Assumptions, not measured traffic; excludes extra licence costs. No plans/allowances revised.

## Exact remaining questions for Mapbox sales — no contact made
1. Provide authorized current previews for the three exact addresses and representative Edmonton,Warman,ruralSK and U.S. properties, including complete roof+garage and service boundaries.
2. For each: aerial or satellite, upstream source, capture date, nativeGSD, orthorectification/positional accuracy and max useful zoom? Do these differ between interactive RasterTiles and StaticImages?
3. Does Mapbox presently deliver the cited Vexcel coverage at these locations, including small-town/rural footprints? What source replaces it outside coverage?
4. How are shadows, canopy, roof displacement, stale developments and source seams handled? Can unsuitable properties be identified before charging?
5. Is reproducible historical imagery available, or must contract permit retaining snapshots? Can the same estimate reopen without source drift?
6. Confirm commercial manual tracing, permanent derived geometry/quantities, multitenant employees, branded satellite PDFs, customer forwarding and post-termination archives.
7. Quote all licence minimums, seats/business fees, API spend commitments and satellite print/redistribution charges for current plan volumes.
8. Can Mapbox provide a working browser-compatible public or expressly authorized evaluation route without paid-account creation?

## Recommendation and next handoff
Pursue an evidence request, not implementation approval. Neither accept nor reject Mapbox quality based on these access failures. Existing ordinary API economics justify asking; total licensed affordability remains unknown.
If approved later, inspect genuine pixels at exact geocoded properties, preserve source attribution, compare like-for-like extents with available Google QA references and independently verify alignment/dimensions before suitability claims. No such pilot started tonight.

## Safeguards and verification
Research/docs only. No application changes, paid accounts, purchases, supplier outreach, manual deployments, account/customer records, pricing/geometry/PDF alterations or imagery integration changes. AutoMeasure preserved, AI Trace remains removed, QAmanualRoofing/vector restrictions intact.
Starting CI success verified. No new app regression suite run for documentation-only research. Final commit/deploy/check status reported separately after publishing; do not call queued/building work passed/live.
