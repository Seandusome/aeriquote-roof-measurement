# AeriQuote — resume here, October 27, 2026

## Latest follow-up — approved Mobile Expanded PDF correction

The CURRENT commit containing this updated resume follows7afa2328c396497c67395a20671ccc70353c76a3 and fixes the previously documented390px Expanded PDF distortion. Read docs/QA_MOBILE_EXPANDED_PDF_2026_10_27.md and its RESULTS.json before treating the historical remaining-issue list below as current. Explicit proportional aerial sizing preserves pixels/marker circles; numbered-marker leader strokes avoid existing label boxes. Only Expanded presentation changed. Single, vector, imagery/API/Solar, measurements/pricing/accounts are unchanged.67/67 final regressions;18 Chromium workflows;36 actual PDFs/54 rendered pages reviewed; independent WGS84/Decimal checks passed. No physical-device/live-provider licensing claim.

The old phone-distortion/leader-overlap entries below are historical findings now corrected in the tested fixture matrix, not reasons to repeat or revert this work. Extremely dense labels, authenticated deployed provider workflows, physical devices, licensing, provisional billing anchors and missing branch protection remain limited/unverified as documented. Final remote SHA/CI/deployment are verified in the conversation handoff after this commit is published. The remainder records the preceding7afa232 QA checkpoint for continuity.

## Current scope and stop state

Continue ONLY on landscaping-multi-area-recovery-oct11 in Seandusome/aeriquote-roof-measurement. Do not touch main, production or real customer/demo accounts. Keep AI Trace removed, AutoMeasure intact, manual Roofing and Vector Diagram PDF QA-only. Google/Nearmap licensing discussions are pending. No imagery provider, Leaflet imagery layer, Solar function, aerial PDF renderer, pricing engine, saved estimate schema or allowance policy changed in this batch. Do not connect Stripe, build CRM or develop architectural roof plans.

This resume is committed with the final Batch B change and evidence. **The commit containing this file is the final checkpoint**; get its exact SHA from GitHub branch HEAD/final conversation handoff, rather than assuming the older base is current. Its tested parent is d068dd7 below. Verify current remote head/CI/Render before any next edit. Do not repeat completed repairs.

## Checkpoints and repository safety

- Started from3c4e56303e1be1eb14c2c398ba136fbfa34a329b, complete tree85645213a405b7e0c2e627e8198b49b1fdcc9a6f. That checkpoint was LIVE on Render and had successful GitHub application/recovery runs40139995097/40139995133.
- Workspace maintenance had restored local67a7421 (the earlier725472c equivalent). Fetched the recovery branch, restored its three changed files only, committed the local equivalent asbe337ed and verified exact complete-tree equality. Important source was not discarded. Local/connector commit IDs differ by construction, but trees are compared.
- **Batch A:** d068dd7b02272d173055a171c1d8348b50f2f821; locald9fcf61; treef8bde323e5ed7c9dfb4d214102f277bd610f9206. Unsaved-work warning scope fix.67/67 regressions passed. Verified LIVE deploymentdep-dbggaqcs728c73fgcv20, finished2026-10-27T20:12:06Z.
- **Batch B/final:** this document's commit adds the passive property-pin repair, regression assertions, optional isolated browser harness and reports. Final67/67 regressions and18/18 Chromium matrix passed on its application source. Final CI/deploy must be verified after publishing; accepted/queued is not success. Final handoff records terminal results.
- Main unchanged atc049a04b2ac5cc4df3d5c253fe9ca12f1d85806a. No main checkout, merge, push or deployment.
- **Recovery branch is NOT GitHub-protected:** API explicitly returned protected:false. Available connector has no branch-administration writes. Owner must configure suitable branch rules/required checks. Recovery-only checkout and expected-head publishing protect this work operationally but are not a substitute. Do not claim this is complete.

## Repairs and proof

### A — broken unsaved-work warning

beforeunload referenced historicalMode, which exists only as a showCustomerEstimate parameter. Real Chromium emitted ReferenceError during navigation. Existing VM test masked it with an invented global. Removed the artificial test global first and observed the regression fail. Removed only that out-of-scope reference in the handler. Loaded/nonempty unsaved work warns; identical clean saved work permits navigation; edits after saving warn; no-token/empty work does not warn. No draft autosave added, and an already running old browser tab does not receive this JavaScript automatically.

### B — property pin swallowed intended measurement clicks

Actual pointer testing identified the third rectangle corner hitting the default property marker instead of the map: four intended corners became three saved vertices, producing330ft² instead of659ft² in the fixture. Server checks cannot infer a corner the UI never recorded. A new per-click Chromium assertion failed2 versus3 before the fix.

setPropertyMarker now creates the same visible pin at the same coordinates with interactive:false,keyboard:false. It no longer blocks drawing through its image; its former hover tooltip is passive. Do not replace this with bubbling marker clicks at the marker centre, which could record incorrect coordinates. No imagery API/layer/projection or area/length/pitch arithmetic changed. DOM marker-option assertion is in existing recovery CI; real pointer assertion covers every area, manual roof and line point. Old incomplete outlines cannot be repaired automatically: visually review suspect historical jobs.

## Verification completed

1. Full authoritative local recovery suite:67/67 commands passed after EACH repair, zero failures. Includes independent geometry/pitch, manipulated pricing/geometry rejection, multiple areas/lines, overlap/duplicates, saved history/editing, discounts/included/added taxes/seasonal periods, account isolation/employee access, failed saves/idempotency/timeouts/session expiry, subscription boundaries and all PDF/vector guards. New failure test first reproduced red, then passed.
2. Real local headless Chromium against original rendered app and real Flask/SQLite routes:18 combinations (six industries ×1440/390/768). Standard fictional-account login, controlled property provider, synthetic labelled grid imagery; mouse clicks/buttons/customer input, saved estimate, fresh page/reopen, matching stored totals/customer names. All pass, zero script errors and no measured workspace horizontal overflow. Every intended corner is explicitly counted after the pin repair. **These are viewport/mouse tests, not physical devices or live provider ground truth.**
3. Five surface industries combine two four-vertex areas and one line, including empty Add Area→Linear. Roofing uses the existing explicitly allowlisted manual QA trace, confirmed pitch and scope. Normal AutoMeasure completeness/pitch/garage paths remain covered by API/DOM fixtures; no live new Solar result was independently ground-truthed.
4. Real browser POST aborted once: customer report stays closed and exact snapshot remains; retry succeeds. Other401/409/timeout/concurrency/credit cases pass controlled suites; no real customer changes.
5. GeographicLib2.1 WGS84 polygon/line references and independently written Decimal arithmetic pass all18 final browser source snapshots. Tolerance0.6% accounts for existing spherical-vs-ellipsoidal methods and rounded quantities; not survey accuracy.
6. Final fiction-only example totals: surface jobs153.18CAD; Commercial163.52CAD with its distinct linear rate; one confirmed pitched manual roof79.30CAD. SK5%+6% explicitly selected. Regional AB5%/0%, discounts and other rates are covered by existing suites, not inferred from the SK browser fixture.
7. Sixteen actual html2canvas/jsPDF downloads,24 pages rendered/reviewed: both layouts for every desktop industry, plus both layouts Snow at390/768. Single1page/Expanded2pages. Saved quantities, customer/company, taxes and totals agree. Synthetic background only; manual Static-path image baking is stubbed, so no claim of provider-rendered roof correctness. Phone Expanded distortion remains a confirmed visual failure below. Earlier no-image18-case run also passed.
8. No local PostgreSQL executable. Existing GitHub workflow uses disposable postgres:16 and tests real concurrency/rollback/credits/paid periods; final checkpoint's CI job must be checked before final status. Never use customer DATABASE_URL for a destructive test.

## Confirmed unresolved problems and next priorities

- **Phone Expanded PDF geometry distortion:**390px export stretches the aerial horizontally compared with1440/768. Circular numbered labels become ellipses; synthetic grid/diagram proportions differ. Quantities/totals remain correct. Existing leader overlap is visible. Aerial PDF modifications were expressly forbidden here, so the renderer is unchanged. Seek a specifically scoped approval before repairing that layout; do not call PDF visual QA an unqualified pass.
- GitHub recovery branch protection absent; needs repository administration.
- Licensing unresolved. Read docs/GOOGLE_LICENSING_CALL_2026_10_27.md before the15-minute call. Obtain written authority for Leaflet/non-Google display, tracing/derived storage, imagery/PDF distribution and general-purpose Solar roofing. No new provider access is assumed.
- Fresh authenticated DEPLOYED six-industry Google imagery/actual-logo-upload/PDF workflows remain unverified in this batch. Sean personally confirmed the combined estimate now opens; his uploaded Commercial PDF was inspected earlier. That is not six-industry live coverage. Original old tab recovery remains unverified.
- Physical iPhone/Android/tablet touch/pinch/drag/rotation/native print untested. Device-width Chromium is clearly distinguished.
- Deliberate discard/crash still loses unsaved drafts; warning is not autosave. Cannot restore missing old drawing points without user confirmation.
- Billing anchors remain account-created UTC anniversary provisional until trusted billing integration exists. No Stripe changes.
- Live reset-email delivery, simultaneous public-signup versus employee identity race and real-roof ground truth/Pinehouse completeness require separate tests. Do not remove existing incomplete-roof guards.
- First-time UX sequence is visible and usable in these controlled runs, but no untrained contractor session was observed. Do not add controls/rename approved wording based on speculation. Your Company is a configurable fallback, two surfaces plus a line is intentional. Commercial title in an uploaded PDF alone does not prove an unwanted industry switch.

## Reports and reproducibility

- docs/QA_PRELAUNCH_2026_10_27.md: detailed findings, tests and explicit limits.
- docs/GOOGLE_LICENSING_CALL_2026_10_27.md: short technical briefing and written-permission questions, not legal advice/authorization.
- scripts/prelaunch_browser_server.py: temporary SQLite, fictional owner, loopback8765, fake provider, external calls fail closed; never use production accounts.
- scripts/test_prelaunch_browser.cjs: optional real Chromium regression; all six industries, three widths; every intended point; aborted save; actual save/reopen/PDF; browser errors fail. Default no-image path; QA_BROWSER_IMAGES=hide uses labelled fixture imagery. QA_BROWSER_OUTPUT sets scratch location. Target is hard-coded localhost for safety. Stop server after use.
- scripts/verify_prelaunch_browser.py OUTPUT: independent GeographicLib/Decimal checks for stored browser snapshots. See QA report for pinned test dependencies.
- Scratch evidence at time of save: /tmp/prelaunch-results.json and /tmp/prelaunch-regression.log; /tmp/aq-prelaunch-final/ contains18 sources/screenshots,16 PDFs and rendered contacts. These may be pruned; durable code/reports reproduce the tests. Do not claim stale scratch paths exist after maintenance.

## Safe publishing / continuing

Publish only the explicit source/test/docs files. Use a COMPLETE recursive Git tree, verify it equals tested local tree, create a child of the observed recovery head, expected_sha lease, force:false. Never publish a partial documentation tree. Auto-deploy is on commit for the TEST service; no extra manual deployment. Verify actual LIVE commit and terminal GitHub jobs, including PostgreSQL, and read-only main ref afterwards. Do not expose secrets or inspect customer databases.

Test Render service: srv-db5a2g5ckfvc739fui70, workspace tea-daaurjp5efls7391kvj0, https://aeriquote-commercial-test.onrender.com/. A successful public login-page request is health only, not authenticated workflow proof. The final code change is2small client fixes plus tests/documentation; all previous features and integration code are preserved. Leave unrelated generated Python caches uncommitted. No further feature batch is implied by finishing this save.
