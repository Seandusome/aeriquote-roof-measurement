# Pre-launch reliability QA — October 27, 2026

## Scope and checkpoint

Started from GitHub 3c4e56303e1be1eb14c2c398ba136fbfa34a329b, tree 85645213a405b7e0c2e627e8198b49b1fdcc9a6f. Render test deployment dep-dbejakc9v7es73cjh890 was LIVE. Application and recovery runs40139995097/40139995133 both succeeded. Local maintenance had restored the earlier725472c-equivalent tree; restored exactly the three changed files and verified complete tree equality before testing. No important uncommitted source was overwritten. Generated Python caches were left alone.

**GitHub reports protected:false for the recovery branch.** Do not claim protection is enabled. Available GitHub connection does not expose administration writes. Recovery-only checkout, explicit files, complete-tree verification and expected-head publishing are operational safeguards, not GitHub branch protection. Owner must configure appropriate GitHub rules/required checks; no main settings were changed. Main was read only and remains c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a.

## Confirmed defects fixed

The beforeunload handler referenced `historicalMode`, a parameter local to showCustomerEstimate, as if it were a global. Actual Chromium navigation emitted ReferenceError; the handler could fail before requesting a warning for unsaved work. The old VM regression explicitly injected historicalMode:false, masking the real-page scope error.

Removed only the unavailable parameter reference. Existing loaded-property/nonempty-workspace and saved-fingerprint checks still decide whether to warn. No quote validation, measurements, pricing, provider integration or PDF rendering changed. Read-only history on a fresh page has no active property token and does not need a warning; an existing unsaved active workspace remains conservatively protected.

Batch A is saved on GitHub as d068dd7b02272d173055a171c1d8348b50f2f821 (local d9fcf61; tree f8bde323e5ed7c9dfb4d214102f277bd610f9206), after67/67 commands passed.

Regression was first made to fail by removing the artificial global: ReferenceError reproduced. With the application fix, unsaved geometry warns; successful saved fingerprints permit navigation; later customer edits warn; no-token and empty-workspace cases do not warn. This is a warning, **not crash recovery or autosave**. Deliberately discarding or a browser crash can still lose an unsaved draft.

### Batch B — property marker silently swallowed drawing corners

Real Chromium diagnostics proved an intended third corner hit the default Customer Property pin image instead of the map. The first four-click rectangle became a three-vertex triangle,330ft² rather than659ft² in this fixture. The existing server correctly checked the geometry it received, but could not know about the missing click. This is a genuine undermeasurement risk, not a pricing-calculator mismatch.

The pin is now a passive Leaflet marker (`interactive:false,keyboard:false`), preserving its position/image while allowing clicks to reach the map at their actual coordinates. Its former hover tooltip is no longer interactive; tooltip wording remains in the source. Provider/imagery layers, resolution, projection and measurement arithmetic are unchanged. Do not forward marker clicks by their marker centre: that would record the wrong coordinates.

The new browser assertion was first run against the old marker and failed at the third intended click (2 recorded versus3 expected). With the fix, every intended area/roof/line point is counted, all six industries/three widths pass, both rectangular surface areas have four vertices, and independent WGS84/Decimal checks validate the resulting saved snapshots. Existing surface DOM tests also assert the pin is noninteractive. No missing historical vertices can be inferred or automatically repaired; old jobs must be visually reviewed if their tracing appeared incomplete.

## Automated and independent checks

- Before and after each application batch:67/67 authoritative recovery workflow commands passed, zero failures. Final log includes geometry/client guards,70 client/server pricing fixtures, discounts/included taxes/recurring periods, manual pitch, automatic completeness/duplicate guards, empty area→Linear, failure/retry receipts, session expiry, account isolation, employee access, monthly25/75/200 rules, profile/logo restoration, saved editing, Single/Expanded and QA vector exporters.
- Targeted failure recovery regression now reproduces real lexical scope instead of inventing historicalMode. Existing incomplete/mismatched geometry remains rejected, with no silent repair or discarded valid saved data.
- Real local Chromium:18 industry/width combinations, six industries ×1440/390/768 pixels. Standard login with a fictional local account; real Flask routes and disposable SQLite; controlled property provider and synthetic labelled imagery; actual mouse drawing and buttons, customer input, pricing, POST save, new-page load and saved reopening. No real property/API/account was used.
- Five surface industries: two service polygons plus one line, including Add Area→Linear with no new points. Roofing: existing allowlisted QA manual trace, explicitly selected pitch and scope confirmation; ordinary AutoMeasure remains covered by fixture API/DOM regressions, not a fresh live provider result.
- All18 combinations save/reopen with matching totals/customer names, zero captured browser script errors and zero measured workspace horizontal overflow. Final surface fixture total is153.18CAD (Commercial163.52CAD with its separate linear default); manual Roofing79.30CAD. These are viewport emulations with mouse input, **not physical touch tests**.
- Aborted actual browser save request: no report opens, snapshot unchanged, normal retry saves. HTTP401/409/timeouts, concurrent requests, duplicate saves and credit deductions additionally pass controlled automated suites; no claim of live cloud network interruption.
- Independent GeographicLib2.1 WGS84 polygon/line checks and independent Decimal line/tax arithmetic passed for all18 saved browser snapshots. Geometry tolerance0.6% accommodates existing spherical versus ellipsoidal calculations plus quantity rounding; this is not survey accuracy or real-roof ground truth.
- Actual html2canvas/jsPDF downloads:16 PDFs (Single and Expanded for all six desktop industries; both layouts also Snow at390/768). Rendered all24 pages. Visually reviewed six Single pages, twelve desktop Expanded pages and representative phone/tablet pages. Ordinary Single is1page and Expanded2pages; quantities, company/customer, tax5%+6% and totals agree with saved fixtures. These use synthetic imagery, not Google/Nearmap ground truth. Pure manual report imagery responses are fixtures, so provider-baked roof-outline correctness is not established by this run.
- Separately completed the18-combination no-image workflow using the existing Without Images option. No image/PDF engine was changed.

## First-time experience findings — no speculative UI edits

The tested main sequence exposes property loading, Add Area/Linear (Trace Roof in manual Roofing QA), explicit Save/Cancel, per-area rates, customer fields, Create Estimate and PDF layout/download. The empty-area tool-switch dead end reported by Sean is fixed and now also user-confirmed. Two surfaces plus a separately listed line is intentional, not a missing third surface.

Existing generic Your Company branding is a configurable profile fallback, not proof of account leakage. The uploaded Commercial PDF cannot prove an industry-switch defect without knowing the selected industry. Do not rename approved labels or invent a tax/brand bug from that sample. Existing regional tax/profile tests pass; the new browser fixture deliberately uses SK5%+6%.

Watch items remain: technical users can inspect a fixture, but this does not substitute for an untrained contractor usability session. Very short/repeated vertices, overlaps, free jobs and rounding are covered by regression fixtures. Aerial-label overlap and generic address-mismatch wording remain documented polish issues; imagery/PDF paths were explicitly out of scope for modification. No new controls or feature development.

## Confirmed PDF issue deliberately not changed

At390px, the Expanded aerial page stretches horizontal proportions: numbered circular markers become wide ellipses and the synthetic square grid/diagrams differ from the1440/768px versions. Saved vertex coordinates, dimensions, quantities, taxes and totals stay consistent. Reproduced with controlled image data through the actual existing exporter; not a Google imagery quality inference. This needs a separately approved aerial PDF layout fix, because the instruction for this batch explicitly prohibits changes to existing aerial PDFs. Do not present this review as all PDF visual checks passing. Existing numbered leader/area label overlap remains visible too.

## Remaining limits and launch blockers

1. Configure/verify recovery branch protection with repository administration access; currently absent.
2. Obtain written licensing scope for Google/Mapbox/Leaflet display, tracing/derived storage, Solar general roofing and customer PDF distribution. See GOOGLE_LICENSING_CALL_2026_10_27.md. No legal permission is inferred.
3. Fresh authenticated deployed six-industry provider imagery/PDF and actual logo upload tests not performed here. Sean confirmed his fresh combined estimate opens; his uploaded Commercial PDF was visually inspected earlier, but it is not six-industry live coverage. Original stuck tab recovery remains unverified.
4. Physical iPhone/Android/tablet touch placement, drag/pinch/rotation, keyboards and native PDF/print unverified. Current matrix uses real headless Chromium with emulated widths/mouse.
5. Forced discard/crash has no draft autosave. Warning fix reduces accidental navigation risk but cannot repair an already executing old tab remotely.
6. Billing anchors remain account-anniversary provisional until trusted subscription periods are connected. No Stripe or purchases added.
7. No local PostgreSQL binary available. Current checkpoint's CI PostgreSQL succeeded previously; require the new checkpoint's disposable PostgreSQL CI before declaring final checks green. Live email delivery and simultaneous signup-versus-employee identity race remain outside this batch's new browser proof.

## Reproducing the optional browser harness

Use a disposable environment only. Install jsdom30.1.2/Leaflet1.9.4 for existing suites; Playwright1.56.1, html2canvas1.4.1, jsPDF2.5.1 and its Chromium for the optional browser script; Python app requirements and GeographicLib2.1. Set NODE_PATH to the chosen dependency directory if installed outside the repo.

Run scripts/prelaunch_browser_server.py on127.0.0.1:8765 (temporary SQLite and QA-only fictional identity, provider access fails closed), then scripts/test_prelaunch_browser.cjs. QA_BROWSER_IMAGES=hide tests fixture aerials; default none tests the existing no-image option. QA_BROWSER_OUTPUT chooses a scratch output directory; QA_BROWSER_WIDTHS and QA_BROWSER_INDUSTRIES restrict a matrix. Run scripts/verify_prelaunch_browser.py OUTPUT for independent quantities/pricing. Stop the temporary server afterwards. Never point these tests at deployed accounts; target URL is deliberately fixed to loopback.

Publishing must include the complete tested Git tree, not just changed files. Commit results/final CI/deployment are recorded in the resume document and final handoff.
