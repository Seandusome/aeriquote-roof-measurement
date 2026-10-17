# Surface measurement workspace simplification — October 17, 2026

## Scope
Landscaping, Snow Removal, Pressure Washing, Paving & Sealcoating and Commercial Properties share the same simplified flow. Recovery branch only; main/production untouched. Preserve Roofing, industry headings, aerial width/imagery, multi-area and linear geometry, independent rates, combined pricing, estimate/history/PDF behavior and all scope guards. AI Trace remains removed.

## Interface
- Keep two familiar toolbar choices: Add Area and Linear, with existing industry examples.
- Hide the duplicate Measurements for This Job summary on surface industries. One labelled saved-area list shows names, quantities, per-area rates, amounts, saved-in-job state and Edit Outline / Remove Area. No empty draft row is presented as saved.
- Show the area editor only during drawing/editing, with Save Area / Save Area Changes and Cancel. Start Over clears only the draft and Cancel restores an edited original.
- Saved lines have one Edit Line action. Extend Line and Remove Line move under More line options. Saved lines remain visible beside saved areas across tool views. Active line drawing has Save Line, Cancel, Undo and Start Over; drag edits retain Save Line Changes / Cancel Line Edit.
- Invalid/empty outlines and zero-length lines have disabled Save and visible instructions. Unfinished drawing/editing blocks estimate creation; guidance beside Create Customer Estimate names the required Save/Cancel step. Completed quantities are labelled saved in the current job, distinct from saving the completed estimate.
- Cancel an area draft without losing other areas/line; cancel a line extension without losing its original geometry or rate. Entering Linear from another view restores its saved rate, separate from area rates. Roofing restores its existing controls with no duplicate nodes.

## Local validation
Python compilation; shipped inline-JavaScript parsing; full DOM/Leaflet controls regression (zero script errors); all six industry measurement-edge and wording/estimate tests; multi-area recovery and rendering checks; analytical landscaping engine tests passed. New scripts/test_surface_workspace.cjs exercises all five surface industries through actual buttons: Save/Cancel, area edit -> Start Over -> Cancel preservation, no empty saved rows, names/rates, area+linear totals, saved line options, extension cancellation, draft protection and restoration of Roofing controls. CI now runs the new suite.

## Live validation
Initial application 9f7875c was verified live: clean Save Area / Cancel drawing controls, compact saved rows, a cancelled second-area draft retaining the first, normal keyboard changes to area names and independent rates, two areas plus a saved line, Edit Line / Cancel restoring the same length and total, and industry switching across Landscaping, Snow, Pressure Washing and Paving retaining all quantities and prices. Commercial and final follow-up rollout checks still pending. QA fixtures: 21,830 ft² at $0.20; 14,077 ft² at $0.40; 348.0 displayed linear ft at $0.70; total CAD $11,366.85. These are illustrative QA polygons/line, not verified customer measurements.

The follow-up corrects misleading draft display: the active area badge shows the CURRENT drawing, the job summary says Save measurement and progress stays on Measure until saved. It also hides redundant global area-rate boxes once saved areas have their own rates, and hides the duplicate Commercial job-rate card while using its separate linear-rate input. Local controls and five-industry workspace tests passed after this follow-up. Both GitHub workflows passed on 9f7875c.

Earlier actual PDF file-inspection limitation remains: browser download event completed but returned file was inaccessible for rendering. Do not describe new PDF pages as visually verified.
