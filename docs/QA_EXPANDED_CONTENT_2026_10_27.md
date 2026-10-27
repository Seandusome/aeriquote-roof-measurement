# Targeted Expanded PDF content and live artifact follow-up — October 27, 2026

## Verified base and scope

Recovery branch only, base GitHub811dfc9d9ee3566cdd7b34181f8deb7a3ef94f69, complete treeb319c7a3863f901ff269d37e71f199217a64e9fb. Render commercial test deployment dep-dbgher8ae00c739reem0 verified LIVE. No main, production or real customer changes. No imagery provider, API call, Solar, saved geometry/pricing, branding configuration, Single/Vector PDF path, allowance or AI Trace changes. Existing Single and Vector functions compare byte-for-byte with base.

## Three unavailable artifacts: investigation, not an assumed PDF defect

Original Pressure/Paving/Landscaping Expanded paths returned during the preceding QA session were absent in BOTH cloud browser filesystem and workspace. Thus a local rendering failure cannot explain that earlier inspection gap. The original bytes and download-completion/file-lifecycle telemetry are unavailable: initial file completion versus subsequent artifact cleanup cannot now be distinguished. Do not call those PDFs broken or claim a proven transfer-only cause.

Reopened the exact saved fictional QA versions via Previous Estimates > View History > Open Estimate. No new estimate/revision, changed branding or new measurement was required. All three re-exported successfully; immediately verified nonempty files in browser and workspace, parsed actual jsPDF2.5.1 PDFs, rendered and visually inspected both pages. Pressure1,751,268bytes; Paving1,768,830bytes; Landscaping1,734,401bytes, each2pages. Correct Shingle Guard branding,1733ft² +72.0ft, subtotal1393.60,5%69.68 +6%83.62, total1546.90CAD. These are authorized QA examples on public1715 Second Avenue North, Saskatoon; service rectangles are fictional, not surveyed boundaries. No application download-generation defect reproduced.

## Confirmed defects and limited repair

1. Expanded Street View cloned width100% with fixed170px height. Real source640x360 was drawn approximately565x170, distorting the photo. Overflow fitting also reduced height without width. Repair fits explicit width AND height from source dimensions inside the existing565x170 bounds; overflow reduction updates both proportionally. Full frame retained, existing caption/pagination intact, no image fetching/resolution/provider changes.
2. Expanded header copied customer name/date but silently omitted existing customer phone/email. Copy those already-present report fields into existing metadata on every page. Constrain grid tracks to minmax(0,...) and wrap long unbroken contact/address text rather than expanding past the page. Customer/pricing/source data are not modified. This is content restoration, not a major layout redesign.

No confirmed clipping in ordinary recovered PDFs; earlier proof screenshot was itself a cropped viewport and cannot establish PDF clipping. Long-contact output is tested separately below. Existing section pagination may require3pages (whole marketing block); do not collapse or redesign it in this batch.

## Verification

- Targeted proportional-resize regression failed before repair and passed after. Existing normal fit/overflow/continuation/date-block tests retained.
- Full recovery regression68/68 commands PASS after application repair, including pricing/geometry/account isolation/password/allowance/Single/Expanded/Vector guards. Final GitHub CI adds disposable PostgreSQL concurrency; verify terminal status after publishing.
- Local actual Chromium matrix6industries x390/768/1440 =18 complete measure/save/reopen workflows, both layouts,36 actual PDF downloads. Roofing uses existing QA-only confirmed manual pitched roof; five surface industries use2areas+line. Synthetic provider fixtures, NOT physical devices or live imagery truth.
- Three additional Snow long-name/long-unbroken-email cases at390/768/1440 with portrait source =6actual PDFs. All actual customer contact text present; DOM bounds/scroll checks before every Expanded page capture show no clipped metadata. No estimate/customer/pricing/branding mutation during exports.
- Total42actual PDFs/75rendered pages reviewed in contacts, selected1100px pages enlarged.21Expanded PDFs independently checked after Poppler rendering: calibration circle width/height ratios0.96–1.04 (pixel rounding), source border aspect ratio agrees, four frame edges preserved. Portrait360x640 and landscape640x360 fixtures; real Street View available in this QA property is landscape only.
- Authenticated fixture profile supplies company/logo for all six industries (not injected into report). Every workflow then switches to distinct fictional businessB: B profile hydrates, A logo absent, no A estimates visible. Existing real Flask owner/employee/profile/isolation suites pass. This is isolated fixture evidence, not a new live employee authentication claim.
- Independent GeographicLib WGS84 geometry/pitch and Decimal pricing checks PASS all21saved snapshots. Existing spherical/ellipsoidal tolerance0.6%, not survey certification. Surface totals153.18CAD, Commercial163.52CAD, confirmed manual roof79.30CAD.
- See companion RESULTS.json for per-export dimensions, prices, raster evidence, SHA256 and page counts. Opt-in reproduction: install existing browser dependencies plus Pillow/numpy/scipy/Poppler; run scripts/run_expanded_content_browser.py with QA_BROWSER_OUTPUT and NODE_PATH configured. All provider requests fail closed to fixture routes.

## Known remaining issues / boundaries

- **Single PDF Street View distortion remains:** portrait calibration circle becomes a wide ellipse at all tested widths; a landscape example can also be distorted depending on source/box ratio. Single function/style path deliberately unchanged per user's restriction. Requires separately approved narrow correction; do not call all PDF visual checks unqualified passes.
- Portrait Street View is smaller because the existing170px maximum height is preserved. No major photo/layout redesign attempted. Extreme/unbounded customer text can exceed a page; exhaustive arbitrary-length text is not claimed.
- All physical-device testing, real portrait provider examples, licensing permissions remain unverified. Baseline live Roofing mismatch guard remains intact; no live completed Roofing estimate was fabricated.
- Recovery branch protected:false remains an owner/admin configuration task; expected-head non-force publishing is used operationally. Main remains c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a.
- Postdeployment live corrected-export evidence and terminal CI/deployment state are reported in final handoff; this report records prepublication verification.
