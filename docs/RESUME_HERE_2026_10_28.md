# October29,2026 — low-cost imagery supply research COMPLETE

STOP for review; no implementation, outreach or purchases authorized/performed.

Read [LOW_COST_IMAGERY_SUPPLY_2026_10_29.md](LOW_COST_IMAGERY_SUPPLY_2026_10_29.md) and the machine-readable assumptions/results at qa/imagery-sourcing-costs-2026-10-29.json. Prior Nearmap report remains intact.

Starting HEAD13e0fb60adfe3f89f750d5052c86c7bb76964299; GitHub40915455129/40915455410 success; Render test dep-dbhnigk9v7es73bk12i0 LIVE. Research commit changes documentation only. No application, database, customer account or production changes. Main untouched.

Key findings:
- Named Ontario OGL collections, Edmonton City OGL, Vancouver OGL, Québec CC-BY open collections and original USDA public-domain NAIP are legally distinct from merely viewable services. Broad commercial copy/adapt/distribute grants support tracing, retained geometry and PDFs subject to attribution/exemptions; named-source provenance matters.
- Edmonton's actual current portal-embedded OGL was recovered and read; perpetual commercial adaptation/distribution verified.2025 City orthophotos7.5cm, Sept–Oct2025. Dataset API licenseId absent; confirm any tile exceptions; exclude out-of-city Esri images.
- Ontario DRAPE2024:16cm,45cm stated accuracy,March–May2024,35,993km². Named release expressly OGL. Recommend bounded released urban/rural tiles, not mixed provincial basemap.
- SGIC public ImageServer explicitly prohibits further commercial redistribution. ISC60cm/3m product cannot be assumed roof-grade or SaaS-licensed from low retail prices. Negotiation required.
- NAIP2025 is30/60cm by state, leaf-on; genuinely public domain original assets but not universal roof-quality imagery.
- Tarin regional VIEWS and First Base Solutions bulk/MapCast are preferred wholesale inquiries. No applicable OEM price/rights verified. FBS actual EULA is internal-only/no distribution/no Internet without written agreement; ordinary subscription insufficient.
- Recommended pilots:Edmonton2025 and Eastern Ontario DRAPE2024, proposals only. Actual property-pixel/field accuracy testing NOT performed in this research.
- Hypothetical USD all-in model includes$6,000 shared initial integration+$1,200 regional ingestion,$910/year open-data operations,500GB total corpus and$0.01/job reserve. First-year open totals at1k/10k/50k jobs:$8,120/$8,210/$8,610; ongoing:$920/$1,010/$1,410. Not nationwide costs, measured usage or vendor quote. Fixed$3k and metered scenarios/break-even/gap costs in report.20% gaps can raise50k ongoing cost from2.82c to10.12c/job.
- Five ranked contacts:Geospatial Ontario,City Edmonton,Tarin,First Base Solutions,USDA/USGS. Contact details/questions in report. No vendor contacted.

Preserve existing Google/Mapbox/Leaflet/Solar integrations,AutoMeasure code,manual Roofing/Vector QA gates,measurements,prices,taxes,allowances,aerial PDFs and all checkpoints. AI Trace remains removed. Prior MapsPeople restriction remains launch blocker for current Google workflow; open imagery does not retroactively licence historical Google-derived content.

Next:Sean reviews scope/costs,then separately authorizes source samples/rights clarification or supplier outreach. No implementation started. October28 physical-iPhone Area retest,Remeasure Area evaluation,Canadian region filtering and Linear/manual-roof safeguards remain pending below.

---

# October 29, 2026 — imagery licensing research checkpoint

Research COMPLETE; STOP for review. No application implementation authorized by this batch.

Read [IMAGERY_LAUNCH_FEASIBILITY_2026_10_29.md](IMAGERY_LAUNCH_FEASIBILITY_2026_10_29.md) for the Nearmap meeting briefing, licensing questions, code-based feasibility analysis, cost scenarios and supplier comparison.

Verified starting recovery HEAD78dd1ffbc938157f2f2580f8c4cba77750a05543; both GitHub workflows40779768758/40779768938 succeeded, including postgres_integrity. Render test dep-dbh7cc5g1s2s73fij2r0 LIVE for that commit. Main read-only baseline unchanged c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a. The next documentation-only commit becomes the research checkpoint; application blob remains e35719018a15c456d87de84e5004915790f9065b.

Sean reports written MapsPeople confirmation that Google standard terms do not permit AeriQuote's commercial tracing, derived measurement storage and customer aerial-PDF workflow, with no enterprise exemption from MapsPeople. Original letter not independently retrieved. Do NOT assume current Google workflow is cleared for launch. Do NOT disable/change integrations on this finding without approval.

Nearmap is technically plausible with existing Leaflet/manual geometry/pitch/pricing/accounts/PDF engines retained, but all imagery/report/retry/reopen routes need a later approved adapter, including exceptional Solar and direct Google fallbacks. Nearmap imagery alone does not replace AutoMeasure geometry/pitch. Its standard MSA internal-use/output and termination restrictions require explicit SaaS, vector retention, customer redistribution and historical-survival contract rights. No vendor permission, quote, coverage-key test or integration has been obtained.

Cost planning only, assuming USD subscriptions and no fixed fee/reopen multiplier:20% revenue imagery budget at full25/75/200 use gives Basic0.232/Pro0.1573/Business0.099 USD per completed property.10% gives0.116/0.0787/0.0495.25/50/100% utilization, hypothetical0.05/0.10/0.25/0.50 unit prices and minimum-commitment scenarios in report. Exact profitability cannot be certified without vendor quotes and other costs. Nearmap tokens/vendor meters are NOT AeriQuote allowance credits.

Two preferred alternative follow-ups:Eagleview Imagery API and Hexagon HxGN Content Program. Rights/prices remain unconfirmed; standard Hexagon store agreement insufficient. Vexcel reserve has explicit published vectorization prohibition, so do not assume ordinary access permits tracing. Rural Canada and address-level image quality remain unverified for every candidate.

Next action:Sean reviews report; request explicit written Nearmap rights/pricing/coverage proposal and comparable Eagleview/Hexagon terms only after vendor-contact approval. No vendor contact, purchases, trials, application code, customer/database changes or manual deployment performed. Documentation may auto-deploy under existing branch settings. No new application tests were run because source code is unchanged; prior passing CI/PG was verified directly.

Preserve October28 priorities below:physical-iPhone Area retest; evaluate original-preserving Remeasure Area; Canadian province filtering without silent tax changes; existing Linear/manual-roof safeguards. Preserve AutoMeasure code, QA-only manual Roofing/Vector and removed AI Trace. No imagery/pricing/allowance/PDF redesign or changes. Historical Google-derived records need a separately approved licensing/retention plan; do not delete, shift, migrate or reprice.

---

# End-of-day checkpoint — October 28, 2026

STOPPED FOR TODAY. No further implementation authorized tonight.

All verified fixes through application checkpoint0e63ef48f4eb327e25e65b5296804a01c78e5e8c are committed on landscaping-multi-area-recovery-oct11. Recovery HEAD matched that checkpoint at end-of-day verification. Both GitHub runs40778997564 and40778997631 succeeded,including PostgreSQL integrity checks. Render test deployment dep-dbh79jfb9u1s73amtmfg is LIVE for that exact commit. Tracked working tree was clean before this documentation update. The end-of-day documentation-only commit becomes the final branch checkpoint;no application changes accompany it.

## Next priorities — planning only until work resumes

1. Verify the Area correction fix on Sean's physical iPhone,especially first edit/save followed by second edit of both Area1 and Area2. Check missed taps cannot append vertices,valid Save works,invalid Save stays blocked,and Cancel restores the exact originals. Browser touch emulation passed;physical confirmation remains pending.
2. Evaluate Remeasure Area as the PRIMARY correction option. Preserve the original saved geometry,quantity,rate and estimate until a complete valid replacement is explicitly confirmed. Plan safe Cancel/failure handling and multiple-area isolation before implementing. Do not delete the original when replacement starts;do not bypass validation or silently alter measurements. No new workflow is implemented tonight.
3. Simplify Country/Province/State selection:Canadian users should see Canadian provinces/territories without scrolling through U.S. states. Inspect existing country controls first. Preserve saved property regions,tax settings and historical estimates;do not silently change regional taxes when filtering options. No implementation tonight.
4. Preserve all existing Linear edit/Save/Cancel/native-touch locks and manual Roofing pitch,geometry,scope and incomplete-measurement safeguards. Keep AutoMeasure code and QA-only restrictions intact;keep AI Trace removed.

## Resume safely

Verify current recovery HEAD,checks and Render before editing;do not overwrite newer work. Read docs/QA_AREA_VALIDATION_2026_10_28.md,docs/QA_POLYGON_TOUCH_2026_10_28.md and docs/QA_LINEAR_TOUCH_2026_10_28.md for the phone fixes and precise evidence. Account handoff remains docs/RESUME_HERE_2026_10_28_ACCOUNT_SECURITY.md. Full regression72/72 and targeted touch validation at320/390/768px passed. No agent physical-device pass claimed.

For an existing invalid phone draft,Cancel restores the prior in-job area. “Saved in this job” may not mean server-persisted:save the completed estimate before refreshing unfinished work. Existing invalid drafts are NOT automatically repaired. Crossed-edge-specific highlighting and exact ordered coordinates of Sean's screenshot remain unverified/unimplemented. Live reset-email verification still awaits a separate verified QA mailbox;never reset the existing account's credentials.

No imagery integration,measurement formula,pricing,tax,PDF,account allowance,schema,Stripe or CRM changes in this end-of-day save. Main baseline c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a,production and real customer accounts remain untouched. Previous checkpoints and all approved features preserved. Stop after confirming the saved documentation checkpoint;do not begin another batch.

---

Latest authorized fix:Area self-intersection interaction investigation from9bf10b0. Read docs/QA_AREA_VALIDATION_2026_10_28.md first. Confirmed accidental background taps appended vertices during Area and QA manual-roof corrections;guarded without weakening validation or repairing existing geometry. Actual iPhone screenshots reviewed;exact draft coordinate order unavailable. Preserve unfinished phone work before any refresh. Verify recovery HEAD/checks/Render before resuming.

Latest authorized fix:repeated Area/Roofing touch correction from2e94561. Read docs/QA_POLYGON_TOUCH_2026_10_28.md first. Area and roof correction have independent confirmed failures and now share explicit drag/native-touch locking,with reviewed-roof auto-pan disabled. Exact physical-phone retest remains pending. Verify recovery HEAD,checks and Render before resuming.

Latest follow-up:repeated Linear phone edits frombb60300. See the new follow-up section in docs/QA_LINEAR_TOUCH_2026_10_28.md. It fixes confirmed native page panning while Linear correction is active;repeated touch Edit/Save and saved-editing checks are expanded. Exact physical-device retest remains pending. Verify recovery HEAD and Render before resuming.

Latest authorized batch:Linear endpoint touch correction from7bf0208. Read docs/QA_LINEAR_TOUCH_2026_10_28.md before older resume entries. Fix is limited to temporary map-pan locking during Linear correction and disabling its marker auto-pan;touch checks320/390/768 plus existing full regression evidence are documented there. Physical-phone recheck remains pending. Final checkpoint is recovery branch HEAD;verify GitHub/Render before resuming. Main/production untouched.

## Latest — final account security and subscription reliability batch

Read docs/RESUME_HERE_2026_10_28_ACCOUNT_SECURITY.md first. Application checkpointea73ac6 contains five confirmed security fixes across four small commits.72 regressions and disposable PostgreSQL tests passed; real controlled browser CSRF and account-switch recovery passed. No allowance history/anchor or imagery/measurement/PDF changes. Final documentation commit is recovery HEAD; stop after completion. Earlier content below is historical context.

# AeriQuote — October 28, 2026 handoff (America/Edmonton)

## Current recovery state

Repository:Seandusome/aeriquote-roof-measurement. Work ONLY on landscaping-multi-area-recovery-oct11. Started from verified6758d12, tree0b5c5ebeecc0d5690732bb43bb001265dd5dd5f0, Render dep-dbgitp5g1s2s73c87mc0 LIVE. No newer work existed. Workspace maintenance had restored an older local checkout; preserved it at aeriquote and reconstructed exact GitHub blob hashes in a separate aeriquote-oct28 folder. Verified complete baseline tree equals GitHub. Do not resume from the stale aeriquote folder. Local and connector commit IDs differ; source tree equality is authoritative.

Verified application checkpoints:
-2f53fa8f05f857b2f6f281cd5a3db8773997ef0d: automatic roof resampling/partial-overlap protection (local3453d5b).
-803f3e8a88c876e0b948e8c7a8791f81cf5e3fe3: browser test harness handles intentional no-image reports (local89fea7a); no application changes.
-fb23535f862f4403aa89cb102f91ad3b8a2d35fc: saved-money reconciliation warning/PDF guard (localf597052). Latest application commit. Render dep-dbh4m6favr4c739f9cl0 LIVE at19:21:51UTC. Application CI40753481980 and recovery40753482300 succeeded, including disposable PostgreSQL tests.

The final documentation commit is the recovery branch tip. Resolve HEAD before resuming; never overwrite advanced work. Verify final tip CI/Render status before claiming it live. Completion response supplies that final checkpoint. Main baseline c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a is read-only and untouched. Recovery branch is NOT protected; administration remains a separate task. Never change production, real customer accounts, or security settings to run tests.

## Batch 1 — confirmed overlap bug fixed

Yesterday's exact-vertex-set check rejected repeated roofs across IDs, rotations/reversal/closing/repeated vertices. It missed identical footprints with an extra collinear vertex and partially overlapping automatic roofs with distinct IDs. Confirmed real disposable Flask save returned200 and overwrote the QA record with duplicated coverage. New regressions failed red, then passed.

measurement_integrity.snapshot_error now applies the EXISTING positive-area polygon overlap validator across automatic outlines. Resampling cannot disguise the same coverage. Shared edges/vertices and disconnected garage outlines remain accepted; positive controls passed. Invalid quote rejected before estimate/allowance writes, valid record retained, no geometry silently deleted. This is validation only: no AutoMeasure engine, masks, Solar calls, imagery, pricing formula, schema or persistence changes. Existing exact-ID/vertex checks retained.

Existing18 API industry/pricing cases still pass:all six industries x regular/discount/taxes included; concave L/triangle/narrow valid area, duplicate vertices, multi-area+zigzag line, edits/replay/stale versions, unconfirmed manual roof scope/pitch, adjacent4/12 and8/12 planes plus detached6/12 roof. Independent GeographicLib2.1 WGS84 references and pitch identities, independently written Decimal pricing fixtures. Sphere/ellipsoid tolerance0.6%, not survey accuracy.

## Batch 2 — recovery/account security

Real local Chromium recovery test passed:unsaved refresh/navigation warnings; dismissing retains exact measurements/customer. Shared session logout, expired save, other-business login in another page:report remains closed, draft intact, foreign estimate list empty; correct-business re-login then save/reopen succeeds. Failed profile fetch in new business does not show prior-business cached branding. Forced native tab close warns; simulated forced target destruction bypasses warning and loses unsaved in-memory geometry. Saved estimate survives and no phantom revision is created.

No autosave or persistence added. Any future draft recovery must first address account binding, stale revisions, duplicate retries, sensitive customer data in browser storage, cleanup, migration and allowance deductions; report risks and obtain approval before implementation. This batch changes no database persistence behaviour.

Test harness correction:the aerial aspect assertion ran even when the recovery test intentionally selected no images. Guard it with imageChoice!==none. This was a testing defect, not an application failure; the real recovery workflow passed after correction. Updated committed test coverage preserves aerial assertions in image-based cases.

## Batch 3 — subscription allowances

25 Basic/75 Pro/200 Business validated by existing real disposable DB suites:exact anniversary rollover, leap year/end-of-month boundaries, preserved lifetime records, simultaneous final-credit requests, rollback on failure, failed property imagery acceptance, retry identity, owner/employee shared usage, business isolation, immediate disable/reactivation and complimentary rules. No extra entitlement on reactivation. Client profile edits cannot reset usage/billing anchor; named test-service status cannot bypass a real paid plan. PostgreSQL CI covers true concurrent transactions in postgres:16, never a customer database.

Actual Stripe period anchors remain UNFINALIZED. Current fallback uses account-created UTC billing anniversaries and preserves migration rules. No Stripe, purchases or credit-accounting policy changes.

## Batch 4 — controlled and actual imagery/PDF evidence

Local Chromium141 (Playwright1.56.1), disposable SQLite, external providers blocked:18 complete workflows across six industries x390/768/1440. Controlled labelled grid imagery, two concave areas/four-point line for surface industries and confirmed manual pitched roof for Roofing. Draw/save/price/customer/create/fresh-page reopen/PDF, no script errors or measured horizontal overflow, intrinsic aerial proportions checked, quote/customer/pricing unchanged after downloads.36 controlled PDFs generated. Independent WGS84/Decimal verifier passed all18 saved snapshots.

After saved-money guard, three additional Snow390/768/1440 workflows and six actual PDFs passed; independent verifier passed. Those nine rendered pages were visually reviewed. Dense tiny fixture labels and width-dependent framing remain readability limits; no PDF redesign. The fixture report-image stub is NOT proof of provider-baked roof outlines.

Actual authenticated test-site QA access required a fresh sign-in. Initial email/password attempt was rejected; Sean restored access. Existing history contained clearly QA TEST/DO NOT SEND records; only those were read. No profile save, new live estimate, measurement redraw, usage charge or customer record edit was performed. Live provider checks are saved reopening/export checks, NOT six new live property-measuring workflows.

Reopened actual imagery and downloaded Single/Expanded for all six industries,12 primary live PDFs/18 pages rendered and visually reviewed:
- Landcaping current QA version,2301 Avenue C North:16372ft² +454.8ft, seasonal10% discount, extra25.50, subtotal2080.19/GST104.01/PST124.81/total2309.01CAD. Decimal reconciliation passed.
- Snow/Pressure/Paving prior QA versions:16372ft² +463.2ft, subtotal1961.47/GST98.07/PST117.69/total2177.23CAD. Decimal reconciliation passed.
- Commercial prior QA version:17463ft² +602.5ft. Discovered legacy discrepancy below; do NOT distribute the pre-guard PDF as a valid quote.
- Roofing Pinehouse QA record:two existing manually traced sections,displayed5092+5436=10528ft², assumed/fixture-confirmed5/12 pitch; subtotal1052.83/GST52.64/PST63.17/total1168.64CAD reconciles. Record notes explicitly say synthetic four-corner QA traces, not verified real roof geometry. Actual photograph rendered, but NO claim that these outlines measure the actual roof or constitute verified architectural accuracy.

All primary live Single1page/Expanded2pages; photo/outlines/edge labels/number markers/customer/company content visible, no discovered stretch or clipping. Five actual landscape Street Views640x360, July2015, retained full proportions. Roofing saved no Street View:approved placeholder, actual Roofing Street View remains unverified. Company AeriQuote QA plus existing ShingleXtra logo/contact configuration preserved; no branding change or cross-business data used. Real aerial source1280x840 displayed708.5625x464.984375:aspect ratio relative to source1.000021 (pixel rounding).

Several paired-download tool calls returned a second path without completed bytes. Separately re-exporting each Expanded document and verifying its browser-side size before navigation yielded valid synchronized files. This is NOT evidence that the application generated corrupt PDFs; all completed files parsed/rendered. Do not link reserved/missing paths.

## Confirmed historical money defect and non-mutating safeguard

Commercial October18 saved record displayed subtotal1896.93 +GST94.85 +PST113.82 =2105.60, but stored total displayed2105.59. This predates current currency rounding. Do not backfill, silently reprice, change stored totals or delete history. Other five primary live jobs reconcile.

New savedEstimateMoneyIssue compares displayed cent values of tax base/taxes/total, failing closed on missing components. Historical report clearly shows a review warning while preserving original values. Common PDF entry point blocks inconsistent saved pricing before image/capture/vector branching; valid Single/Expanded/QA Vector paths remain unchanged. Existing EDIT MEASUREMENTS / PRICE action can produce a corrected new version after explicit user review/save. Native print was not separately exercised; the warning exists in the report DOM and is not hidden by print CSS, but no claim of complete native-print pagination verification.

Live post-deploy verification:reopened the exact same Commercial version, original2105.59 retained, warning visible, PDF click blocked with clear status. No record was rewritten. Screenshot saved. Then reopened valid Landscaping version and successfully completed both PDF exports again after the guard; render/visual check passed, values unchanged. Final representative downloadable examples are these post-guard Landscaping PDFs, not the inconsistent Commercial exports. Pre-guard Commercial evidence is isolated under before-guard.

## Batch 5 — first-time experience

Five measurement/quote steps remain intact; existing simple industry tools, help and saved/edit feedback preserved. Current real onboarding JS plus isolated signup/profile endpoints pass six fresh fictional industry trials and12 setup variants:CA/US region/tax/rates, saved benefits/services, validation, failed-save retry, duplicate finish prevention and delayed account response retaining edits. Protected workspace and first saved-estimate routes pass. This is developer/controlled workflow review, not an untrained contractor study or six fresh live signups. No speculative wording/UI additions, CRM or measuring tools.

## Regression and remote verification

Post-overlap full69 commands passed. Post-money full70 commands ran:one old PDF fixture supplied savedPricing total only, omitting tax fields. Completed that fixture with consistent base800/taxes0/total800 and reran its real DOM suite successfully; all other69 were green unchanged. Final clean GitHub70-command recovery suite atfb23535 and application validation succeeded; PostgreSQL jobs succeeded. Added test_saved_money_guard.cjs covers the actual legacy fractions, rejection before PDF capture/provider calls, no mutation, valid amounts and included-tax residual.

Final source changes:measurement_integrity.py overlap validation; app.py9-line historical money warning/export gate; tests/CI only otherwise. All Google/Mapbox/Leaflet/Solar integration code, imagery resolution, PDFs' valid designs, AutoMeasure code, manual Roofing/Vector QA restrictions, allowances and approved wording preserved. AI Trace remains removed. No physical-device tests.

## Remaining launch risks and exact next resume

1. Forced browser crash/discard/OS kill still loses unsaved drafts. No approved persistence solution yet; obtain approval after risk design.
2. Actual roof geometry/pitch/provider completeness is not ground-truthed here. Pinehouse fixtures are explicitly unverified synthetic boundaries. Preserve fail-closed incomplete/overlap checks.
3. The old Commercial record remains inconsistent by design; it is now marked/re-export blocked. Correcting historical data requires deliberate owner review/new version or separately approved migration, never automatic repricing.
4. Real phones/tablets touch/drag/pinch/native downloads and actual portrait Street View remain unverified. Browser emulation is not physical-device evidence. Fresh live drawing/save flows for every industry were not rerun today; live checks used existing QA records, while full workflows used controlled providers.
5. Imagery/Solar licensing remains unresolved. Do not assume testing grants commercial rights or change integrations while awaiting Google/Nearmap responses.
6. Recovery branch protection absent. No administrative permissions changed. Current-month anchors are provisional pending trusted Stripe periods.
7. Dense labels/paper efficiency in complex controlled exports need separate scoped review if requested; no redesign authorized or performed.

Next session:verify remote recovery HEAD and exact Render LIVE commit, read this file first and October27 handoffs for history, then select the next approved risk with Sean. Work ONLY on recovery. Never touch main/production/customer accounts. STOP after today's final report; do not begin another batch without approval.

Reproducible tests live in repository. Scratch evidence:/tmp/oct28-overlap-red.log,/tmp/oct28-overlap-green.log,/tmp/oct28-final-results.json,/tmp/oct28-browser,/tmp/oct28-recovery-browser.log,/tmp/oct28-money-positive. Live artifact/evidence directory:/workspace/scratch/c13e42512364/output/oct28-live; may be pruned, so use committed tests/docs and separately saved representative PDFs. Current local checkout:/workspace/scratch/c13e42512364/aeriquote-oct28. Pinned temporary browser dependencies:/tmp/aeriquote-qa-deps (jsdom30.1.2,Leaflet1.9.4,html2canvas1.4.1,jsPDF2.5.1,Playwright1.56.1); system Playwright's newer Chromium download was truncated, so the pinned official stable build was used. That environment failure was not an application defect.
