# AeriQuote — low-cost imagery supply and regional partnership research
October29,2026, America/Edmonton. RESEARCH ONLY; stop for review.

## Decision

A regional open-data foundation plus selectively negotiated regional imagery is more plausible for AeriQuote's plans than buying roof reports or paying repeatedly for every property. It is not a verified nationwide solution. Start with an Edmonton2025 pilot and an Eastern Ontario DRAPE2024 pilot. Do not launch all six industries nationwide on this research: rural coverage, freshness and roof-edge quality remain gaps.

Verified starting recovery HEAD13e0fb60adfe3f89f750d5052c86c7bb76964299, treec8d10cd4c7e16c844392e3666b21fe4329091e6d. Both GitHub runs40915455129/40915455410 succeeded. Render test dep-dbhnigk9v7es73bk12i0 is LIVE for that commit. Read the existing general resume and IMAGERY_LAUNCH_FEASIBILITY_2026_10_29.md. No application code, integration, account or database was changed. Main/production were not modified; AI Trace remains removed. Documentation commits can trigger the existing recovery auto-deploy; no manual deployment requested.

## Evidence rules

“Open” below refers to named datasets expressly published under an open licence, not every image in a public viewer. Interpretation: a perpetual commercial copy/adapt/distribute grant supports manual tracing, retaining derived geometry and distributing annotated imagery PDFs, subject to attribution, exemptions and compliance. These specific AeriQuote actions are generally not individually named in the licence. “Negotiated” means no sufficient SaaS/storage/PDF grant was verified. A viewable endpoint, purchased tile or reseller relationship is not permission by itself.

Resolutions/capture dates are publisher metadata, not independent ground-truth accuracy or a completed visual property test. No real-property pixels were used to measure a roof in this batch. Public metadata and licence documents were inspected; providers were not contacted and imagery was not purchased. Contact channels are verified published channels, not tested email delivery.

## 1. Public-sector datasets and licensing

|Program / actual source|Verified imagery and capture|Coverage / roofing vs larger service areas|Rights classification and access|
|---|---|---|---|
|Geospatial Ontario DRAPE2024|16cm RGBN orthophotos, March12–May31,2024; stated45cm ground accuracy;35,993km² [O1]|Eastern Ontario project footprint, including rural areas within its index. Promising for parking/lawn/site boundaries; small roof facets, occluded edges and thin sidewalks need validation|Named release is OGL–Ontario. GeoTIFF/order transfer; public imagery services exist. No imagery royalty for named open data [O2,O3]|
|Ontario SCOOP2023 / SWOOP2020|SCOOP16cm, captures2023 plus April2024,43,692km²; SWOOP2020 16cm, March–May2020,44,828km² [O4,O5]|Regional collections, not uniform province-wide current16cm. Older captures can miss extensions/new sites|Both catalogue resources expressly OGL–Ontario. Do not apply that grant to unrelated third-party layers|
|Ontario newer releases|Catalogue lists SWOOP2025 for2026 release;2026 COOP metadata says20cm and April26–June4,2026 [O2,O6]|Availability of final tiles/services must be checked. A preliminary index is not proof all image bytes are delivered|Confirm final release, rights and tile metadata; not assumed better/current everywhere|
|City of Edmonton2025|7.5cm RGB, September–October2025; approximately286MB per GeoTIFF;32GB city ECW;NAD83/3TM114,EPSG3776 [E1]|City-owned coverage; strong roof-outline candidate, including garages, but tree/building lean and accuracy still need field checks. No extension to rural Alberta|Official City maps page directs aerial orthophotos to open data [E2]. Current portal-embedded OGL–Edmonton grants perpetual commercial copying/adaptation/distribution with attribution [E3]. Dataset API lacks an explicit licenseId; confirm any tile-level exceptions before pilot|
|City of Vancouver2022|7.5cm RGB, June6–July1,2022;NAD83/UTM10,EPSG26910 [V1]|City/UBC/UEL and specified nearby portions; not all Metro Vancouver. Fine native pixels, but four-year-old capture is a material launch limitation|Dataset explicitly OGL–Vancouver; commercial/perpetual copy/adapt/distribute terms verified [V2]. Download tiles and self-host; not a licence to all VanMap basemaps|
|Québec regional open orthophotos|Capitale-Nationale2023:20cm, spring2023, Portneuf plus part of Jacques-Cartier; GeoTIFF2km tiles/JP2. Province catalogue is CC-BY4.0 and combines vintages [Q1,Q2]|Useful additional regional service-area coverage; province-wide catalogue label does not establish uniform20cm availability|Named open collections are free download/CC-BY4.0. Credit creator/source/licence and indicate modifications; no added restrictions on licensed material [Q3]. Verify exact tile attribution and date|
|Saskatchewan ISC/SGIC|ISC product page:60cm imagery, stated3m positional accuracy, GeoTIFF/TIFF/JPG, township/section products. Original program began2008; current capture date varies [S1]|Broad Saskatchewan availability including rural does not imply roof-grade resolution.60cm/3m is a poor default for small roofs/sidewalks; only coarse service-area feasibility pending validation|NOT open for our full workflow. Official public ImageServer metadata prohibits further commercial redistribution [S2]. Purchased product has an EULA; tracing/vector permanence/PDF rights need written agreement|
|USDA NAIP / USGS distribution|2025 program roughly half states30cm, half60cm; older1–2m imagery also exists. Leaf-on; repeat cycle generally2–3years; metadata is tile-specific [U1]|Main program CONUS; do not promise every U.S. state/territory. Large visible fields/parking sites may be usable; small roof sections/curbs/trees are problematic. Not a like-for-like7.5cm substitute|USDA aerial orthophotography is public domain [U2]. Commercial tracing, retained geometry and PDFs are not copyright-restricted for those original public-domain assets. Credit USDA/source/date; do not inherit third-party basemap restrictions|

### Attribution, hosting, caching and persistence

For named Ontario/Edmonton/Vancouver open assets, the broad copying/distribution grants support retaining an original, generating tiled/COG derivatives, caching and self-hosting without a measured per-property royalty. This is a licence interpretation, not a promise of unlimited bandwidth from government servers. Keep source, acquisition date, licence version, transformation details and checksum with each ingested collection. Put appropriate attribution close to the imagery and in customer PDFs. Preserve historical capture identity; never regenerate a saved quote against “latest” imagery without making the change clear.

Required/default lines include:
- Ontario: Contains information licensed under the Open Government Licence–Ontario.
- Edmonton: Contains information licensed under the Open Government Licence–City of Edmonton.
- Vancouver: use the provider's specified credit/default OGL line and licence link.
- Québec: MRNF or named regional creator, dataset/capture date, CC-BY4.0 link and modification notice.
- NAIP: credit USDA FPAC-BC Geospatial Enterprise Operations and acquisition year; consult original tile metadata.

Open licences exclude third-party rights they cannot grant and do not imply endorsement or permission to use City/provincial logos. Historical retention remains subject to compliance; it does not authorize tracing an unrelated copyrighted Google layer. Open source imagery does not retrospectively clear existing Google-derived records.

Choose downloads from named licensed collections rather than screenshotting mixed government viewers. Edmonton specifically notes that imagery outside Edmonton in its map products can come from Esri [E2]. Ontario OIWMS is a published free public service with source-metadata companion [O7], but its mixed acquisitions must be inspected per source; the named download collection is the safer initial scope. None of the reviewed public endpoints establishes an AeriQuote production SLA. Ask before heavy bulk use; self-hosting limits dependence on availability/rate changes.

Costs: open dataset licence royalties are zero; special delivery/media, support or processing charges were not quoted. ISC's published retail references include$52/GeoTIFF section and$105/GeoTIFF township, with possible volume discounts [S1]. Currency/current applicability and OEM rights must be confirmed; these prices are not SaaS redistribution prices. Capture freshness cannot be inferred from the2026 website footer or original20%-per-year program wording.

### Edmonton licence retrieval note

The official portal page renders its licence as an embedded original document. Its served content was HTML, despite a generic attachment path; read the HTML text, not a failed PDF extraction. Verified commercial/perpetual and copy/adapt/distribute clauses. SHA256 of retrieved embedded document:44a89d997f8cee1719bba599a4392443bcda5850261f351d927ff4d78f87fe8d. Do not publish temporary signed asset URLs. Cite stable City licence portal [E3]. This is stronger evidence than relying on third-party licence mirrors or an old City Terms PDF.

## 2. Commercial regional/wholesale leads

**Tarin Resource Services (Western Canada):** actual annual regional VIEWS WMS and downloadable orthophoto discovery; published coverage map updated March14,2024 includes vintages through2023. It is an unusually relevant fixed-region distributor lead for Saskatchewan/Alberta, but source ownership, native GSD, current availability, pooling, cache and PDF rights are UNVERIFIED. Its SPOT offering is not automatically roof-grade. Ask for an imagery-only OEM regional contract, not an individual GIS seat. No public applicable OEM quote found. [T1,T2]

**First Base Solutions (Ontario plus listed Alberta holdings):** MapWarehouse bulk tiles and MapCast bandwidth subscriptions are established products. The2022 coverage PDF includes5–15cm regional examples and Toronto8cm; these are dated examples, not current universal coverage [F1]. An official help page publishes retail references of$70/500m tile,$150/1km tile and MapCast from$500/year for500MB/month [F2]; currency, age and applicability require confirmation. The actual standard MapWarehouse EULA is internal-business-only, forbids third-party distribution and requires prior written agreement for Internet placement [F3]. Therefore ordinary retail/MapCast access is NOT cleared for AeriQuote. Negotiate a superseding OEM licence, rights to annotations/permanent geometry/customer PDFs, and pooled bandwidth. A small advertised subscription is not a low-cost SaaS quote.

**McElhanney:** real orthophoto/LiDAR catalogue and digital-orthophoto acquisition/internet-hosting services [M1]. Ask to licence existing inventory over a bounded region and whether underlying client contracts permit sublicensing. Capture/GSD/cost and AeriQuote distribution rights are unverified. Custom flights should be a later, jointly funded regional option, not assumed affordable at1,000 jobs.

**NV5 Geospatial:** genuine aerial photogrammetry and custom3-inch ortho capability, plus public procurement frameworks [N1]. Useful for a future pooled county/municipal acquisition or U.S. regional gap, not evidence of a cheap off-the-shelf OEM library. Region, ownership, minimum acquisition and redistribution costs require quotation.

**Data for Canada / Source Cooperative:** already packages several municipal open orthophotos and Ontario DRAPE2024 as downloadable geospatial assets [D1]. Source Cooperative provides public data access and a published contact [D2]. This could reduce preparation effort, but does not create rights beyond original licences, guarantee data freshness or provide a commercial SLA. Verify source linkage/checksums; do not treat beta hosting as a permanent free production backend.

SGIC itself demonstrates pooled acquisition, while Ontario's catalogue describes earlier public/private cost-sharing and present government funding. These are partnership models to ask about, not open invitations or verified membership prices. Purchasing from a distributor cannot override an upstream vectorization/PDF restriction.

No reviewed wholesaler has confirmed one inexpensive, high-resolution Canada/U.S. multi-tenant licence. A sustainable initial geography may need to be narrower than national coverage. Do not silently substitute coarse imagery to claim all six industries are supported.

## 3. Ranked actionable shortlist — five initial channels

|Rank|Organization/program and verified contact|Why this rank / obstacle|Specific opening questions|
|---|---|---|---|
|1|Geospatial Ontario:imagery@ontario.ca;705-772-5891 [O8]|Broad named open regional releases;16cm is below premium urban detail|Which final DRAPE2024/SWOOP2025 tiles are available now? Any third-party exclusions? Best bulk download/delivery path, source-date layer, attribution and update notifications? Any delivery cost or limits?|
|2|City of Edmonton:opendata@edmonton.ca;mapdesk@edmonton.ca [E2,E4]|Recent7.5cm City data with recovered commercial OGL; confirm collection-specific exceptions|Confirm2025 orthophotos wholly under OGL–Edmonton, self-hosting/derived storage/customer annotated PDFs; identify any excluded external imagery. Get accuracy report, acquisition per tile, bulk manifest and update cadence/cost|
|3|Tarin:orderdesk@tarin.ca;403-269-8228 [T1]|Most relevant regional wholesale lead for SK/AB; no OEM rights/price verified|Quote pooled AeriQuote tenants for a bounded Saskatoon/Edmonton/Calgary region,5–15cm where available; source/date/coverage polygons; permanent vectors and distributed PDFs; self-host licence vs regional WMS, minimums and annual updates|
|4|First Base Solutions:sales@firstbasesolutions.com;905-477-3600 [F4]|Bulk catalogue, detailed imagery and bandwidth model; standard EULA blocks proposed use|Can a signed OEM addendum supersede internal-use/no-Internet/no-distribution terms? Fixed regional fee or pooled bandwidth without per-employee seats? Quote own imagery separately from third-party holdings; permanent vectors/PDF retention after termination|
|5|USDA FPAC-BC GEO:geo.sales@usda.gov;USGS EROS custserv@usgs.gov /1-800-252-4547 [U1,U3]|Public-domain broad U.S. service-area foundation; inadequate as universal small-roof solution|Which30cm counties/vintages and bulk original assets are available? Any original-tile restrictions, cloud/leaf-on issues and release dates? Is regional higher-resolution partner data separately licensed? Confirm cost for special delivery, not imagery royalties|

Useful secondary channels: Vancouver's official open-data contact form [V3]; Québec geoboutique@mrnf.gouv.qc.ca [Q2]; ISC1-866-275-4721 [S1]; McElhanney Vancouver vancouver@mcelhanney.com /604-683-8521 [M2]; Source Cooperative hello@source.coop [D2]. None contacted.

## 4. All-in aerial supply model

### Scope and assumptions

All model amounts are USD before tax/FX. Confirm AeriQuote subscription billing currency. These are hypothetical planning cases, NOT supplier quotations or measured traffic. Volumes count successful annual property-measurement workflows within the licensed/usable region, not monthly subscribers. Do not divide one city's licence by national traffic outside it.

Bounded pilot corpus:500GB TOTAL including originals/processed/archive versions, not500GB per copy. It is NOT all of Ontario/Canada/U.S. DRAPE's35,993km² at16cm/4bands is about5.62TB uncompressed before overviews; use selected tiles. Each additional region, vintage, backup copy or resolution can increase cost.

Published Cloudflare R2 Standard pricing:$0.015/GB-month,$4.50/million writes,$0.36/million reads, direct egress free; other metered services may charge [C1]. No deployment or purchase made. Model conservatively ignores free tiers:
-500GB storage:$90/year.
-Worker/CDN delivery service reserve:$60/year; monitoring/backup operations reserve:$60/year.
-Annual refresh/checking labour:12h×$50=$600; processing compute reserve:$100/year.
-Recurring fixed open-data operations:$910/year.
-Initial regional ingestion/metadata QA:24h×$50=$1,200.
-Common future adapter/integration/acceptance reserve:120h×$50=$6,000 ONCE. This is hypothetical budgeting, not a scoped development commitment; include it to avoid pretending engineering is free.
-Variable render/request/operations contingency:$0.01/workflow. Assumed50MB traffic and roughly120 requests/workflow; at50,000 jobs that's2.5TB/year and6m requests. Not benchmarked. A whole-image proxy/expensive on-demand warp can cost more.
-Commercial fixed-region example:ADDITIONAL$3,000/year licence on the same self-hosted package; this number is invented for sensitivity analysis.
-Commercial transaction examples:$0.10 or$0.25 per charged transaction,1.5 billable transactions per completed workflow for retries/reopens, vendor hosting/export included by assumption, plus$360/year API administration. Same$7,200 initial integration/QA reserve; no minimum spend assumed.

Underlying commercial units must include pan/zoom, PDF export, survey changes, expired reuse windows and failed retries. If billed per tile/MB/property, convert to completed-workflow cost. Measurement allowances must not be changed to hide vendor charges. A fixed fee can be additive or a minimum floor; don't count it both ways.

### First-year total, including engineering reserve

|Model|1,000/year|10,000/year|50,000/year|
|---|---:|---:|---:|
|Open/self-hosted:$8,110 +$0.01N|$8,120 ($8.120/job)|$8,210 ($0.821)|$8,610 ($0.1722)|
|Hypothetical$3,000 fixed licence:$11,110 +$0.01N|$11,120 ($11.120)|$11,210 ($1.121)|$11,610 ($0.2322)|
|Hypothetical$0.10 transaction:$7,560 +$0.15N|$7,710 ($7.710)|$9,060 ($0.906)|$15,060 ($0.3012)|
|Hypothetical$0.25 transaction:$7,560 +$0.375N|$7,935 ($7.935)|$11,310 ($1.131)|$26,310 ($0.5262)|

### Ongoing annual supply costs after initial integration/ingestion

|Model|1,000/year|10,000/year|50,000/year|
|---|---:|---:|---:|
|Open/self-hosted|$920 ($0.920/job)|$1,010 ($0.101)|$1,410 ($0.0282)|
|Hypothetical$3,000 fixed licence|$3,920 ($3.920)|$4,010 ($0.401)|$4,410 ($0.0882)|
|Hypothetical$0.10 transaction|$510 ($0.510)|$1,860 ($0.186)|$7,860 ($0.1572)|
|Hypothetical$0.25 transaction|$735 ($0.735)|$4,110 ($0.411)|$19,110 ($0.3822)|

This is aerial supply, not total SaaS profitability: excludes general app hosting/support/payment/refund/sales costs and any separately retained geocoding/Street View bills. No licensing for Street View/Solar is resolved by open orthophotos.

With initial$7,200 spread over three years, open annualized cost becomes$3,310+$0.01N, or$3,320/$3,410/$3,810 at these volumes. At50,000 that's$0.0762/job, materially different from the2.82-cent steady-state figure.

### Break-even and gaps

For equal usable coverage/quality, transaction multiplier1.5 and the assumptions above:

|Vendor price per transaction|Open cheaper above approximately|$3,000 fixed licence cheaper above approximately|
|---|---:|---:|
|$0.05|8,462 jobs/year|54,616 jobs/year|
|$0.10|3,929|25,358|
|$0.25|1,507|9,727|
|$0.50|744|4,798|

Formula:open crossover=550/(1.5c−0.01); fixed-licence crossover=3,550/(1.5c−0.01), rounded up. Initial integration reserve cancels because equal across examples. These are algebraic sensitivity results, not evidence comparable licences are available. Low volume can favor transactions even when open data has zero royalties, because operations labour still costs money.

If20% of jobs cannot use open imagery and need a hypothetical$0.25 transaction with multiplier1.5, variable cost becomes0.8×$0.01+0.2×1.5×$0.25=$0.083/job. Ongoing totals:$993/$1,740/$5,060; first year:$8,193/$8,940/$12,260. At50,000, steady-state cost rises from2.82c to10.12c. “Gap” includes imagery too old/coarse/occluded, not just blank map coverage. A hypothetical$1 or$5 fallback is substantially worse; no fallback means the job must not be quoted from inadequate imagery.

Plan context at full monthly use, assuming USD and a hypothetical20% aerial budget:Basic$0.232/job,Pro$0.1573,Business$0.099. These are budget ceilings, not actual profit margins. The$3,000 fixed example fits Business's20% envelope at50,000 ongoing regional jobs but not at10,000. Open data can support the plans at density/scale; it is not cost-free at launch. Retain high-utilization stress tests and startup cash requirements.

## 5. Two recommended pilots — proposals only

**Pilot A: Edmonton City2025, a small verified City-owned subset.** Fresh September–October2025,7.5cm data and commercial OGL make it the best initial manual-roof/service-area candidate. Licence acquisition budget$0; ingestion/hosting/QA still cost money. Exclude Esri/out-of-city imagery. Confirm dataset-specific exceptions with City staff before implementation; verify actual pixels, positional accuracy and all needed buildings before any customer use.

**Pilot B: Eastern Ontario DRAPE2024, a bounded urban-to-rural corridor inside final released tile coverage (for example Ottawa/Carleton Place, subject to index confirmation).**16cm leaf-off imagery and an explicit OGL release offer useful rural/commercial-lot testing without pay-per-property royalties. Prioritize Snow/Landscaping/Paving/Commercial large surfaces; treat Roofing/Pressure Washing narrow details as conditional until measured against ground truth. Use named downloadable tiles, not a mixed province-wide mosaic. Newer SWOOP2025 can follow once final availability/metadata are confirmed.

Vancouver2022 is a credible high-resolution backup pilot but older; Saskatchewan SGIC is not an acceptable roof-quality/open-redistribution substitute today. Tarin is the practical local negotiation lead, not a verified remedy.

For both pilots, later approval must precede code/integration changes. First inspect actual samples:roof edges/garages, overhang/building lean, vehicles/trees, snow/shadows, narrow curbs and new construction. Compare surveyed/field distances/areas independently; no metre-per-pixel number guarantees roof accuracy or pitch. Retain contractor pitch confirmation and incomplete/overlap guards. Test source reprojection/bounds, saved reopen with the SAME survey, attribution and real Single/Expanded PDFs without changing approved design. Keep the original job and prevent quotes where imagery is inadequate.

A future supply catalogue can identify geographic footprint/date/nativeGSD/licence/attribution and explicit no-coverage outcomes while existing measurement/account/pricing engines remain intact. This is planning, not an approved new feature or storage migration. Do not shift saved vertices when changing imagery, and do not repair historical Google licensing by relabelling those records.

## 6. Stop point

Next decision:review these findings and approve a small sample/rights-confirmation phase or supplier outreach. Obtain a signed OEM agreement before using negotiated imagery. No contact, purchase, new account, application change or integration performed. No new browser/PDF/physical-device verification claimed. Existing code tests were not rerun just for documentation; starting CI/Render success was verified directly.

The current Google workflow remains uncleared following Sean's MapsPeople correspondence. Preserve all existing functionality/checkpoints, Linear touch and manual Roofing protections, QA-only Vector/manual features and removed AI Trace. No autosave/schema/allowance/pricing/PDF changes. Stop after research checkpoint.

## Official source links

O1 DRAPE2024 resolution/date/licence:https://data.ontario.ca/dataset/open-ontario-imagery/resource/84111458-d36a-4e0a-b10e-cb9bf18880c8
O2 Ontario open imagery programme/releases:https://data.ontario.ca/dataset/open-ontario-imagery
O3 OGL–Ontario:https://www.ontario.ca/page/open-government-licence-ontario
O4 SCOOP2023:https://data.ontario.ca/dataset/open-ontario-imagery/resource/7a637818-08d9-4951-936e-c1adb0d858e1
O5 SWOOP2020:https://data.ontario.ca/en/dataset/open-ontario-imagery/resource/106b788e-7d26-413b-a787-68b0515ba79d
O6 COOP2026 metadata:https://www.arcgis.com/sharing/rest/content/items/642bf56e4f1441f397d1ef3012275321/info/metadata/metadata.xml?format=default&output=html
O7 OIWMS public services/source information:https://www.arcgis.com/home/item.html?id=101295c5d3424045917bdd476f322c02
O8 Ontario official service contact metadata:https://www.arcgis.com/sharing/rest/content/items/101295c5d3424045917bdd476f322c02/info/metadata/metadata.xml?format=default&output=html

E1 Edmonton2025:https://data.edmonton.ca/dataset/Orthophoto-Repository-2025-Map/3r8m-cnxp ; machine metadata:https://data.edmonton.ca/api/views/3r8m-cnxp.json
E2 City imagery provenance/contact:https://www.edmonton.ca/business_economy/maps-and-aerial-products
E3 Current OGL portal/embedded document:https://data.edmonton.ca/stories/s/Open-Government-Licence-Edmonton/msh8-if28/
E4 City open data/contact:https://www.edmonton.ca/city_government/initiatives_innovation/open-data

V1 Vancouver named collection:https://opendata.vancouver.ca/explore/dataset/orthophoto-imagery-2022/
V2 Official licence:https://vancouver.opendatasoft.com/pages/licence/ ; City programme:https://vancouver.ca/your-government/data-and-maps.aspx
V3 Official contact form:https://opendata.vancouver.ca/pages/contact/

Q1 Capitale-Nationale2023:https://www.donneesquebec.ca/recherche/dataset/orthophotographies-2023-region-de-la-capitale-nationale
Q2 Provincial imagery/licence/contact:https://www.donneesquebec.ca/recherche/dataset/imagerie-orthorectifiee-du-quebec
Q3 CC-BY4.0:https://creativecommons.org/licenses/by/4.0/

S1 ISC source/specifications/retail references:https://www.saskregistries.ca/MapsandPhotos/Imagery/SGICOrthoImagery
S2 Public SGIC service restrictions:https://gis.saskatchewan.ca/imagery/rest/services/SGIC_Public_Orthophotos/ImageServer/info/iteminfo?f=pjson

U1 Current NAIP metadata/resolution/contact:https://catalog.data.gov/dataset/national-agriculture-imagery-program-naip-imagery
U2 USDA public-domain statement:https://www.fpacbc.usda.gov/geospatial-services/customer-services
U3 USGS access/contact/technical context:https://www.usgs.gov/centers/eros/science/usgs-eros-archive-aerial-photography-national-agriculture-imagery-program-naip

T1 Tarin regional services/contact:https://www.tarin.ca/
T2 Actual dated coverage map:https://www.tarin.ca/s/OrthoCoverage_ByYear.pdf ; resources:https://www.tarin.ca/resources
F1 FBS published capture/GSD coverage:https://www.firstbasesolutions.com/wp-content/uploads/FBSOntarioOrthoSummary_2000-2022.pdf
F2 Official retail reference/help (not OEM quote):https://www.firstbasesolutions.com/MapCastHelp
F3 Actual EULA:https://maps.firstbasesolutions.com/legal.php
F4 Business-development contact:https://www.firstbasesolutions.com/contact/
F5 Bulk ordering/API/printing caveats:https://support.firstbasesolutions.com/faq/
M1 McElhanney orthophoto catalogue/services:https://www.mcelhanney.com/vertisee/ ; https://www.mcelhanney.com/services/geospatial/
M2 Official regional contact:https://www.mcelhanney.com/locations/vancouver-british-columbia/
N1 NV5 capture capabilities:https://www.nv5.com/geospatial/technology/orthoimagery/
D1 Data for Canada prepared datasets:https://source.coop/dataforcanada/d4c-datapkg-orthoimagery
D2 Source Cooperative access/governance/contact:https://docs.source.coop/
C1 Official hosting tariff:https://developers.cloudflare.com/r2/pricing/

Some official interactive pages return empty HTML/403/429 to the web reader; indexed official text was cross-checked with direct public metadata where possible. No bot wall was bypassed. Edmonton licence content was obtained from its publicly embedded original document. Source metadata/terms are not a substitute for a completed image-quality pilot.
