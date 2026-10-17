# Roof retrace and Roofing wording fix - October 17, 2026

## User feedback
Sean's 813958173.jpg showed a solid manual outline underneath the numbered dashed review candidate on the second building. He had rejected an earlier trace and retraced it. Roofing tool examples still said Lawns / driveways / parking and fencing / curbing.

## Findings
Review always loaded the original detected candidate, even when a later manual boundary existed. Existing manual display layers stayed visible beneath the review. Separately, deleteLastPlane removed just two Leaflet layers although each plane also had its polygon, pitch label and edge/corner labels, so stale drawings could survive undo. The screenshot alone cannot establish which saved data rows existed.

## Changes
- Review uses the selected roof's current replacement draft, latest matching saved manual trace, or saved corrected outline before the original detected candidate.
- A corrected saved roof exposes REVIEW SAVED OUTLINE & PITCH; a flagged roof with matching saved manual traces exposes REVIEW LATEST MANUAL TRACE & PITCH.
- Review hides saved manual display layers and the selected structure's normal overlay, so one draft is edited. Cancel restores saved data/displays.
- If saved manual traces overlap the selected roof, review lists their M numbers and quantities. Saving requires explicit confirmation to replace those traces with one reviewed roof. Cancel does not remove them; unrelated manual planes and other roofs remain.
- Corrected source is dealer_reviewed_trace when the dealer's latest boundary is used; source is not mislabelled as automatic/detected.
- Generic Add Missing Roof cannot add parallel measurements while a roof is flagged: the user is directed to the selected roof's Property Summary remeasurement control.
- Undo manual plane rebuilds all manual layers from remaining saved planes rather than popping two layers.
- Roofing examples: Roof footprints / flat areas; Gutters / eaves / ridges. Area copy explicitly says footprint measurement does not adjust for pitch; AutoMeasure roof correction is used for pitched roof area.
- Estimate safeguards remain. No main/production edits; AI Trace remains removed.

## Completed local verification
Python compilation; full controls regression without script errors; all six-industry measurement edge cases; all six-industry wording/estimate/switching/custom-marketing tests.
Added real DOM/Leaflet regressions for rejected trace ALL-layer removal; latest saved/draft trace selection; one visible editing layer; cancel restoration; independent explicit same-roof duplicate replacement; unrelated roof/plane preservation; saved-outline re-review; Roofing-specific tool descriptions.

## Still pending
Direct browser and actual new PDF download QA remain blocked by the native credential-protection runtime error described in DETECTED_ROOF_REVIEW_2026_10_17.md. Do not claim these live checks passed. Whole-building automatic/mixed-pitch accuracy is still not established. This is dealer correction with verified uniform pitch.

## Follow-up: repeated Remeasure while already editing
Sean reported that repeatedly clicking REMEASURE THIS ROOF left the active outline in place. The handler previously rejected all active trace/review modes. Clicking remeasure for the SAME target now cancels its draft/review and starts an empty replacement trace, clearing all old handles and draft layers. It still refuses switching to a different roof mid-edit. The active selected-roof row reads RESTART THIS ROOF TRACE. Estimate creation is disabled throughout replacement editing, including already-valid saved roofs, and Cancel restores the prior saved readiness/display. No saved measurements are deleted on restart.
The added DOM/Leaflet test repeats restart three times, checks every removed layer against the actual map, restarts from draggable outline review, verifies pitch confirmation reset, and verifies both saved roofs remain byte-equivalent. Full controls regression and Python compilation passed locally. Live browser/PDF verification remains blocked.
