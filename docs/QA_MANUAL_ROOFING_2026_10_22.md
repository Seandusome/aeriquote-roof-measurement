# Manual-only Roofing QA checkpoint — October 22, 2026

Base: GitHub 68e6a8e440bbf0cfff9c161d0d58dfc288462978, tree 6fd61c973aca357c235461ebbdf781722144c9ad. Work only on landscaping-multi-area-recovery-oct11. No production, main or customer-account changes. AI Trace remains removed. Imagery licensing is NOT resolved by this development.

## Activation and reversal

Default OFF. Activation requires BOTH AERIQUOTE_MANUAL_ROOF_QA=1 and an explicit comma-separated AERIQUOTE_MANUAL_ROOF_QA_IDS list of authorized isolated QA business IDs. No query parameter, browser storage, subscription plan or industry alone can opt an account in. Employee sessions use their business ID. No deployed environment settings were changed. Never put paying/customer business IDs on this list. To reverse, unset the flag/list; AutoMeasure code and its internal `auto` mode remain in place.

## Implemented

For opted-in Roofing only, property preparation creates a `manual_roof_static` session after the existing geocode/coordinate checks. The existing nine-image, scale-2 wide aerial path is retained, with existing Static fallback. Imagery is staged before workspace replacement and acceptance/credit deduction. No Solar geometry or image fallback is allowed in that session. Its mode persists across worker/session recovery and saved editing session reconstruction.

Existing manual roof trace engine calculates each polygon's surface area from ground area / cos(pitch), stores independent points/pitch/surface quantity in manualPlanes, and sums surfaces for the existing pricing engine. Generic flat Area is not substituted. Internal `auto` continues to represent roof-surface pricing; no global mode rename/removal.

QA controls promote manual tracing, hide automatic entry/return/display controls, and provide individual Edit/Delete plus Add Roof Section/Garage. Each new trace or edit clears inherited pitch. Selecting a real pitch (including explicit flat/custom degrees) is required before Save. Edit keeps the saved polygon until replacement succeeds; Cancel keeps it unchanged. Drag handles edit corners; Start Over permits retracing. Invalid/self-crossing/overlapping areas fail; shared section boundaries are allowed. A final scope confirmation is invalidated by additions/edits/deletions. In-progress section drafts block estimate creation. Manual controls are removed when switching to another industry.

Server validation independently recalculates surface quantities and validates polygons/pitches. New manual workflow snapshots additionally require pitch confirmation for every section, overall scope confirmation, no automatic structures mixed into the manual-only roof quote, and no overlap. Old historical snapshots are not rewritten or migrated.

Automatic `/structure`, `/structure-mask`, `/locate-building` are guarded for manual QA; `/rgb` and `/mask` cannot access Solar for manual sessions. Existing non-Roofing Solar recovery is preserved. Saved manual estimate editing creates a manual session and cannot resurrect Solar recovery. PDF paths retain their original geometry, resolution and pricing behavior.

## Verification

New `scripts/test_manual_roofing.py`: actual isolated Flask routes and URL recorder; address and rural pin loading; QA/default-off/account isolation; automatic escape-route blocking; Static imagery failures/retries; persisted session recovery; five industry routing; independent spherical geometry plus analytic 6/12 slope factor; shared edges and detached garage; overlap/incomplete/invalid/unconfirmed rejection; real SQLite save/reopen and saved editing sessions. No paid API requests.

New `scripts/test_manual_roofing.cjs`: actual app DOM/Leaflet functions and controls with controlled network; section pitches, adjacency, garage, overlap prevention, edit/cancel/delete, snapshot, draft blocking, scope confirmation, zoom/pan invariance, customer estimate total, and real Single/Expanded PDF exporter entry points with controlled canvas/PDF sinks. These are emulated DOM/export tests, NOT authenticated live browser tests or actual downloaded PDF visual inspection. Existing complex-roof test harness loads the new guard helpers without weakening its assertions. Both new tests are in recovery CI.

Final full regression results are recorded below after completion. PostgreSQL concurrency checks also run in the recovery GitHub workflow's isolated PostgreSQL service; local PostgreSQL is unavailable in this runtime.

## Remaining limitations / next verification

- Connected Chrome has only logged-out QA login pages. No authenticated live workflow/PDF download was verified. No physical-device testing occurred.
- QA mode was not enabled on Render. A future explicitly authorized QA-only environment activation and sign-in are needed for live Google imagery and actual Single/Expanded PDF visual checks.
- Four-step manual flow cannot infer missing sections or pitch from a 2D aerial. Contractor scope/pitch confirmation is necessary; it cannot prove physical completeness. Trees, stale imagery and unclear roof boundaries still require on-site confirmation.
- Roofing Linear remains a separate selected estimate measurement, preserving prior pricing semantics; it is not silently added to roof-area charges.
- Unfinished drafts retain the existing refresh warning; they are not a newly implemented cross-refresh autosave feature. Completed saved estimates preserve their snapshots.
- Existing imagery and PDF licensing must be cleared independently before any commercial rollout. Do not claim that avoiding Solar makes Google Static imagery tracing/Leaflet/PDF use unrestricted.

## Final local regression result

63/63 recovery regression/check commands PASS on the final application tree, including both new manual tests, independent geometry, full pricing matrix, all six industries, imagery loading transaction tests, session recovery, saved editing, Single/Expanded exporter tests, monthly subscription boundaries, account isolation and interrupted/concurrent SQLite saves. `git diff --check` also passes. Dependencies were already installed; local venv has no pip, so installation is not counted as a regression test. No local PostgreSQL executable is available; PostgreSQL verification is delegated to the existing isolated CI job, not claimed as a local pass.

## GitHub checkpoint verification and wording follow-up

Initial manual workflow checkpoint eed1881b4704952425aec45f1bd5317acddd78f5 has successful GitHub runs 39852372243 (application validation) and 39852372402 (full recovery plus real isolated PostgreSQL concurrency/acceptance/period checks). A final QA-only terminology fix keeps the four-step manual instructions, Trace Roof label and hidden automatic controls correct when the existing industry wording updater runs. Outside manual Roofing the previously approved wording remains unchanged; targeted manual/industry-wording regressions cover this distinction.
