# Phone and tablet layout QA — October 18, 2026

Recovery branch only. Latest application commit: 95d61058415f6cb9d89330b1b6d4a144e7b1df47. Render dep-dbaimoivcj2c73a9qer0 live; BOTH GitHub workflows passed. Main untouched, AI Trace remains removed, roof scope guards and manual 5/12 preserved.

## Method and limits

Built-in browser has no documented viewport/device emulation capability. Browser shortcuts did not resize it. Added an isolated, unlinked same-origin QA shell at `/static/scripts/mobile_visual_qa.html`, using the normal authenticated app in an iframe. Width choices 320, 375, 390, 430, 768 CSS pixels; height 780. The frame uses the existing QA account and normal authorization. No new authentication bypass or account created. This is real browser layout inspection, NOT physical iPhone/Android or touch emulation. Phone keyboards, pinch/pan, finger placement, rotation and native download/print integration still require real-device checks.

## Findings and fixes

- Main measuring HTML had no viewport meta tag. Added device-width/initial-scale; no zoom restriction.
- Header was a fixed horizontal flex row: account buttons disappeared beyond the clipped card and the logo/tagline consumed a large blank header at phone width. Shared mobile stylesheet stacks branding, wraps tagline and presents account actions in two columns; all remain reachable.
- Address fields, saved area controls, customer forms and tool buttons now fit phone width; inputs use 16px font, buttons at least 44px tall. Surface tools stack consistently. Drawing heads and page spacing wrap clearly. Map uses a bounded phone height.
- First drawing point revealed Undo/Start Over and moved the aerial. Mobile action slots and help space now reserve their dimensions. Live DOM geometry verified identical map top before/after first and later points, for BOTH Area (243.5px) and Linear (370.5px).
- Estimate actions did not wrap; phone footer now stacks them. Tablet report's inline width plus overlay padding caused horizontal overflow; 701–980px report now fits overlay and wraps actions. Live 768px check: overlay clientWidth=scrollWidth=736, report width 692. Phone 320/375/390/430 checks also fit.
- Single page export captured the narrow/tall phone report as an unreadably tiny strip on landscape paper. Phone/narrow exports now clone into a detached 1320px paper layout, freeze the approved map pixels, retain native aspect ratio, remove editing controls, then clean up the clone. Saved aerials use their native labelled canvas; live maps are captured without resizing/refitting Leaflet. Desktop capture at >=900px report width remains unchanged. Expanded export retains its existing fixed paper layout.

## Live checks

- Six workspace types inspected at 320px using visible Business Type control (no profile Save). Correct area/linear choices and Roofing AutoMeasure/secondary tools fit; body clientWidth=scrollWidth=303. Shared QA account's saved profile remains unchanged. Changing URL industry alone does not override its saved profile, so that was not treated as industry proof.
- All six four-step setups walked through final review at phone width (Roofing initially 390px, follow-up 320px; surfaces 320px). Business, price/taxes, optional branding and final review fit; DOM width checks show no horizontal page overflow. Final profile Save was deliberately not repeated. Existing earlier all-six live saved setups remain the persistence evidence.
- Roofing signup page inspected at 320px: industry, name/business/email/password guidance, country, free-trial terms and Create button visible and fit. No additional account submitted.
- Commercial fresh phone-width property entry: 2301 Ave C North, Saskatoon, SK. Illustrative area rectangle 11,560 ft² @ $0.10 plus 291.7ft line @ $0.25. Services $1,156.00 + $72.93, subtotal $1,228.93, taxes $61.45 + $73.74, total CAD $1,364.12. Saved customer `QA TEST Phone Width Area and Line DO NOT SEND`. Both drawing stages retained stationary aerial. This is a QA shape, not a certified measurement.
- Saved Paving combined estimate reopened through phone history; 16,372 ft² + 463.2ft, CAD $2,177.23 retained. Actual Expanded PDF downloaded from 320px view, both pages rendered/visually inspected: aerial/outlines/edge labels, measurements, prices and Street View present. Browser download-event listener timed out for iframe, but the actual nonempty PDF was recovered from the synchronized download directory; UI also confirmed download. No repeated click was needed.
- Fresh Commercial Single page PDF before fix FAILED visually (tiny phone strip). After fix, reopened the saved phone fixture and downloaded actual Single page PDFs, rendered and inspected. Final file after native-aspect correction is readable full paper layout, both measurements/labels, aerial, Street View, correct $1,364.12. Earlier failed file is not a passing fixture.

## Regression coverage

Public routes/assets/inline scripts, 29-page public UI, all-five surface workspace tests and full actual DOM/Leaflet controls passed locally. `scripts/test_phone_pdf.cjs` independently checks narrow clone width, map pixel/aspect preservation, live report unchanged, export cleanup on failure and unchanged desktop path. Added to recovery CI. Existing desktop DOM PDF fixture needed an explicit 1320px report width because JSDOM has no layout engine; its original aerial/vector assertions remain, and the full suite passed. Both CI workflows passed for application 95d6105. Follow-up adds native saved-canvas/aspect assertions and this checkpoint.

Remaining: physical mobile touch/keyboard/native download and print checks. Do not describe responsive iframe checks as a full real-device certification. No customer communication sent; payments remain deferred.
