# Focused saved-estimate PDF integrity correction — October 31

## Confirmed cause and reproduction

Starting recovery checkpoint2381a60987906ac27e5af7d2167b7adee1797001; remote HEAD and both completed workflows verified successful. Recovery was live at82fdd04 /dep-dbj4t6t659jc739gvv7g, auto-deploy Off. QA database configuration was not read as plaintext or changed.

The fictional browser owner’s property history at2301 Avenue C North, Saskatoon contains an initial manual Roofing version followed by surface-industry revisions with two service Areas and an independent Linear. PREVIOUS VERSION7 is the Commercial$1,570.25 snapshot. Reopening that exact revision reproduced the orange old roof/pitch/dimensions alongside the currently priced service geometry. A newly downloaded **Single** PDF also contains it. The issue therefore affects the historical diagram consumed by both Single and Expanded, not only Expanded pagination. Fresh interactive surface reports take an early surface branch and did not show that inactive roof.

The saved quote captures multiple geometry families so changing tools/industries does not discard work. Pricing chooses only the active family using industry, measurementMode and measureSource. `buildSavedHistoricalSnapshot` previously submitted *all* stored roofs, manual planes, Areas and Linear to the existing image endpoint; `drawSavedMeasurementLabels` likewise painted every family. Reopening therefore made inactive geometry part of the baked diagram even though pricing correctly excluded it. This was source-selection divergence, not duplicated database records, a changed total or a new pricing calculation bug.

## Narrow fix

Application commit **60ae098f7f2010dea2c9bbde767b0a35d3395f57** introduces a read-only projection following the existing server pricing selection:

| Priced scope | Diagram scope |
|---|---|
| Surface estimate with saved commercialAreas | Those Areas plus the separately saved, positively measured Linear |
| Area mode without multi-area scope | Saved Area only |
| Linear mode without multi-area scope | Saved Linear; legacy explicitly combined surface Area retained |
| Auto/google or adjusted | Selected structures |
| Auto/manual | Positive manual planes, otherwise existing structures fallback |
| Auto/hybrid | Structures and manual planes |

Historical image input, label painting, interactive report framing/rendering and PDF trace/reference construction use that active projection. Saved snapshots and previous revisions are never edited or sanitized in storage. No geometry, price, tax, customer field, rate or allowance is recalculated by a replacement engine. Existing validators reject incomplete/mismatched active service geometry before export/Print. The saved canvas records its active-scope fingerprint; PDF capture rebuilds a missing/stale historical canvas through the existing endpoint instead of trusting unrelated pixels.

No measuring controls, RETRACE interaction, PDF layout, imagery provider/API integration, database connection, credentials, account guards, pricing or subscription logic were changed. The request geometry is corrected; its provider and resolution remain unchanged.

## Tests and evidence

- New executable renderer regression first fails against the pre-fix app: request includes house/manual/area/area/linear instead of area/area/linear. It passes on the fix.
- Targeted test executes the actual historical renderer and label painter, captures the image-request bodies, verifies all five surface industries in Area/Linear modes, Roofing sources/modes, repeated rendering, immutable source snapshots, invalid area/quantity rejection, and blocked Single/Expanded/Vector/Print before capture.
- Existing six-industry saved editing, all-five-industry RETRACE targets/Cancel/line isolation, priced-roof overlap and Expanded proportion tests passed. The large visible-control suite passed after updating synthetic fixtures to state their actual Roofing scope and use calculated Area quantities; no safeguard was weakened to satisfy a test. Its prior empty/incorrectly typed snapshots are not valid customer estimates under the new guard.
- Full local regression: **79/79 commands passed** on the final committed source. GitHub application run41241456362 and recovery run41241456410 SUCCESS; recovery job124656051282 and disposable PostgreSQL16/18 jobs124656051141 /124656051267 SUCCESS. New test is included in the canonical recovery workflow.
- Recovery deploy **dep-dbj5esc9v7es7395qou0**, application **60ae098f7f2010dea2c9bbde767b0a35d3395f57**, verified LIVE at21:03:35UTC. Auto-deploy remains Off. Production still LIVE atc049a04 /dep-db5b726k1f9s73e862ug; main was not modified. No database/environment edits occurred.
- Post-deploy Cloud Chromium reopened the exact Commercial previous revision7: both Areas(6,125+7,508ft²),205.4ft Linear, branding/customer and$1,570.25 total match. Actual Single(1page) and Expanded(2pages) PDFs were downloaded, rendered and visually inspected: old orange Roofing outline/pitch/dimensions are absent; both purple Areas and teal Linear remain, Street View proportions/attribution and approved layouts are preserved. Subtotal$1,414.64 +GST$70.73 +PST$84.88 =$1,570.25, unchanged from before.
- Original Roofing previous revision1 reopened with its orange roof, confirmed22.6° pitch and7,348ft² /$815.67. Its actual Single PDF was downloaded/rendered/visually inspected and retains the roof without surface overlays. Saved history still lists the original revisions; no estimate Save or historical rewrite was performed in this live follow-up.
- Four actual PDFs(5pages total including the before-defect Single) and a before/after image are preserved with SHA256 manifest. All PDF visual inspection used actual existing authorized QA imagery, not synthetic grid images. This does not establish commercial imagery licensing rights.
- New live verification is desktop Chromium. Repeated industry switching/Area/Linear/RETRACE Save/Cancel, account/allowance security and geometry rejection are covered by the full controlled suite; they were not all repeated through live browser UI in this short batch. Physical iPhone/Safari/Messenger remains pending. No unrelated application defects were addressed.

Before evidence: `qa/pdf-active-scope-2026-10-31/commercial-reopened-single-before.pdf` and `before.jpg`. Earlier Expanded defect artifact remains in `qa/db-isolation-2026-10-31/pdfs/commercial-expanded.pdf`.

Only fictional QA data was used on the already isolated recovery database. No production/main/original paid DB action, schema migration, account reset, credential/configuration change, supplier contact or imagery licensing claim. Physical iPhone/Safari/Messenger verification is not inferred from desktop Chromium or DOM simulations.

The containing documentation/evidence commit is the final resume checkpoint; no deployment is needed for it. Continue only after owner review.
