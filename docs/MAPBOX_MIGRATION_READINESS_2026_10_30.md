# AeriQuote — Mapbox migration readiness and launch plan
October30,2026, America/Edmonton. Research, code inspection and planning only. No implementation approved by this document.

## Decision
**A provider migration appears technically practical without rebuilding the measurement engine or changing subscription prices. It is not ready for implementation or commercial launch approval.** First obtain an executable rights/pricing proposal and current property-level evaluation imagery. Preserve existing Google and Solar code until a separately approved, reversible adapter is tested.

New information is Sean's report of a Mapbox sales response: enterprise packages starting around$25,000 annually may support commercial multi-tenant use, customer aerial PDFs and redistribution. We have not independently authenticated the email, reviewed an Order or received a signed licence. This is a credible procurement lead, not granted rights. Currency, final minimum, includedAPI drawdown, permanent derived storage, historical retention and exact coverage remain unverified. Existing standard-terms concerns are not waived by an indicative sales discussion.

## Verified baseline and regression evidence
- Recovery HEAD22360c196a72deed73440de913e83b96775be69e, tree8ccfc1d81ab78535f99b27878455b7b158cb7ddf.
- GitHub40968931671 validate SUCCESS. Recovery40968931670 SUCCESS: recovery job82steps, postgres_integrity14steps, all successful. Current workflow contains74 run commands including dependency/setup and repeated industry variants; do not equate commands to individual test cases.
- PostgreSQL service job runs real disposable postgres16 tests for concurrent failure/recovery, property acceptance, subscription renewals, password reset/login lifecycle and cross-role signup identity races. This is CI evidence, not destructive testing of Render/customer data.
- Render test dep-dbhsrj60tbcc73agrf30 LIVE exactHEAD. No manual deployment.
- app.py unchanged blob e35719018a15c456d87de84e5004915790f9065b,5,052lines; inspected via GitHub, not stale local checkout.
- Read latest general and account-security resumes, Mapbox audit/quality comparison and QA_PRELAUNCH_2026_10_27.md. Inspected property_sessions.py,saved_estimate_edit.py,measurement_integrity.py,pricing_integrity.py,account_credits.py,render.yaml and workflows.
- Branch protection absent; no administrative settings changed. Main baselinec049a04b2ac5cc4df3d5c253fe9ca12f1d85806a remains outside work scope.
- No newly confirmed application defect in this inspection. No app tests/browser/physical-device tests newly executed; existing successful CI verified.

Detailed inventory: [MAPBOX_PROVIDER_DEPENDENCIES_2026_10_30.md](MAPBOX_PROVIDER_DEPENDENCIES_2026_10_30.md).
Earlier legal/cost basis: [MAPBOX_IMAGERY_AUDIT_2026_10_29.md](MAPBOX_IMAGERY_AUDIT_2026_10_29.md).
Actual access limitations: [MAPBOX_QUALITY_COMPARISON_2026_10_29.md](MAPBOX_QUALITY_COMPARISON_2026_10_29.md).

## What can remain
Retain Leaflet, latitude/longitude geometry, local Area/Linear arithmetic, manual roof planes and confirmed pitches, duplicate/self-crossing/overlap safeguards, per-area rates, discounts/taxes/seasonal periods, customer/company branding, authentication, employee permissions, business isolation, idempotent saves/revisions and monthly allowances.
Retain approved Single/Expanded designs and QA-only Vector exporter. Retain AutoMeasure source and internal automatic modes; no global rename. Keep manual Roofing double-gated until separately approved for launch. Keep AITrace removed.

## What must change later
Imagery loading and camera metadata, nine-image mosaic/detail paths, direct Google fallback URLs, report backgrounds with baked outlines, historical report rebuild and editing-session's Google-key dependency need an adapter. property_sessions.py currently restores a Google key into provider-specific URLs/modes. Historical aerials regenerate from fresh Google requests while Street View bytes can be saved in payloads.

Mapbox Satellite supplies imagery, not Google Street View or verified Solar roof geometry/pitch. Remaining geocoding and Street View require separate permission/provider decisions. /rgb legacy surface_static fallback can still invoke Solar Insights/Data Layers; it must not be reachable as a hidden recovery path in a future Mapbox manual mode. A Mapbox enterprise licence does not authorize old Google imagery or general Solar roofing.

## Smallest safe provider adapter — proposed contract
Use a thin background/camera layer behind current measurement tools, not a new editor.
1. A normalized property identity holds confirmed coordinates/address separately from image centre; different source centring never moves saved geometry.
2. A provider background result describes actual bounds, CRS(WebMercator), logical size, decoded physical dimensions/pixel ratio, camera centre/zoom/bearing, attribution, provider/source/version/date if available, coverage status and permitted retention. No API token in saved payload.
3. Keep current public route behavior through internal adapters where possible. A licensed static-background backend can first preserve the existing image-overlay lifecycle, including staging, while Raster Tiles can supply the interactive Leaflet background after tile-completeness checks. Do not add both a9-static mosaic and redundant XYZ loads to every property.
4. Background and overlays remain separate internally, with a shared verified projection. Compose exact saved geometry onto a licensed static photograph for reports; preserve the currently approved final image/PDF design. No coordinate simplification to fit provider URL limits.
5. Route every initial/detail/exact-pin/report/reopen image through the selected provider, including errors. No silent cross-provider fallback. Reject incomplete, blank, invalid-content-type or undecodable responses and explicitly unavailable coverage.
6. Keep current two-phase prepare/decode/accept sequence, stale-response guards and exactly-once business-scoped acceptance. Do not clear old measurements/customer/pricing while replacement imagery is pending. Provider retries do not create a new allowance operation.
7. Feature flag scoped to explicit disposableQA businesses only, default existing provider. Rollback restores routing, never rewrites geometry/history. No paying-customer enabling without new approval.

Any new saved provider-provenance fields or retention migration constitute saved-data changes: report exact risks and obtain approval before implementation. Old versions remain immutable; do not infer source/date metadata retrospectively, silently swap the historical photograph, delete records or reprice.

## Alignment and display acceptance
- Distinguish [lat,lng] Leaflet arrays from [lng,lat] GeoJSON/provider input. Test pin confirmation, ambiguous/reversed coordinates, high latitude/extent limits.
- Keep canonical saved points independent of viewport; Area/Linear/pitch quantities must be invariant under map pan/zoom/image replacement.
- Current staticMapBounds uses256×2^zoom and640logical pixels; existing scale2 responses are1280pixels. Raster Tiles@2x increases pixel density with the same tile footprint. Style-rendered512tile conventions are a different issue. Do not apply one universal zoomOffset.
- Prefer explicit geographic bbox and validated returned view metadata for Static Images; test centre/corner projections rather than copy Googlezoom integers. Keep bearing/perspective zero; camera pitch is not roof pitch.
- Provider-native resolution differs from screen pixels and maxzoom. No upsampling marketed as roof-level detail. Require declared useful source detail, complete visible boundaries and independently checked control points; never infer missing garage/roof sections.
- PDFs must use the exact approved camera plus saved geometry. Validate corners/centroids against independent projection; pin visual error tolerance in source pixels during pilot, then separately assess ground accuracy. Pixel alignment alone is not field accuracy.
- Preserve image proportions, circles, labels/dimensions, company/customer data and taxes at320/390/768/1440px. Wait for source decode, fonts and canvas-safe CORS; block/report failed image output or obtain explicit approved no-image choice. Do not claim a missing background is a successful aerial estimate.

Official technical references (previously read October29):
https://docs.mapbox.com/api/maps/raster-tiles/
https://docs.mapbox.com/api/maps/static-images/
https://docs.mapbox.com/help/glossary/zoom-level/
Static Images' documented1280base dimensions/@2x,URL limits and supported styles need validation in the proposed contract/pilot. Do not assume Mapbox Standard Satellite is supported by Static Images.
October30 web refresh attempts returned tool errors. No new pricing/documentation change is claimed; this plan uses the retrieved October29 official snapshot and flags revalidation before implementation.

## API and operational controls
Retain debouncing/cancel/sequence guards; instrument actual requests by action/provider/outcome without customer identifiers or credentials in logs. Deduplicate identical in-flight renders within rights; cap retries/backoff for429/5xx; keep obsolete responses from replacing current property. Alert on budget/coverage failures instead of lowering resolution or changing monthly allowances.

Use one platform usage meter rather than imaginary free tiers per business. Retain needed retina/native resolution. Only browser caching/retention expressly allowed by signed terms; no unapproved server tile warehouse or snapshot archive. Maintain separate provider-request counts and customer allowance accounting. Failed properties must not charge customer allowances; vendor request charges may still accrue. No API keys created, no caching changes now.

## Phased plan and effort
Engineering estimates, not commitments; exclude vendor response time, contract review and sample acquisition. One engineer, no parallel staffing assumed.
| Phase | Scope and gate | Effort |
|---|---|---|
|0 — rights and evidence|Confirm signed rights/evaluation permission, quote, budgets and actual regional imagery. Resolve GoogleStreet View/historical records separately.|External lead time unknown|
|1 — adapter contract and fixtures|Freeze current source baseline; define normalizedcamera/provenance, failure contract, rollback and test fixtures. Approve any persistence change before coding.|2–3 engineer-days|
|2 — isolated interactive adapter|QAflag; staged property images/tiles, detail refresh, exact pin, no cross-provider/Solar fallback, same allowance receipts.|4–6days|
|3 — report and compatibility paths|Manual/exact-pin/historical static renderer, savedediting, attribution+CORS, identical approvedPDFlayouts. Legal retention decision precedes any provenance migration.|3–5days|
|4 — regression and real-device acceptance|Six-industry workflows, live-authorized samples, independentgeometry/pricing, actualPDFvisuals, devices, security+PostgresCI, cost telemetry.|4–7days|
|5 — staged release decision|Owner review of contract, errors/costs/coverage, rollback rehearsal; production requires separate approval.|1–2days|
Total14–23 engineer-days, roughly3–5 working weeks after prerequisites. A limited pilot could finish sooner; no promised launch date. Do not implement Phase1 code until approved.

## Required test matrix
- Six industries × Area/Linear combinations, tiny/narrow/irregular/multiple areas, edit/delete/Cancel/repeat/reopen. Roofing main+garage, every pitch confirmed, incomplete/overlap/duplicate cases fail closed.
- Independent WGS84/GeographicLib distances/areas and Decimal pricing/tax/includedtax/discount/seasonal totals; compare snapshots before/after provider/viewport actions.
- Network interruption, partial/blanktiles, stale callbacks, imagery timeout, no coverage, invalidcoordinates, expired auth, account switching, duplicateaccept/save and parallel employee requests. Preserve original workspace and exact business receipts.
- Solar/Google aerial network spies assert zero calls in Mapbox mode through retry, garageadd, manualcorrection, historyreopen andPDF. Preserve automatic feature's code/tests outside that mode.
- Saved current/legacy snapshots/version conflict, no re-geocoding/no deductions on reopen, no Street View substitution or stale branding. Never touch real accounts.
- Single/Expanded actualPDFdownloads for all six at320/390/768/1440; independent measurement/pricing and rendered page comparisons; landscape+portraitStreet View and long customer data. VectorQA unaffected.
- Physical iPhone plus Android/tablet when available: repeatedArea1/Area2/Linear/roof edit→Save→edit,Cancel,drag/pinch,keyboard/orientation and nativePDFdownload. Emulation results separately labelled.
- Full current regression plus disposablePostgres service tests, actual authorized provider samples and QA business isolation; migration test evidence cannot be replaced by synthetic grids.
- Compare action-level API counts to baseline60raster/1.8static assumptions; heavy120/3 case and retries; measure legitimate cache hits only.

## Updated launch-blocker checklist
| Priority/category | Evidence/status | Release criterion |
|---|---|---|
|P0 — commercial imagery rights|Unsigned sales lead; standard terms insufficient|Executed Order covers all six industries, multi-tenanttracing, permanent derived geometry, satellitePDF/customerforwarding, caching/retention and historical/posttermrights; finalcurrency/fees known|
|P0 — source quality/coverage|Exact requestedMapboxproperties remain unverified|AuthorizedSaskatoon2addresses,Calgary,Edmonton,Warman,ruralSK,USsamples; native GSD/date/type/positional evidence, boundaryvisibility and complete-property checks|
|P0 — provider migration|Not implemented/tested|Approved isolated adapter passes all paths with no inadvertentGoogle / Solar fallback; rollback ready|
|P0 — roofing launch configuration|ManualRoofQA-only; AutoMeasure preserved; independentrealrooftruth unresolved|Explicit approvedcommercial launch configuration; confirmedpitches+completeoutlines and insufficient-coverage quote blocks; Solar rights resolved if ever enabled|
|P0 — billing for paid launch|Stripe absent; account-created anchors provisional|Separately approved billing/webhook lifecycle, trustedperiod boundaries,idempotency/paymentfailure/cancel/reactivate tests; do not rewriteusage now|
|P0 — physical measurement interaction|Sean reportediPhone second-edit failures; fixes automated,touch-emulated; latestphysical retest pending|PhysicaliPhone repeatedArea1/Area2/Linear/RoofSaveCancel pass; no map drag/missedcorner or silentinvalidgeometry; Android/tablet verification scoped|
|P1 — security/account acceptance|CurrentCIincludingPostgres passes; isolatedliveemployee/newbusiness lifecycle and resetemail not fully verified|Disposableowner/employee andcrossbusinesslivechecks; separateverifiedQAmailbox for actualResendreset delivery; never resetexistingSeanaccount|
|P1 — PDF acceptance on new provider|Current approvedPDFtests/historyevidence; noMapboxPDFs|ActualSingle/Expanded at all widths and industries; proportions,overlays,branding,taxes and savedquote match; providerattribution|
|P1 — release governance|Recoverybranch unprotected|Owner-approved rules/requiredchecks and test/production separation verified; noadminchanges here|
|P1 — historicalrecords|Prior inconsistentCommercial record export blocked; oldGooglephotographs/Street View rights unresolved|Keepguard,immutableprices; intentionalownerreview/newversion or separatelyapproveddata/legalplan|
|Risk decision — unsaveddrafts|Crash/discardloses unsavedmemory; beforeunloadwarning exists|Honest save/recovery wording and useracceptance. Autosave NOT automaticallyrequired; any persistence design needs separateapproval for privacy/stale/duplicate/accounting risks|
|Usability follow-up|Canadianregion selector cumbersome; RemeasureArea primary-option evaluation pending|Small separatelyapprovedscope; preserveoriginalmeasurement/rate andhistoricaltaxes. Not a reason to addnewtools/CRM|
|Optional polish|Dense labels/advancedroof-plan features|Not a launch prerequisite; noPDFredesign/architecturalfeature work|

No new launch defect was reproduced during this planning batch. This table separates known limits, verification gaps and optional improvements; greenCI does not establish commercial rights or physical-device accuracy.

## Financial sensitivity — hypothetical commitment
Assume plans and commitment in **USD** solely for comparison. Quotedcurrency not confirmed. Price/user mix:62%Basic29/25 at80%,30%Pro59/75 at75%,8%Business99/200 at65%. Weightedmonthlyrevenue43.60; expected39.675completedproperties/subscriber, full54. Complimentary/trial accounts generate usage but no subscriptionrevenue and are excluded: add them before a realbudget.
The$25,000 annual commitment amortizes to2,083.333/month; actual cash may be annualupfront, not monthlyfinancing. No signedminimum/paymentterms verified.

| Subscribers | Monthly revenue | Annual revenue | Expected jobs/month | Full jobs/month | Annual licence / revenue |
|---:|---:|---:|---:|---:|---:|
|100|$4360.00|$52320.00|3,967.5|5400|47.78%|
|250|$10900.00|$130800.00|9,918.75|13500|19.11%|
|500|$21800.00|$261600.00|19,837.5|27000|9.56%|
|1000|$43600.00|$523200.00|39,675|54000|4.78%|

October29 API model:60raster+1.8static/job includespan/zoom/retries/reopen / re-export assumptions; not telemetry. Sharedfreeallowances and marginaltiers applied. No freshOctober30publishedrateverification due retrievalerrors. OtherGooglecalls/geocoding, hosting/storage, PDFcompute, support, taxes/paymentfees, marketing/refunds/development excluded.

| Subscribers | Expected API only | Full API only | Fee + expected API | Fee + full API | Full fee + API / revenue |
|---:|---:|---:|---:|---:|---:|
|100|$0.00|$0.00|$2083.33|$2083.33|47.78%|
|250|$0.00|$15.00|$2083.33|$2098.33|19.25%|
|500|$110.06|$217.50|$2193.40|$2300.83|10.55%|
|1000|$410.02|$607.70|$2493.35|$2691.03|6.17%|

**Do not double-count a bundled package.** Three distinct contract scenarios:
A. Conservativeunbundledsensitivity:25k plus all public API usage as above, not a claimedvendorinvoice.
B. If package contains annual API creditK, add only max(0,annualeligibleusage−K)/12, with eligibility/discounts/rolloverto beconfirmed. IllustrativeK=5,000 (NOT a quote): at1,000subscribers totalmonthly fee + overage2,083.33 expected or2,274.37 full; at100/250/500 allmodelledAPIcovered.
C. If25k coversallmodelledeligibleusage with no overage, fee remains2,083.33/month. Not established; usagecaps/wholesalepricing and creditallocation may differ.
Currency, includedAPI credits, annualminimum, rights and taxes remain unverified until actualOrder.

Coverageoflicencealone:ceil(25000/(43.60×12)) = **48 full-year paying subscribers**. This ignores everyotherexpense, churn and startup timing. At48, annualgrossrevenue25,113.60 leaves only113.60 beforeeverythingelse. At10k/25k/50kfee,counterfactualfee-only thresholds20/48/96. Iflaunchramps from0 to100linearly, average50subscribers yields26,160annualgross, nearlyallconsumed byfee; endingyearwith100 is not equivalent to100all year.

Planningbudget tests, not guarantees:
- Fee+API below20%grossrevenue:239expected or240full-use subscribers.
- Below10%gross:504expected or535full-use subscribers.
- At100:47.78%licence burden is heavy. At250:roughly19% leaves room but viability depends onothercosts. At500:10–11%fee + API; at1,000:5.7–6.2%. Stronger scale economics do not prove profitability.
- Businessatfull200 costs3.36/month in marginalbaseAPI(firstpaidrates,nofreeallocation), but fixedlicence per business depends onplatformscale. At100mixedsubscribers, equallicenceallocation20.83/business plus3.36=24.19, about24.4%ofBusiness99. At500allocation4.17+3.36=7.53. Equalallocation is budgetingchoice, not vendorbilling.
- Modelquoteconversionfactorx into planrevenuecurrency:annualfee25000x. x=.75/1/1.35 givesfee-only thresholds36/48/65; hypotheticalexchange sensitivities, not currentFX.
- Need actual non-provideroperatingcosts plus realisticlaunchramp, trial/complimentaryusage, failedrequests and churn to approve a cashbudget.

JS model independently checked with PythonDecimal, including239/240 and504/535 thresholds. Rounding finalcurrencyHALF_UP; fractionaljobs are cohortexpectations. Rawmodel: [qa/mapbox-readiness-2026-10-30-financial.json](qa/mapbox-readiness-2026-10-30-financial.json).

## Outstanding Mapbox sales questions — not sent
1. Please supply the proposedOrder/license/rider for AeriQuote and confirm allsixindustries; whichCAL/CommercialSatellite/print/OEM provisions are included and which standard restrictions are expressly overridden?
2. Can contractors/businesses permanently retain independently createdpolygons,lines,pitches,quantities and estimates, including aftercontracttermination? Ownership and allowedexport formats?
3. Can downloadedcustomerPDFs include satellite/aerialbackgrounds+overlays, be forwarded/printed bycustomers and remain accessible indefinitely? Whatattribution,cache,backup andhistoricalsnapshot rules apply?
4. Is server-sideStatic Images/proxy/rendering/storage explicitly authorized? Does a newbackground source/date require notice when reopening historicalgeometry? Do upstreamVexcel/Vantor rights cover this?
5. Is25kUSDorCAD, exactannualminimum, paymentdueupfront, renewal/escalator, term/exitrights and any evaluation/pilot fee? Is it an estimate or formaloffer?
6. Exactpooled API creditvalue, wholesaleRaster/Static/Geocodingrates, free-tierinteraction, overage, seats/businesses, trial/complimentaryusage, cap/expiry/rollover andminimumusage?
7. Currentauthorizedpropertysamples at1715 2ndAveN/2301AveCN Saskatoon,1340SouthdaleCresSW Calgary,Edmonton,Warman,ruralSK andUS; source/native GSD/capturedate/orthoaccuracy/usefulzoom andmissingcoverage response?
8. DoesStatic Images matchRaster source/vintage? Can historicalversions be pinned/licensed? Availability/support/SLA and outage/backoff guidance?
9. WhatLeafletonboarding is included? ConfirmXYZ/@2x/camera/attribution integration expectations. Satellite does not supplyGoogleStreet View orSolarroofpitch; no such replacement is assumed.
10. What writtenevaluationpermission/access can we use beforecontract, without purchases or accidentalcommercialderivation?

## Stop and next authorization
Documentationonly. No integration, customeraccount/data, pricing/allowance, schema,PDFdesign, imageryresolution, Solar/AutoMeasurechange, vendorcontact orpurchase. No freshMapboximagerytest or signedrights claim.
Next action only afterSean's review: obtain contractual evidence and approved evaluationaccess, then separately authorize boundedadapterimplementation. Resume from newdocumentationcheckpoint, verifyHEAD/CI/Render first. Do not start coding as part of this task.
