# Mobile Expanded PDF correction — October 27, 2026

## Verified start and bounded change

GitHub recovery HEAD7afa2328c396497c67395a20671ccc70353c76a3, treebb9d1c3fb5a80e041b4d6fb5b89fd8107ccccc06, matched the tested local5254ddd tree. Renderdep-dbggcd0ae00c73dqkjf0 was LIVE at that commit. Work stayed on landscaping-multi-area-recovery-oct11. Main/production and real customer accounts untouched. Recovery branch still reports protected:false; this correction does not configure repository administration.

The previously confirmed390px Expanded aerial stretched horizontal proportions and circular numbered markers into ellipses. The exporter gave the image a full-width/fixed-height rectangle and relied on object-fit:contain. html2canvas's capture did not preserve that fit. Original PDF renders from the preceding batch provide the before image.

Only Expanded PDF presentation changed:

- Calculate the largest proportional fit from actual aerial pixel dimensions and available page space. Set explicit matching pixel width/height, centred. No reliance on object-fit; no crop, provider request, resolution reduction, refit/zoom or geometry recalculation.
- Keep numbered markers circular by preserving the entire captured aerial's pixel ratio.
- Clip numbered-marker leader strokes around existing area/dimension label rectangles and the marker boxes. Labels, measured values and marker numbers are retained. This is an Expanded-only drawing adjustment; existing measurement placement and labels elsewhere remain unchanged.
- Reject invalid/zero dimensions rather than silently stretching an unusable image. The existing export failure cleanup still runs.

Single capture function, pricing calculator, quote snapshot function and QA vector exporter were compared with the starting source and are unchanged. Google/Mapbox/Leaflet imagery layers, API calls, Solar functionality, account allowances and licensing-dependent workflows are unchanged. AI Trace remains removed.

## Regression verification

- Targeted Expanded tests: portrait/square/landscape aspect fit, maximal proportional size inside available rectangle, invalid image rejection, leader clipping around labels, fully covered and zero-length leaders, existing photo/date pagination and continuation.
- Existing DOM exporter test still proves seven measurement/pricing rows, page numbers, unchanged snapshots and cleanup after an injected capture failure. Its failure mock previously returned an image without width/height; corrected the fixture to include the same1200×900 valid dimensions used by its successful case, preserving the intended capture-failure assertion. The first full run exposed this test-fixture problem; the final full run is67/67 PASS, zero failed.
- Existing failure, saved-editing, pricing/tax, independent geometry, account isolation/credits, Single/Expanded, manual Roofing and QA vector regressions all pass within those67 commands.
- Real local Chromium: six industries ×390/768/1440px =18 workflows. Explicitly enable QA_BROWSER_ALL_PDFS=1 in scripts/test_prelaunch_browser.cjs to download both layouts for every combination. Existing default harness behaviour remains available.
- Actual html2canvas/jsPDF downloads:36 PDFs,54 rendered pages. Single1page and Expanded2pages for each fixture. All54 pages visually inspected through six nine-page comparison sheets, plus the detailed phone aerial. No new clipping/hidden prices/customer details observed in these fixtures.
- The capture wrapper checks actual Expanded image CSS width/height against natural pixel ratio at every width. Every export additionally asserts unchanged frozen quote, pricing text, customer name and company branding.
- Independent GeographicLib2.1 WGS84 polygon/line references and separate Decimal arithmetic validate all18 saved snapshots. The existing0.6% geometry tolerance reflects spherical-vs-ellipsoidal approximations and rounding, not survey accuracy. Final totals unchanged: surface153.18CAD; Commercial163.52CAD; manual roof79.30CAD, with explicitly selected5%+6% tax.
- Pixel-component inspection of30 numbered navy circles across the15 surface-industry Expanded PDFs measured width/height ratios0.9615–1.0371, consistent with circular raster edges rounding by about1pixel. Visual review independently confirms round markers and undistorted grids/diagrams. Roofing has no commercial numbered circles; its roof/dimension pixels retain the same aspect fit.

## Visual result and limitations

The390px source remains a portrait aerial on the landscape PDF page. It is now centred with side space instead of stretched horizontally. Tablet/desktop source shapes likewise retain their own proportions. This preserves every captured pixel and label; it does not request extra imagery or pretend all devices captured the same map extent.

Numbered-marker leader lines no longer run through the tested area/dimension labels. Extremely dense or long labels can still exceed available space; this bounded change does not promise collision-free labels for every possible property. No important information is hidden to force a fit.

All data/imagery in this new matrix is fictional QA data with a labelled synthetic background. Actual browser pointer drawing, server SQLite save/reopen and PDF rendering are real, but provider results are controlled fixtures. No authenticated deployed Google imagery, physical phone/tablet touch/native printing, real roof ground truth or licensing authorization is claimed. Existing ordinary AutoMeasure is preserved and regression-tested, not newly developed; browser Roofing uses the existing allowlisted manual QA workflow.

## Deliverables and reproduction

User-facing examples: AeriQuote_Expanded_PDF_390px_QA.pdf; AeriQuote_Expanded_PDF_Comparison.png (before390 and corrected390/768/1440); AeriQuote_PDF_QA_All_Industries.zip (all36 PDFs, saved fictional sources and six rendered comparison sheets). These are QA estimates, never send as real customer quotes.

Use scripts/prelaunch_browser_server.py only on loopback with its disposable fictional account/provider. Run QA_BROWSER_ALL_PDFS=1 QA_BROWSER_IMAGES=hide with the existing browser harness; stop server afterwards. Run scripts/verify_prelaunch_browser.py OUTPUT. No customer DATABASE_URL. Persistent application changes/reports are in the recovery Git tree; test-output scratch may be pruned. Final GitHub checkpoint/terminal CI/Render results are reported after publication in the conversation. This file is committed with the verified correction, not a separate feature batch.
