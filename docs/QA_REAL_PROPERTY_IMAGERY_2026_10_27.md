# Real-property imagery verification — 2026-10-27

Base GitHub checkpoint:2382c49. Recovery branch only. Test Render service only; approved isolated owner QA session. Main, customer accounts and production untouched. AI Trace remains removed.

## Actual provider workflow and confirmed defect

Property:1715 2nd Ave N, Saskatoon SK S7K 2G4. Snow Removal, fictional customer QA TEST Real Imagery Oct27 - DO NOT SEND. Live aerial imagery and actual Street View (640x360, April2026) loaded through unchanged providers. A four-corner sample parking/driveway area and a two-point reference line were drawn and saved. The line crosses the property/roof front; it is a QA reference, not a surveyed sidewalk or complete snow-removal scope. No fictional imagery was used in this live workflow.

Saved and freshly reopened DOM customer/company, quantities and prices matched exactly. Area1239ft² at0.80=991.20; line displays48.0ft at0.25=12.01 (underlying unrounded distance used). Subtotal1003.21, GST5%=50.16, additional6%=60.19, total1113.56CAD. Independent Decimal line-item/tax checks passed. Existing branding Shingle Guard; no profile save/change. Prior same-property QA versions retained. Session counters are not proof of monthly-credit ledger deductions.

Actual Single(one page) and Expanded(two pages) PDFs downloaded, synchronized, parsed and rendered. Deeper inspection confirmed saved aerial canvas1280x840 displayed851.375x465, causing1.201537 horizontal distortion. Photo and outlines stretched together, hiding the issue in simple alignment checks. Numeric measurements/prices were unaffected.

## Narrow correction

Contain and center the existing saved canvas proportionally inside the unchanged report image box; preserve original pixels and saved georeferencing. Project Expanded area-number markers and label collision boxes into that fitted canvas frame, including its offsets. No provider/API, geometry, pricing, saved-record, credit, Street View, Vector or overall PDF layout changes.

## Local verification

New saved-canvas style regression reproduced red before repair, then passed. Full68-command recovery regression passed, zero failures. Includes geometry, pricing, account isolation, interrupted saves, credits, aerial/vector PDF guards and removed AI Trace checks. PostgreSQL is verified separately by GitHub CI, not claimed as local execution.

Real Chromium:12 completed six-industry cases at390/1440px, save/reopen, intrinsic saved-canvas ratio, Single and Expanded downloads, no script errors. These controlled regression fixtures use explicitly labelled synthetic imagery; they are separate from the real-photo live test above. Independent GeographicLib WGS84/Decimal checks passed for every source snapshot (0.6% spherical/ellipsoidal tolerance, not survey accuracy). No physical-device test.

## Deployment follow-up

After this commit deploys, reopen the exact existing saved QA version without changing records; verify canvas display/source ratio1.0, unchanged fields/totals, actual photo/overlay/number-marker alignment and Street View proportions. Re-export both actual PDFs, render all three pages and save final corrected screenshots. Record deployment, CI and final artifacts in the completion report; do not mistake initial distorted exports for final corrected examples.

## Limits

One actual Snow Removal property does not prove all-industry live provider accuracy, survey accuracy, roof completeness, licensing permission, physical-device behaviour or portrait live Street View. Six-industry checks above are controlled regression coverage only. Imagery licensing remains unresolved. Recovery branch protection is absent (read-only verified); no administration change attempted.
