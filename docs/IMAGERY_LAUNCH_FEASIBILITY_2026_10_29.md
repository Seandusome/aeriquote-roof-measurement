# AeriQuote — imagery licensing and launch feasibility
Research date: October 29, 2026 (America/Edmonton). Research and planning only.

## Verified starting state and scope

Recovery branch: landscaping-multi-area-recovery-oct11, repository Seandusome/aeriquote-roof-measurement. GitHub HEAD 78dd1ffbc938157f2f2580f8c4cba77750a05543 (tree e31b47bd106bcd65ea4825eb40bb444f37eec4fe); application workflow 40779768758 and recovery workflow 40779768938 succeeded. Recovery and postgres_integrity jobs explicitly succeeded. Render test deployment dep-dbh7cc5g1s2s73fij2r0 is LIVE for this exact commit. Main remains c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a, read-only. Recovery branch protection remains absent; no administrative changes.

Read the October 28 general and account-security handoffs, API cost audit and October 27 Google call briefing. Re-inspected the current app.py blob e35719018a15c456d87de84e5004915790f9065b directly from GitHub; an older local checkout was not used as current source.

New evidence supplied by Sean: MapsPeople, a Google Maps Platform Premier Partner, stated in writing that the proposed Google-imagery tracing, derived-measurement storage and customer aerial-PDF workflow is not permitted under standard terms, and that its enterprise offering cannot provide an exemption. This report records Sean's account of that correspondence; the original letter was not independently retrieved. Treat the existing Google workflow as NOT cleared for commercial launch. No integrations were disabled or changed.

No vendor contacted, trial/account created, imagery purchased, application code changed, customer/database record accessed or deployment manually triggered. Only research documentation is being committed. Automatic documentation deployments may occur under the existing recovery-branch configuration. Previous checkpoints remain ancestors.

## 1. Nearmap meeting briefing — approximately two minutes

AeriQuote is a multi-tenant contractor SaaS serving Roofing, Snow Removal, Pressure Washing, Paving & Sealcoating, Landscaping and Commercial Properties. Independent businesses and their employees trace property features in Leaflet, retain latitude/longitude geometry and quantities, apply their own rates/taxes, then distribute branded Single or Expanded estimate PDFs with an aerial image and measurement overlays. Manual Roofing uses contractor-confirmed pitches; we are asking for imagery, not roof reports or AI geometry.

We need an OEM/embedded SaaS agreement explicitly authorizing commercial tracing, permanent measurement retention, third-party customer PDFs, customer forwarding, historical reopening and survival rights after subscription cancellation. Please provide imagery-only API pricing, all minimum commitments and billable units, plus property-level Canadian/U.S. coverage and native resolution.

Technical fit looks plausible. Licensing, address-level coverage and unit economics are still open. Our illustrative full-use imagery budgets at 20% of plan revenue are about $0.23 Basic, $0.16 Pro and $0.10 Business per completed property workflow, including retries, PDFs and reopening. These are negotiation budgets, not Nearmap quotations.

## 2. Licensing findings and questions for the Account Executive

The current Nearmap MSA is dated for customers signing from February 5, 2026. Sections 2.1.1–2.1.3 limit standard use/output to internal purposes and reserve other uses for prior written consent. Section 2.5 restricts third-party/product/derivative uses; section 2.2 requires attribution. Section 6.4 requires cessation/deletion at termination, with a narrow non-use archival exception. Sections 15.8–15.9 provide an order-form precedence and signed-amendment route. These are reasons to negotiate, not evidence approval will be granted. A standard API subscription is insufficient evidence for AeriQuote's workflow. [N1]

Ask for written answers incorporated into an authorized order form/addendum:

1. Does the agreement expressly permit independent contractor businesses, their owners and employees to use AeriQuote's embedded Leaflet interface commercially? Are they licensed SaaS end users, sublicensed users or required Nearmap account holders? Are seat/account/customer caps or per-tenant fees imposed?
2. May contractors manually trace roofs, roof sections, garages, lawns, driveways, parking lots and linear features, calculate areas/distances and retain the resulting coordinates, pitches and quantities permanently? Who owns those records? Distinguish numerical measurements, editable vector geometry and source-image pixels.
3. May AeriQuote create high-resolution branded PDFs containing source imagery plus outlines, dimension labels and pricing? What pixel/DPI/AOI limits, watermark and attribution rules apply? Approve BOTH existing Single and Expanded layouts.
4. May contractors send PDFs to customers and customers retain, print and forward them to their own employees, owners, insurers or other relevant parties? Must recipients have subscriptions? Does embedding a raster map with vector annotations meet required fixed-output rules?
5. May saved estimates be reopened, edited, re-exported and viewed years later? May AeriQuote retain a licensed image snapshot, or must it re-request a historical survey? What is the cost after 30 days?
6. Do geometry ownership/use, already-distributed PDFs and permitted historical viewing survive termination of AeriQuote's agreement OR the contractor's subscription? Request explicit survival language; an archival exception that forbids use does not support ordinary customer reopening.
7. Which exact SKUs cover Tile+Coverage and/or imagery-only Transactional Content/Staticmap? Can imagery be bought without AI packs, DSM, roof reports or per-roof analysis?
8. Provide written coverage/date/native-GSD examples for Saskatoon, Edmonton, smaller Saskatchewan communities and rural SK, plus U.S. metro/small-town/rural locations. Are detached structures and entire large commercial parcels covered? Which datasets are owned versus third-party licensed?
9. What are the billing currency, annual/minimum commitment, minimum seats, prepaid blocks, rollover, overages, rate limits and price-change protections? Define billable coverage calls, tiles, bytes, AOIs, buildings, survey dates, retries, empty results and PDF re-exports.
10. Can AeriQuote use a restricted server proxy and/or restricted browser credentials? Specify CORS, allowed domains, key sharing/tenant attribution, permitted session caching, stored image retention/backups and transaction-token handling. Do not equate a token lifetime with a storage license.
11. Can an imagery-only AOI include more than one building without multiple property charges? How are overlapping AOIs, pans beyond the initial bounds, failed downloads and duplicate requests charged? Can nonbillable availability checks precede a transaction?
12. Will the agreement explicitly permit non-Nearmap annotations and the current separate address-verification workflow? Identify any restrictions on combining providers, legacy Google-derived records or third-party imagery. We will not retrace/relicense historical Google content merely by changing the background.
13. Who has authority to approve these rights, which agreement supersedes standard restrictions, and can we receive an approved evaluation scope before any integration trial? No implied permission from marketing demonstrations.

## 3. Technical feasibility — retain the engine, replace the imagery dependency boundary

Confirmed current architecture at 78dd1ff:

| Component | Current dependency | Retention assessment |
|---|---|---|
| Drawing/display | Leaflet, georeferenced image overlays, markers and polygon/line layers | Retain interface and editing safeguards; add an approved imagery adapter later |
| Area/Linear calculations | Saved lat/lng vertices; local polygon area; map.distance lengths | Retain calculations unchanged; test projection/bounds rather than rescaling geometry |
| Manual Roofing | Traced sections, explicit pitch confirmation and surface-area adjustment | Retain pitched manual engine and detached sections; currently QA-only |
| Prices/taxes/accounts | Existing independent validation, branding, business isolation and allowances | Retain; provider billing must not redefine customer measurement credits |
| Saved estimates | Geometry, pitches, customer/branding/pricing snapshots and revisions | Retain schema/behaviour initially; any provider metadata/storage proposal needs approval |
| Aerial PDFs | Leaflet/report images, html2canvas and jsPDF; some manual-roof imagery has Google paths baked in | Preserve design/export machinery; replace image acquisition and local overlay compositing later |
| AutoMeasure | Google Solar geometry, pitch, RGB/masks, structures and retry paths | Preserve code; Nearmap imagery alone does NOT replace automated geometry/pitch |
| Addresses/Street View | Google geocoding/Street View; separate Mapbox address verification | Not replaced by buying aerial imagery; separate rights and launch decisions required |

Current functions/routes include loadStandardWideAerial, refreshAerialDetail, loadRaster, perform_property_lookup, /wide-aerial, /fallback-map, /exact-pin-map, manual-roof/customer report image routes, saved_estimate_editing_session and /rgb. Normal surface loading assembles nine Google 640x640 scale-2 images; zoom detail/report/reopen may request more. There are also direct browser Google Static fallbacks. Five surface industries skip Solar during ordinary loading, but /rgb still contains lazy Solar recovery after report failure. QA manual Roofing sessions explicitly reject that Solar recovery. Ordinary Roofing/AutoMeasure remains Solar-dependent. Therefore replacing only the initial visible aerial is NOT a complete migration.

### Nearmap APIs and necessary changes (not implemented)

- Tile API uses 256x256 Web Mercator XYZ tiles, matching Leaflet's usual coordinate model. Use vertical imagery for measurements. Panorama is a visualization product with different display proportions, not a measurement substitute. [N2]
- Coverage API exposes survey IDs, capture dates, native pixelSize and maximum tile zoom, plus survey boundaries. Select and pin a verified survey; check the whole measurement bounds, not just the property pin. Do not quietly substitute a different capture at re-export. [N3]
- For report pixels, evaluate imagery-only Staticmap v3 via Transactional Content. Its image endpoint supports JPG/PNG/GeoTIFF/world files, bounding boxes and up to4096x4096 per image/tile. Point/radius requests limit radius to100m; large sites need an approved bbox/tiled approach. Returned georeferencing and resampling must be verified. [N4]
- Transactional Content charges at the coverage transaction, returns costOfTransaction and a30-day token, and supports repeated content retrieval within that token's scope. This is distinct from the DSM/True Ortho v2 billing model, which counts the first successful image. Do not apply v2 billing assumptions to v3. Imagery-only commercial entitlement remains a vendor question. [N5,N6]
- Native resolution is property/survey dependent. Nearmap's content guide describes4.5cm GSD for its current camera system; coverage marketing now advertises as low as4cm. Neither is an assurance for a specific Saskatchewan property. Its published U.S. Reach expansion starts in2027; do not count future coverage as launch coverage. Canadian/rural address coverage was not authenticated or visually tested here. [N7,N8]

Likely future adapter work: authenticated imagery routing; approved key restrictions/proxy; explicit no-coverage handling; accurate world-pixel bounds; report pixels with saved overlays rather than Google path parameters; all exact-pin/detail/retry/reopen paths; attribution; CORS-safe canvas capture; date/scale metadata; caching/retention rules; request metering and429 handling. Remove no existing integration during this research.

Nearmap vertical imagery supplies appearance, not verified roof slope. Manual roof pitches remain contractor-confirmed. A ground outline of a multi-pitch roof still requires properly divided confirmed sections; higher-resolution photography cannot infer missing planes. Detached garages must be explicitly included. Saved coordinates must never be shifted to visually match a different provider; investigate misalignment and require reviewed corrections.

Estimated effort (planning assumption, no implementation): a narrow licensed QA map/report proof could take roughly3–5 engineering days once access is granted. Covering all imagery/retry/reopen paths and six-industry browser/PDF regressions could take an additional1–3 weeks; allow2–4 weeks total. Contracting, coverage gaps, historical-image rights and any separately approved storage migration can extend this. No claim of completed integration.

### Acceptance gate for a later approved pilot

Use explicitly authorized QA imagery at Saskatoon, Edmonton, small-town/rural SK and U.S. metro/small-town/rural sites. Check capture dates, native GSD, positional accuracy/building lean, occlusion and snow cover. Compare independent reference lengths/areas; no accuracy claim from pixel resolution alone. Exercise all six industries, multi-area plus line, confirmed roof planes/garage, first/second touch edits, Save/Cancel, failed requests, retries, reload and saved reopening. Verify no geometry/financial snapshot changes and no credit-accounting changes.

Download actual Single/Expanded PDFs at320/390/768/1440px, inspect photographs, overlays/dimensions, attribution, Street View treatment and source proportions. Record upstream calls, bytes and transactions for load/pan/zoom/retry/PDF/reopen, including after token expiry. Use source-call assertions to detect unintended Google/Solar fallback in any future Nearmap-only pilot. No such pilot, live imagery comparison or physical-device testing was performed in this research.

## 4. Economics — explicit scenarios, no vendor quotes

All amounts below are modelled USD, assuming the stated $29/$59/$99 subscriptions are also USD, before tax, discounts, refunds and FX. Confirm billing currency. These are planning assumptions, not actual Nearmap/Eagleview/Hexagon/Vexcel quotations. No applicable public AeriQuote SaaS redistribution tariff was verified.

Let R=monthly net subscription revenue, A=allowance, u=utilization, k=billable-workflow multiplier including retries/reopens, F=allocated fixed vendor fee and c=variable cost per workflow. Monthly imagery cost is F + A*u*k*c for an additive contract; if a quote uses a minimum-spend floor instead, use max(minimum,usage), not both. True sustainable pricing also depends on payment fees, hosting, email, support, sales, refunds and required profit, which are unknown.

R/(A*u) is only a zero-other-cost revenue ceiling, NOT a sustainable purchase price. At full utilization those ceilings are Basic$1.16, Pro$0.7867 and Business$0.495 per property. An example policy reserving10–20% of revenue for ALL imagery leaves80–90% for other costs and profit, without guaranteeing either.

| Plan | Allowance |20% monthly imagery budget|20% budget/job at25% use|at50% use|at100% use|10% budget/job at100% use|
|---|---:|---:|---:|---:|---:|---:|
|Basic $29|25|$5.80|$0.9280|$0.4640|$0.2320|$0.1160|
|Pro $59|75|$11.80|$0.6293|$0.3147|$0.1573|$0.0787|
|Business $99|200|$19.80|$0.3960|$0.1980|$0.0990|$0.0495|

Utilization levels are sensitivity scenarios, not measured customer behaviour. Fractional jobs represent portfolio averages. A25% assumption is not safe for underwriting a200-credit commitment; stress-test full use. Figures assume F=0 and k=1. If k=2, allowable variable unit rates halve.

|Hypothetical all-in cost/job|Basic full-use monthly cost|Pro full-use monthly cost|Business full-use monthly cost|
|---|---:|---:|---:|
|$0.05|$1.25|$3.75|$10.00|
|$0.10|$2.50|$7.50|$20.00|
|$0.25|$6.25|$18.75|$50.00|
|$0.50|$12.50|$37.50|$100.00|

At50% utilization these costs halve. At$0.10/job Business spends20.2% of revenue before every other cost; at$0.50 it exceeds revenue at full use. “Per API request” must be converted into an all-in property cost: a viewing session may load many tiles, multiple resolutions, a PDF image and historical reopens. One AeriQuote allowance credit does not imply one vendor request/credit.

Portfolio example, entirely hypothetical:20 Basic +50 Pro +30 Business users yield$6,500/month,10,250 maximum properties, or5,125 at50% utilization. A20% imagery envelope is$1,300. With an ADDITIVE$500 fixed fee, remaining variable budget is$800: $0.1561/property at50% or$0.0780 at100%. At only10 subscribers in the same mix, revenue is$650 and the20% envelope$130, so a$500 minimum already breaks that target. Annual commitments must be tested against actual subscriber ramp, not only marginal rates.

Nearmap documents several independent meters:2D MB/GB, API daily requests and product/property credits depending on subscription. Its current API usage guide says the minimum purchasable API Daily Rate is2,000 requests/day; confirm whether an OEM imagery-only quote uses that model. These are units/capacities, not dollar prices. Transactional pricing tables are account-specific; a30-day reuse token does not guarantee free multi-year reopening. [N9,N10,N11]

## 5. Alternatives — imagery APIs, not roof-report purchases

|Supplier|Verified technical evidence|Coverage/resolution limitations|Commercial tracing/storage/PDF status|Cost structure and fit|
|---|---|---|---|---|
|Nearmap|XYZ, Coverage, Staticmap/transactional imagery|Address-level CA/US/rural availability not verified; survey GSD/date required|Standard MSA is insufficient; negotiate explicit SaaS/output/survival rights|Contract quote; request imagery-only, all meters and minimums|
|Eagleview — follow-up #1|Imagery discovery,256px tiles, images up to4096px and orthomosaic endpoint; not limited to roof reports [E1]|Official platform article reports94% U.S. population and65%+ Canada;2-inch/1-inch products vary by capture [E2]|SaaS tracing, vectors, customer PDF distribution and post-term retention UNCONFIRMED; marketing integration capability is not a license|No applicable public imagery-only OEM tariff verified; request geographic/API/volume quote, no report bundle|
|Hexagon HxGN Content Program — follow-up #2|WMS/WMTS and REST/SOAP streaming, imagery downloads [H1]|U.S.15/30cm; selected Metro HD5cm; parts of Canada, exact SK/rural gaps unknown [H1]|Standard EUAA internal-use/access/distribution restrictions require a specifically negotiated commercial license [H2]|Annual AOI streaming or pixel downloads; OEM resale pricing unknown. Coarser imagery may suit large service sites but must not be assumed adequate for roof edges|
|Vexcel — conditional reserve|Current API v2 ortho XYZ/WMTS; Canadian urban7.5cm imagery [V1,V2]|Canadian urban examples include Edmonton; small-town/rural SK not verified|Published EULA2.2(d) explicitly prohibits vectorized representations;2.2(b) limits stored product to one week and requires destruction on termination [V3]. Do not treat ordinary licensing as suitable|Partner quote required; only reconsider with an expressly superseding negotiated license, not a routine subscription|
|Airbus OneAtlas — rural fallback research|Streaming/download APIs,30cm Pléiades Neo,50cm Pléiades and coarser products [A1]|Archive/date/cloud coverage varies;30cm does not preserve near-5cm roof-edge detail|Multiple licenses exist, but exact multi-tenant vector/storage/PDF rights need product-specific written confirmation [A2]|Subscription/pay-per-order; minimum AOI/orders may be inefficient per property; no applicable SaaS quote|

The two immediate alternatives are Eagleview and Hexagon: Eagleview for documented high-resolution imagery-only APIs and Canada/U.S. programs; Hexagon for broad U.S. ortho availability and an established derived-product licensing discussion. This is a follow-up ranking, not an assertion either will approve or be affordable. Hexagon's standard consumer/store license does NOT grant these rights. Vexcel's explicit vector prohibition makes it a weaker first licensing lead despite technical quality.

Commercial coverage does not mean every rural property is covered at suitable resolution. Any eventual government/open-data supplement requires its own license, source attribution, capture/accuracy review and endpoint availability tests. No open or commercial fallback was declared universally suitable.

## 6. Recommended next step and stop point

First obtain a written Nearmap rights-and-price proposal addressing the13 questions, ideally with an imagery-only OEM/SaaS addendum and explicit retained-measurement/customer-PDF survival clauses. Ask for address-level coverage metadata/sample imagery under an approved evaluation scope. Request comparable terms from Eagleview and Hexagon ONLY after Sean authorizes vendor contact; none sent today.

Decision order: (1) contractual rights; (2) native quality/coverage at target properties; (3) all-in cost at full usage and early subscriber minimums; (4) approved isolated prototype. Do not pay for or build a replacement before the first three gates. Do not launch the current Google-derived workflow on an assumption that attribution, manual tracing or an image-free PDF resolves the reported restriction.

Most AeriQuote code is reusable; no rewrite of measuring/pricing/account/PDF engines is justified by this research. Historical Google-based records remain a separate licensing question; Nearmap cannot retroactively license Google imagery or derived records. Preserve them without migration/deletion/repricing until an approved retention/remediation plan exists.

Still unverified: binding Nearmap/alternative rights and quotations; authenticated location-by-location imagery; actual payload costs/CORS/export quality; commercial-launch geography; post-termination retention; future Solar/AutoMeasure commercial permission. Existing Area physical-iPhone retest, Remeasure Area evaluation, Canadian region selector simplification and Linear/manual-roof safeguards remain recorded in the October28 resume. No work on them in this batch. STOP after report; no implementation authorized.

## Official sources (retrieved October29,2026)

- N1 Nearmap MSA, current-from-February2026, clauses1.4,2.1–2.5,6.4,15.8–15.9: https://www.nearmap.com/legal/master-subscription-agreement (some requests redirect to /au/legal/master-subscription-agreement; the MSA identifies Nearmap US as contracting entity for Canadian/U.S. customers; obtain the applicable signed version).
- N2 Tile API: https://developer.nearmap.com/reference/tiles
- N3 Coverage API: https://developer.nearmap.com/reference/coverage
- N4 Staticmap v3 image reference: https://developer.nearmap.com/reference/get_surveys-surveyid-type-format-1
- N5 Transactional Content API: https://developer.nearmap.com/docs/transactional-content-api
- N6 Separate DSM/True Ortho v2: https://developer.nearmap.com/reference/dsm-and-true-ortho-api-1
- N7 Content/accuracy guide: https://help.nearmap.com/kb/articles/1930-getting-started-with-nearmap-content
- N8 Current/future coverage: https://www.nearmap.com/coverage
- N9 Usage models: https://help.nearmap.com/kb/articles/1802-account-data-usage-classic-vs-current
- N10 API daily rate: https://help.nearmap.com/kb/articles/1731-current-view-api-usage
- N11 Product-specific terms, Transactional Content: https://www.nearmap.com/legal/product-specific-terms
- E1 Eagleview Imagery API components: https://www.eagleview.com/blog/developer-demo-see-the-imagery-api-in-action/
- E2 Eagleview platform, coverage/resolution: https://www.eagleview.com/blog/developer-overview-the-geospatial-building-blocks-of-eagleviews-imagery-platform/
- E3 Developer index: https://developer.eagleview.com/llms.txt ; WMTS licensed access: https://developer.eagleview.com/documentation/wmts/v2/overview
- H1 Current technical FAQ: https://docs.hxgncontent.com/hxgn-content-program-resources/Latest-version/frequently-asked-questions
- H2 EUAA currently linked by FAQ (V20240101), sections2,7,13: https://bynder.hexagon.com/m/6ddf50a65e636e4f/original/End-User-Access-Agreement-HxGN-Content-Program.pdf
- H3 Derived products/streaming overview: https://hxgncontent.com/en/about/organisation
- V1 API v2 service examples: https://vexcel.atlassian.net/wiki/spaces/APIDOCS/pages/3482288435/ArcGIS+Pro+Adding+Vexcel+WMTS+XYZ+Services+API+2.0 ; current API version: https://api.vexcelgroup.com/v2/
- V2 Canada: https://vexceldata.com/au/countries/canada/
- V3 September2025 EULA: https://vexceldata.com/eula/
- A1 Airbus API products: https://geoapi-airbusds.com/getting-started/apis-overview/
- A2 Airbus license options: https://space-solutions.airbus.com/legal/licences/

Some interactive developer pages/standalone pricing URLs were not retrievable through search. Usable official API references, indexed official documentation and source code underpin this report; inaccessible pages are not treated as verified evidence. No third-party pricing estimate was promoted to a vendor quote.
