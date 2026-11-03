# Focused live QA — November 3, 2026

Live recovery application: `c7f2d013edf4425972c3fd8da48137a9b2d45882`, deploy `dep-dbl2klff3r2c73890gs0`. The recovery process asserted isolated database binding before and after deployment: host `dpg-dbj4f7lg1s2s73eob8t0-a`, database `aeriquote_recovery_qa`. Auto-deploy remains OFF. Required CI previously passed on this exact application source; no source edits or new workflows in this batch.

The earlier authentication blocker is resolved: the user signed into fictional QA account `qa-browser-oct31-2026@example.invalid`. Correct Render login email is `sdusome@diitalk.com`.

## Passed live

- Reopened fictional QA job, removed Service Area 1 (6,125 ft²), retained Service Area 2 (1,733 ft² @ $0.27), and drew a new nonoverlapping 1,218 ft² area. New name was Service Area 3, with unique names and retained rates. Existing 188.264011 ft line @ $0.10 remained priced.
- Saved area estimate: $467.91 + $328.86 + $18.83 + $54.25 extra = $869.85; 5% $43.49, 6% $52.19, total **$965.53**.
- Customer name `FICTIONAL Roofing Snow Removal Landscaping Customer`, email `roofing-snow-landscaping@example.invalid`, and service `FICTIONAL Roofing roof garage Snow Removal service` remained unchanged in report and both PDF layouts. Internal job notes are not customer PDF content.
- Roofing section Edit, selected 9/12 then Cancel: exact sorted rendered SVG path data unchanged; saved section still 7,348 ft² at 22.62°, and Edit/Delete buttons enabled. Repeated Edit/Cancel worked. No destructive Delete was submitted; enabled state only was verified for Delete.
- Reopened original saved Roofing revision, repeated Edit/pitch change/Cancel, confirmed scope, explicitly entered $0.27, and generated saved Roofing estimate/PDFs. Exact quantity 7,348.380392728047 ft²: rounded service $1,984.06 + $54.25 = $2,038.31; 5% $101.92, 6% $122.30, total **$2,262.53**. All priced geometry appeared; surface history excluded.
- Selected “I set each job’s rate” through the QA business setup. Fresh app started with blank rate and a disabled estimate button. On a measured/confirmed workspace, blank and -1 blocked creation; explicit 0.27 enabled it. Fresh-property measured workflow after manual setup was not repeated. QA fictional profile now uses manual pricing; no production profile changed.
- Four actual live PDF downloads reviewed visually, all 7 pages: area Single (1), area Expanded (3), Roofing Single (1), Roofing Expanded (2). Files are in `docs/qa/live-focused-2026-11-03/`. These PDFs are raster exports, so visual inspection was used rather than relying on empty text extraction.
- Independent WGS84 quantity checks: area 1,735.4695 / 1,220.2302 ft², line 188.81575 ft, roof surface 7,360.52376 ft². All within documented 0.6% spherical/geodesic tolerance. Decimal rate/tax/total calculations match exactly. Results in `independent-reconciliation.json`.

## Confirmed remaining usability issue — report before expanding

User noticed the small pitch/scope checkbox. Reproduced on current deployed c7f2d013, not an old screen. Unchecked scope blocks estimate despite a valid $0.27 rate, but summary heading incorrectly says “Price required”; it also says “22.6° pitch confirmed” and “Measurement looks ready.” Small checkbox text is the only explicit scope action. After Cancel, selector shows attempted 9/12 while saved section correctly remains 22.6°; the distinction needs care in the UI.

Proposed next focused change: prominent **Confirm pitch** action beside the actual saved pitch value, visible confirmation status, and explicit estimate-block explanation naming pitch/scope rather than price. Keep per-section validation and final all-buildings confirmation. Never silently verify default 5/12. Do not bind confirmation to the unsaved selector value. No code change implemented yet: user requested a report before expanding this batch.

## Pending / preserved

Pitch confirmation UI fix and regression checks are next. Destructive Delete execution, fresh measured-property manual-rate sequence, Sean's manual desktop review and physical-phone testing remain pending. No old uncertain draft or promotional-price sequences investigated. Two pre-existing untracked PDF copies preserved untouched. Main, production, customer data and database connection settings untouched. QA tabs kept available; latest unsaved workspace has scope unchecked deliberately to demonstrate the block.
