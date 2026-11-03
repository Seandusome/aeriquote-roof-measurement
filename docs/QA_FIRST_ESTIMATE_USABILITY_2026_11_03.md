# First-estimate usability review — 2026-11-03

Review only, resumed from checkpoint 754fe24e. Application/live recovery remains efb2d29ba72306ef718c62f1de86070af1e33ef7, deploy dep-dbl3b5gae00c73cfdh50. Recovery service srv-db5a2g5ckfvc739fui70 reports recovery branch and auto-deploy OFF. Isolated QA binding remains dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa, PostgreSQL 18; no connection/configuration changes. Main, production and customer data untouched. No application code, deployment or workflow changes.

## Scope and completed path

Signed-in QA account qa-browser-oct31-2026@example.invalid. Started a separate draft, preserving pre-existing work. Used fictional customer names/emails on a real QA imagery address (2301 Avenue C North #115, Saskatoon). This was a contractor-perspective interface review, not a new signup or normal-plan allowance test.

Roofing: fresh property load → manually trace roof → explicitly select 5/12 → finish measurement → explicitly confirm pitches/included roofs → enter manual rate 0.27 → fictional customer → create estimate → download PDF → previous-estimate history → reopen/edit. Property lookup, tracing, confirmation gate, customer entry, estimate creation, reopening and download were reachable. The clearer confirmation action works; default pitch was not silently accepted.

Snow: drew and saved a 902 ft² area and 30.0 ft line, entered fictional customer, created/reopened/downloaded. Pressure, Paving, Landscaping and Commercial reused this property and saved geometry through industry switching, comparing each industry's tools, pricing and completion route, then created/reopened/downloaded. These are five comparison paths, not five independent first-property/first-measurement onboarding runs. Existing QA bypass was used; no new allowance claim.

| Industry | Useful existing guidance | Main friction observed | Create / reopen / PDF download |
|---|---|---|---|
| Roofing | Prominent pitch confirmation, visible 5/12 | Premature confirmation box; repeated instructions; “Pitch of Added Roof” for first roof; measuring/save controls separated from aerial | Completed |
| Snow | Area/linear examples distinguish tasks | Rates split between saved-area rows and job pricing; saved/draft/completed wording competes | Completed |
| Pressure washing | Driveway/patio versus gutter/fence examples | Same split pricing and long customer/create route; active Area mode changes which rate controls are visible | Completed |
| Paving | Driveway/parking versus curb/crack examples | Same split pricing; price shown under Review while editable area rate lives in Measure | Completed |
| Landscaping | Lawn/sod versus edging examples | Same repetition; “Per snowfall” remains an available price-period label in Landscaping | Completed |
| Commercial | Area and linear combination explanation | Area rate in Measure, linear rate in Price; shared history navigation complexity | Completed |

Downloaded PDFs are preserved in the evidence folder. This batch checks ability to obtain the PDF, not a renewed Single/Expanded arithmetic/outline integrity audit. Both layouts and full measurement safeguards retain prior evidence; no claim of fresh comprehensive PDF validation here. Roofing report displayed total CAD 2,413.37. The five surface comparisons displayed CAD 278.65 (902×0.27 +30×0.25 =251.04; 5%12.55 +6%15.06). Roofing display quantity is rounded; no new exact-geometry reconciliation was performed.

## Five recommended simplifications, in priority order

1. **One next action and one current blocker.** Lead with Load property, then trace/save, then roof confirmation where applicable, then price/customer, then Create/Download. Suppress premature later-stage warnings and consolidate repeated instructions into the current blocking explanation. Before any saved roof, the current confirmation box tells the contractor to review saved sections that do not yet exist. Keep all validation gates and explicit pitch confirmation.
2. **Put drawing and saving beside the aerial with task-specific labels.** First-roof language should describe the first roof, not “Added Roof”; use a consistent “Save roof section” action. Property loading immediately starts tracing, so the prominent button changes to Cancel Section before the user deliberately chooses a drawing tool. Keep useful area/linear service examples; keep Undo/Start over and secondary tools available without competing with the next action. Preserve geometry and Cancel safeguards.
3. **Use one authoritative measurement summary.** A roof quantity/status currently appears across the job bar, measurement list, saved-section panel, map labels, property summary, quote measurement and dealer calculation. Retain each priced section, pitch and included state in one clear list; keep detailed map dimensions accessible. Remove redundant instructions/status copies, not measurement evidence.
4. **Make Price the predictable place to review every rate.** Saved-area rate inputs are under Measure; some linear/job rate inputs appear under Price and depend on active tool mode. Show a clear rate association for each priced area/line and keep dealer coverage/gallons/branding secondary until needed. Narrow generic period labels to the relevant industry during a future approved change. Keep explicit manual-rate entry, taxes, period meaning and all pricing validation.
5. **Make finishing and reopening direct.** Previous Estimates → Open currently opens record details, then View History → Open Estimate reaches the report; editing adds Edit Measurements/Price. Make the destination clear and prioritize the current estimate, with history secondary. After creation, make Download the primary next action, with Print/New Property/Edit quieter. Replace “Dealer View” jargon and distinguish “measurement saved,” “24-hour recovery draft,” and “completed estimate saved.” Keep revision history, stale-edit protection and idempotent saving intact.

## Screenshots and evidence

Evidence directory: `qa/usability-review-2026-11-03/`. Original viewport screenshots preserve context; some files capture an earlier viewport immediately after an action, so filenames describe the review stage rather than asserting the exact instant of confirmation. DOM snapshots support current industry labels. No credential screenshots were saved.

- [Roofing: repeated instructions and premature confirmation](qa/usability-review-2026-11-03/aq-usability-roofing-confirmation.jpg)
- [Roofing report controls](qa/usability-review-2026-11-03/aq-usability-roofing-report.jpg)
- [History Open record details](qa/usability-review-2026-11-03/aq-usability-history-open-detail.jpg)
- [Snow tools](qa/usability-review-2026-11-03/aq-usability-snow-tools.jpg)
- [Snow customer/create route](qa/usability-review-2026-11-03/aq-usability-snow-pricing.jpg)
- Pressure/Paving/Landscaping/Commercial measure-price screenshots and DOM text are alongside these, plus six downloaded PDFs.

## Separate concern and limits

Snow area-rate field displayed 0.10 after fill and ordinary sequential typing + Tab, while preview continued using 0.27. Cause is unverified: application update versus automation/event behavior was not established. Restored displayed input to 0.27 before saving, so no deliberately inconsistent estimate was created. Do not claim a confirmed pricing defect or change application behavior from this review. Next diagnostic batch should capture a real input/blur/change sequence and request/preview evidence before proposing a fix.

No fresh accounts, failed-load cases, session recovery, allowance enforcement, full PDF integrity audit, physical-phone testing or owner desktop review were added. Existing assertions/safeguards unchanged. No CI run started or rerun; prior exact efb2d29b workflows remain reported passing: application41702397105, recovery41702397163 (PG16/18), browser41702396986 (10/10).

## Resume — pause

Documentation-only checkpoint is the commit containing this report. Live stays efb2d29b; auto-deploy OFF. First next task, after authorization: validate the Snow rate-field/preview discrepancy in a tightly scoped QA reproduction. Then review the five recommendations before any layout implementation. Owner desktop review and physical-phone testing remain pending. Do not resume old uncertain drafts/promotional cases automatically. Two pre-existing untracked PDF copies remain untouched.

## Follow-up diagnosis (later November 3)

The separate Snow concern above was traced to the observed cloud fill/commit path. Ordinary typing with a genuinely changed value, Tab and clicking away passed; disposable active-state/save/reopen/both-PDF verification passed. No application change. See [focused diagnosis and limitations](QA_SNOW_RATE_DIAGNOSIS_2026_11_03.md). This follow-up supersedes the earlier unverified status without changing the original observations.
