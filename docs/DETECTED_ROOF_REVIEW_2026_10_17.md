# Detected roof outline review - October 17, 2026

Read with RESUME_HERE_2026_10_16.md and CHECKPOINT_2026_10_17.md.

## Implementation
For flagged Roofing results with a valid detected boundary, Property Summary offers REVIEW DETECTED OUTLINE & PITCH alongside the existing manual Remeasure action.
- Copies the detected candidate into a draft; preserves the original roof and provider numbers until save.
- Draggable numbered vertices. Clicking the map does not append unexpected corners. Cancel and Remeasure remains available for a completely different boundary.
- Requires an explicitly selected verified pitch (rise/12 or custom degrees). No pitch is preselected.
- Requires separate full-boundary and uniform-pitch confirmations. Dragging a corner clears both; changing pitch clears pitch confirmation.
- Rejects crossed/degenerate polygons, missing/non-finite pitch and pitch outside 0 <= degrees < 80.
- Computes surface area from the reviewed ground polygon divided by cosine of verified pitch, replacing only the selected roof. It never scales the partial provider roof area.
- Retains label, building ID, previous provider area, review diagnostics, other roofs and the current job rate.
- Saved source: dealer_reviewed_detected_outline, boundary_confirmed, uniform_pitch_confirmed, pitch_confirmed and reviewed_ground_sqft. Summary/customer report use Dealer-reviewed detected outline / verified uniform pitch wording.
- Added unsafe roofs retain their candidate separately while their original unsafe provider area stays excluded.
- Estimates remain guarded until correction save. Existing live/historical/PDF guards remain.

## Limits
This is dealer correction, NOT verified automatic whole-building AutoMeasure.
It uses ONE verified uniform pitch over the selected outline. Mixed-pitch roofs cannot use this shortcut. Do not infer a full-building pitch from Google's partial unit or silently extrapolate.
The dealer must check that the detected outline matches the actual intended building. Exact Pinehouse building selection is not independently certified by this implementation.

## Verification completed locally
- Python compilation passed.
- Real DOM and Leaflet controls test passed, including a real marker drag event, confirmation reset, cancellation preserving byte-equivalent roof data, custom/missing/80-degree pitch rejection, crossed-outline rejection, independent analytical rectangle/slope area calculation, pricing/other-roof/count preservation, source snapshot and customer report wording, added-roof candidate retention and new-property reset.
- Existing controls regression passed without script errors, including prior saved-estimate/PDF safeguards.
- Six-industry measurement edge cases passed.

## Verification still blocked
The cloud browser rejects initialization with native credential state cannot be safely resumed. The documented recovery and runtime reset did not restore access. Do not use alternate credential extraction or bypasses.
This feature has NOT been verified directly on the deployed site or through an actual newly downloaded PDF. Do not claim complete live QA or ask Sean to retest until those checks can be finished. The saved seven-area estimate reopen was verified on the earlier readiness-fix application commit 47f4fdf; its new PDF download is also pending.
Recovery branch only; main/production untouched; AI Trace remains removed.
