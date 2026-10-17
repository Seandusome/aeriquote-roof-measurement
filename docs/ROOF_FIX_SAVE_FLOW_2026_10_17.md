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
Pending after deployment. Do not claim new live/PDF checks passed based on the local exporter regressions. Earlier live fresh-session diagnostics are described above; the actual new downloaded-PDF check remains pending.
