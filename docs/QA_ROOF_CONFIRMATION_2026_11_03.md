# Roofing pitch confirmation — November 3, 2026

Scope: the approved usability fix from checkpoint `21b3990c`, recovery branch only. Replace the small visible checkbox with a prominent **Confirm pitches and included roofs** action next to saved roof sections. Display saved section pitches in rise/run notation; show explicit unconfirmed/confirmed states and an actionable estimate-block explanation. Keep default 5/12 unverified until explicit section selection and final confirmation. Hide legacy automatic main-house controls in the manual-only flow.

## Implementation and safeguards

Saved sections show their actual saved pitch (including 0/12 flat), independently of the next-section selector. The explicit confirmation action revalidates section pitch flags and geometry. Its persisted internal field retains the existing draft/snapshot contract; no visible checkbox remains. Before confirmation the heading says **Roof confirmation required**, the summary does not call the pitch confirmed, and guidance names the exact button to use. After confirmation a checked state is shown. Beginning an edit, adding a roof, changing a saved pitch/geometry or deleting a section invalidates scope confirmation. Cancel preserves saved geometry/pitch and conservatively requests confirmation again. Reopening estimates retains the existing requirement to review and confirm the recovered workspace.

Pricing, geometry, server validation, save IDs, stale-edit protection, allowances and database connections are unchanged.

## Local verification

Passed: manual roof DOM/Leaflet workflow including blank pitch rejection, multiple pitches, flat section, detached garage, adjacent facets, overlap rejection, edit/save/Cancel, delete, confirmation invalidation, snapshot immutability, zoom invariance and both exporter save entry points. Passed six-industry pricing validation, blank manual rate profiles, exact user text preservation, saved editing restoration, industry wording and draft save retry safeguards.

## Publication and CI evidence

An initial oversized file transfer truncated app.py in remote commit `64107f0e`; it was never deployed. Corrected source `c4220b5f` matched tested local bytes. The compatibility drill then correctly failed because its immediate previous revision was the truncated commit. No assertion or workflow was weakened. Follow-up `48a935d8` adds explicit action-time validation and has the complete prior revision. App blob hash is `df0392f527e0e85e069554b5bd0c82d51efe0c41`. Earlier live QA PDFs were also republished in complete, hash-verified form, preserving their local original bytes.

Initial validated application source: `48a935d8fe2597f17e6d26684ca1461ec72337b2`. Required workflows all completed successfully on that exact source: application `41700491300`; recovery including PostgreSQL 16/18 and unchanged backup drill `41700491226`; browser `41700491245` (10/10 jobs). This source was deployed to recovery as an intermediate candidate; the final result below supersedes it.

## Boundaries

Only fictional isolated QA accounts/jobs. Auto-deploy remains OFF. Main, production and customer data untouched. The two existing untracked PDF copies remain untouched. Sean's manual desktop review and physical-phone testing remain pending. No old uncertain draft or promotional-pricing investigations.

## Live follow-up before final completion

Intermediate source 48a935d8 was deployed after all required checks passed; actual PostgreSQL metadata confirmed aeriquote_recovery_qa on PostgreSQL 18.6. Live restoration showed 5/12 saved pitch and Roof confirmation required with a valid $0.27 rate. Explicit confirmation worked; saving a 6/12 section invalidated confirmation and updated quantity to 7,584 ft². Attempting 9/12 then Cancel preserved exact rendered geometry and saved 6/12 pitch; returning to 5/12 restored 7,348 ft².

Two focused live findings were corrected before final completion: a remaining idle Google-main-house instruction, and the visible Add Roof path not refreshing its confirmation display until a map click. The validator blocked unfinished saves, but displayed confirmation and button state were stale. Final source efb2d29b refreshes the manual workspace immediately after entering trace and labels unfinished roof edits as Roof confirmation required. DOM and actual browser regression tests use the visible Add button. Final CI/deployment/live results are recorded below.

## Final result — complete; pause

- Exact final source and running recovery commit: **efb2d29ba72306ef718c62f1de86070af1e33ef7**. App blob hash: `50f3d4a7f7d87cd5c1ba8dadd07b7515c35df4a5` (verified against tested local bytes before publication).
- All required workflows completed SUCCESS on this exact source before deployment: application **41702397105**, recovery/PostgreSQL 16/18 **41702397163**, browser **41702396986**, **10/10 browser jobs**. No unresolved failure on final source. The earlier red runs are superseded; no backup/compatibility assertions changed.
- Final recovery deploy **dep-dbl3b5gae00c73cfdh50**, live at **2026-11-03T19:29:43Z**. Auto-deploy remains **OFF**. Immediately before deployment the recovery process asserted the exact isolated hostname/database. New instance **7b224** asserted exact final commit and connected read-only to **aeriquote_recovery_qa**, PostgreSQL **18.6**, host **dpg-dbj4f7lg1s2s73eob8t0-a**. No connection changes.
- Live Add Roof immediately sets confirmation false, disables estimate creation, clears the pitch selection and gives an unfinished-roof instruction under **Roof confirmation required**. After drawing four corners, attempting Save with blank pitch keeps only the original section and says to select/confirm pitch. Explicit 5/12 selection saves the new section; overall confirmation remains required. Confirming then deleting that second section again invalidates confirmation and preserves the original roof.
- Live saved pitch edit 5/12 → 6/12 shows 7,584 ft² and invalidates confirmation. Attempted 9/12 then Cancel preserves exact rendered SVG geometry and saved 6/12 pitch; Edit/Delete remain enabled. Returning to 5/12 returns the original 7,348.380392728047 ft² geometry/quantity.
- Saved fictional customer **FICTIONAL PITCH CONFIRMATION NOV3**. Read-only QA database evidence confirms one saved manual plane, 22.62° (5/12), `pitch_confirmed=true`, `roofScopeConfirmed=true`. No inactive added roof remains in the saved snapshot or PDFs.
- Real Single PDF (1 page) and Expanded PDF (2 pages) downloaded, rendered and visually inspected. Both show the original intended roof and preserve fictional customer/service text. Independently reconciled: 7,348.380392728047 ft² × $0.27 → **$1,984.06**; extra **$54.25**; tax base **$2,038.31**; 5% **$101.92**; 6% **$122.30**; total **$2,262.53**. Independent WGS84 surface 7,360.523762772878 ft² is within the documented 0.6% spherical/geodesic tolerance. This is not survey-accuracy evidence.
- Actual Previous Estimates → View History → current Open Estimate → Edit Measurements/Price preserves roof, rate and customer fields. Waited for the report overlay to close and restore to finish before asserting. The reopened workspace correctly shows 5/12, confirmation false, an actionable roof-confirmation explanation, no “pitch confirmed” in its unconfirmed summary, and a disabled estimate button. Explicit reconfirmation enables it again; no second estimate save was submitted.
- Screenshots of both states and the two PDFs are saved in `docs/qa/roof-confirmation-2026-11-03/` with reconciliation data. Latest QA workspace is acknowledged by recovery autosave and left confirmed after reopening, without another estimate save.

### Next session

Pause until instructed. Sean's manual desktop review and physical-phone/Safari/Messenger checks remain pending. The prior fresh-property manual-rate sequence remains separately pending. Do not reopen old uncertain draft or promotional-pricing sequences without a new instruction. Main, production, customer data, monthly allowance policies and database connection settings remain untouched. The two pre-existing untracked PDF copies are preserved.
