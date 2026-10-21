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

## Live validation — complete for interface
Application 84f00483293e0ae6a91f1eb2bf854245eda17f0f is live. Both GitHub workflows passed. Built-in browser verified all five industry views retaining two independently priced areas plus a saved line. Commercial's separate linear rate was also exercised. Fixtures: 21,830 ft² at $0.20; 14,077 ft² at $0.40; 348.0 displayed linear ft at $0.70; total CAD $11,366.85. These are illustrative QA polygons/line, not verified customer measurements.

Created the labelled QA TEST - Surface workspace - DO NOT SEND Snow estimate, verified all three items, imagery and total in preview, then reopened the saved estimate from history with quantities/rates/total intact. The earlier Seven Areas QA version remains in history. No customer correspondence, dealer-profile save or record deletion occurred.

On final 84f0048 rollout, verified Drawing badge uses the current draft, progress stays on Measure and summary says Save measurement until saved. Redundant global rate fields disappear when saved-area rates are authoritative. Saved 21,830 ft² plus 348.0 ft at $0.10 each produced CAD $2,461.76. Line Extend -> Start Over -> Cancel and Area Edit -> Start Over -> Cancel each restored original saved quantities and total. Line controls were disabled during area editing; estimate remained blocked until Save/Cancel. Empty second draft showed Drawing: 0 without pretending the saved total was its size. Roofing regressions and safeguards passed; main untouched, AI Trace remains removed.

Actual live PDF visual verification completed October 17: downloaded the saved Snow QA estimate in Single page and Expanded layouts, rendered the actual PDFs with Poppler and inspected all three pages. Satellite imagery, two outlines and edge labels, 348 ft line, independent item rates and CAD $11,366.85 total match the saved estimate. Expanded layout has aerial/numbered areas on page 1 and complete measurements/pricing on page 2, correct page numbers and no clipping or displaced outlines. Earlier download file-access limitation did not recur. This verifies this two-area-plus-line QA fixture, not a new seven-area or Roofing PDF test. No application code changed.
