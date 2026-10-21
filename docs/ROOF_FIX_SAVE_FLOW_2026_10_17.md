# Roofing Fix / Save flow — October 17, 2026

## Diagnosis
Live built-in browser reproduced refresh -> reload 455 Pinehouse Dr -> add right-hand second building -> Fix Roof restoring the original 4,586 ft², 21-corner detected candidate. This established provider-candidate reloading, not resurrection of a discarded manual trace. A saved replacement reopened with its saved boundary in a separate live test. Sean subsequently saved the second roof (5,638 ft²) but could not find another Save and could not create an estimate because Main House remained flagged. Correcting Main House unlocked his estimate.

## Change
- FIX ROOF starts an empty targeted manual replacement for an unverified provider roof. It does not automatically restore the unsafe detected candidate. Manual pitch still defaults to 5/12. Existing overlapping saved manual traces retain the explicit boundary-review/replacement-confirmation route; they are never silently duplicated or deleted.
- EDIT ROOF retains the saved corrected boundary. Underlying detected-outline review remains available internally and its safety checks remain intact.
- Corrected roof rows explicitly say Saved in this job — no additional roof Save needed.
- A short message beside Create Customer Estimate names the outstanding roof(s), identifies the current edit or explains how to create the completed estimate. It distinguishes current-job measurements from a completed saved estimate and hides for all surface industries and Roofing Area/Linear.
- No geometry calculations, pricing, provider thresholds, estimate/history/PDF guards, source wording, main/production or AI Trace changes.

## Local checks
Python compilation; real DOM/Leaflet controls suite (zero script errors); all six measurement-edge and industry-wording suites passed. New assertions exercise clean Fix, targeted Save, saved-outline re-edit, saved second roof plus blocked Main House, cancellation preservation, named guidance, readiness restoration and hiding guidance on other industries.

## Live checks
Application 14648260e89cf5c9a08f4cc6a135d434723c8929 was verified directly on the test site after rollout. Both GitHub workflows passed. The live main and added-roof scope guards remained blocked. The second roof Fix opened a clean manual trace at 5/12 with disabled Save until points were placed. Saving an illustrative four-corner QA trace produced 4,466 ft² and the new saved-in-job label. Edit reopened that same four-corner boundary (4,123 ft² footprint), not the original 21-corner detected candidate; Cancel preserved the saved 4,466 ft². Guidance named Main House as the remaining estimate blocker. A separate illustrative main-roof QA trace at assumed 5/12 saved 1,673 ft², preserved the second roof and unlocked the estimate. These polygons/pitches are QA fixtures, not certified customer measurements.

Created QA TEST - Pinehouse save flow - DO NOT SEND. Estimate: 6,139 displayed ft²; CAD $613.93 subtotal, $30.70 GST, $36.84 provincial tax, $681.47 total. No customer messages or profile saves. Expanded PDF button completed and the browser download API reported a path, but the file did not exist in either the browser runtime filesystem or synchronized scratch after the allowed wait. Actual PDF pages could NOT be rendered or visually inspected. Do not claim full PDF QA; this remains pending due download file access. Render connector lacked a selected workspace, so rollout was verified through actual new UI behavior rather than dashboard deploy status.
