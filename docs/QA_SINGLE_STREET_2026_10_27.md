# Final Single PDF Street View proportion correction — October 27, 2026

## Verified base / boundaries

Recovery branch landscaping-multi-area-recovery-oct11 only. GitHub f4e3f656c493026f85ab31025ce6016ea9e5188d, complete tree e374055c9710a5f5c453fdd8b421204b0eff8bec verified; Render test deployment dep-dbghspk9v7es73avaeu0 LIVE. No main, production or real customer accounts. All browser data in this batch is fictional, seeded in disposable SQLite databases; providers fail closed to synthetic image routes. AI Trace remains absent.

## Reproduction before changing application code

Generated actual baseline Snow Single/Expanded PDFs at390px(portrait360x640) and1440px(landscape640x360). Rendered and inspected. Portrait source's circle became a wide ellipse; independent raster test failed with width/height3.5357. Landscape showed lesser distortion because fixed photo box/source ratios were close. New unit regression first failed because Single capture did not fit source pixels.

Root cause: html2canvas2D renderer does not implement the existing CSS object-fit behaviour. Single capture stretched the image into the CSS box; source/provider data itself was not wrong.

## Narrow repair

Only captureSinglePageEstimate options changed: html2canvas's export-clone callback replaces the cloned Street View image with a same-size/class/style/ID canvas. Fit original image pixels proportionally inside its existing box; centre with white unused margins. No live DOM, imagery URL, map viewport or saved data is edited. Entire source frame, including embedded attribution, stays visible. Existing caption and surrounding layout stay in place. Existing2x export capture preserved. No PDF redesign, controls, new features or provider requests.

Expanded renderer/helpers and Vector path compare byte-for-byte unchanged against base. No pricing, subscriptions, schema, account configuration, Google/Mapbox/Leaflet/Solar or application wording changes.

## Verification actually performed

- Full authoritative regression68/68commands PASS after application change. Targeted phone PDF tests cover landscape/portrait containment, exact source ratio, unchanged live DOM/pricing, capture-error cleanup, desktop layout and existing phone aerial sizing. CI already invokes this regression; no new paid/test service.
-48unique real local Chromium cases:6industries x320/390/768/1440 xportrait/landscape. Every case draws fictional saved geometry, prices, creates customer estimate, saves/reopens and downloads BOTH layouts. Roofing uses existing confirmed QA-only manual pitch/scope; five surface industries combine2areas+linear.96actual PDF downloads,176pages rendered and visually reviewed in eight full matrix sheets plus enlarged samples. No browser script errors or measured horizontal workspace overflow in successful cases.
- Single export clone checks enforce identical customer/branding/pricing text and identical rectangles for header, customer metadata, pricing, CTA, aerial map and photo box before/after containment. Export also preserves exact quote/customer/company state.
- Independent Poppler raster checks PASS all96 PDFs: calibration circles remain round (pixel ratios0.9697–1.04), source-frame border ratios agree and all frame edges remain present. Both portrait and landscape exercised for EVERY industry/width, not just representative cases.
- Golden comparisons: four Expanded pages(390portrait and1440landscape control jobs) are pixel-identical before/after. For corresponding Single PDFs, zero pixels outside the photo region changed, allowing a4-level JPEG threshold and20px encoding boundary margin. Thus customer/branding/pricing/map content remains visually unchanged in these controls.
- Independent GeographicLib WGS84 polygon/line/pitch and Decimal pricing verification PASS all48saved snapshots. Surface153.18CAD; Commercial163.52CAD; manual pitched roof79.30CAD. Existing0.6% spherical/ellipsoidal geometry tolerance is not survey certification.
- Every browser case checks server-hydrated businessA company/logo and subsequently authenticates distinct fictional businessB: correctB profile, noA logo and noA estimates. Existing owner/employee/profile/account-isolation regressions pass.
- Initial long runs stopped at the21st repeated owner login. Confirmed independently in disposable Flask fixture: first20valid logins return302,21st429 under existing email limit. The remaining eight cases were completed in fresh disposable databases; no limit bypass or application security change. No PDF defect was inferred from that harness interruption.

Companion RESULTS.json records all cases, source image dimensions, prices, raster metrics,96PDF SHA256 hashes/page counts and golden checks. Opt-in reproduction uses scripts/run_expanded_content_browser.py, QA_VERIFY_SINGLE=1, requested QA_BROWSER_WIDTHS and QA_STREET_ORIENTATION; run fewer than21logins per fresh fixture. scripts/verify_expanded_street_raster.py accepts --all-layouts. Never point this harness at a live service.

## Actual visual findings / remaining limits

- Portrait image is narrower with white side margins; landscape may have small top/bottom margins. These preserve the full source and existing photo-box dimensions. Customer details, industry branding, geometry labels and totals retain their positions/readability in reviewed output.
- Existing Expanded pagination can use3pages for marketing continuation. No pagination/design change made.
- No new authenticated live-provider or physical-device testing performed in THIS batch. Prior live Expanded evidence at base remains documented separately. Synthetic portrait/landscape imagery verifies rendering, not Google/Nearmap licensing, actual property boundaries or ground-truth automatic roof geometry.
- Existing unsaved forced-discard loss, incomplete automatic-roof guard, licensing unknowns and lack of recovery branch protection remain separate issues; this approval did not authorize changes to those areas.
- Publication/terminal GitHub checks/Render exact SHA must be verified after committing; final handoff identifies checkpoint. Main remains c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a.
