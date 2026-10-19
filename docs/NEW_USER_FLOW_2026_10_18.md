# New-user flow audit — October 18, 2026

Recovery branch only. Starting head e3a41d3f46bbfaf69e3e6cecd2d43538abd28b2f. Sean requested reviewing signup -> setup -> first saved estimate/PDF for all six industries, with plain language and obvious next steps. Payments remain deferred. Main, AI Trace removal, Roofing scope guard and 5/12 manual default preserved.

## Diagnosis before changes
Live public flow: signup did not show which industry was selected or explain the 8-character password requirement. Network failures had no usable retry feedback or duplicate-submit protection. The nine-screen setup allowed empty business information, repeated contact details, included an information-only screen and had US State options still listing Canadian provinces. Source audit additionally found missing contact-name/website/region IDs in Pressure, Paving and Landscaping, missing default-rate IDs in Pressure/Paving, and missing tax IDs and tax-mode values in Pressure/Paving/Landscaping. These values were disconnected from the shared save handler.

## Changes
Four setup screens: business (optional service/property selections collapsed), starting price + explicit tax rates, optional branding/message, review + Save & measure. Contact details hydrate from the signed-in account and flow into estimate contacts without repeat entry; late hydration respects current edits. Canadian provinces/territories and US states use canonical codes. Blank taxes require a value (0 when not charged); no location-based tax calculation is claimed. Final review shows actual business/location/rate/taxes. Validation/error/retry remains on screen. Account save precedes local cache and navigation; browser-storage failure cannot strand a successful signup. Signup confirms selected industry with Change and Log in links and explains password length.

## Verification
Local: 12 clean/legacy setup paths, six signup flows, duplicate clicks, failure/retry, country changes, late responses, values persisted by the real Flask signup/profile routes using isolated databases and actual shared-JS payloads. Public routes/assets/inline JS, 29-page accessibility checks, account access/isolation, six-industry wording and measurement edge regressions, and five-industry surface workspace tests passed. No measurement/PDF application code modified.

## Live verification and remaining scope
Application 2d9d0def105f2b7ad3aa51630f089c789fd6bdd3 deployed and recovery CI passed. Built-in browser walked all four setup screens in all six industries using clearly labelled QA input, stopping before saving to Head Office. Roofing: California/United States and 0% tax final review. Other five: Saskatchewan/Canada, $0.37/ft² and 5% + 6% tax final review. Required Company Name validation, automatic estimate contact preview and optional collapsed fields worked.

Live Landscaping first measurement on 2301 Ave C North #115: illustrative rectangle 10,107 ft² at $0.10, tax 5% + 6%, total CAD $1,121.88. Saved a labelled QA estimate, no customer correspondence. First attempt coincided with deployment and failed to rebuild the aerial; a fresh property load after rollout rebuilt the estimate aerial and dimensions correctly. The earlier failed QA version remains in history; no records deleted. Do not claim a confirmed cause beyond that observation.

Subsequent live PDF/all-industry estimate checks were interrupted by browser native credential-state protection. A documented fresh tab and runtime-reset recovery also failed. Do not repeatedly probe protected browser state. Remaining: live new-account signup (manual credential/terms step), first-estimate/live PDF checks in Roofing, Snow, Pressure, Paving and Commercial, fresh Landscaping PDF export, mobile visual QA. Yesterday's actual PDF visual pass is still valid evidence for yesterday's fixture, not completion of this new-user pass.

Follow-up aligns tax labels with country and clears stale rates when changing country. US exposes the single sales-tax field the existing estimate engine supports; Canadian second tax is not silently carried into US setup. Local tests cover this; final follow-up live visual check remains pending browser recovery.

Signed in securely to Head Office for measurement testing; do not save test setup over its profile. Actual new account creation in the live browser requires manual signup/terms acceptance; do not claim it was completed by automation. Isolated signup/profile integration tests are separate from live new-account verification.

## Resumed live QA — October 18, afternoon

Sean manually created the separate QA account in the built-in browser (Roofing signup). Signed-in Roofing setup was visibly confirmed; credentials were never read or copied. Company was labelled AeriQuote QA. This is ONE live new-account signup followed by all six setup flows on that account, not six separately created live accounts. Head Office was not edited.

All four setup screens were completed and saved for Roofing, Snow, Pressure, Paving, Landscaping and Commercial. Each reached the correct measuring workspace; business/contact/location/starting-price/tax values carried through. Roofing used CAD $1/ft²; surfaces $0.10/ft²; Saskatchewan, 5% + 6%. Later US/California Roofing setup check showed Sales Tax %, blank after country change, with the Canadian second field hidden; this last US check was not saved.

Fresh first-estimate previews and actual Single page PDF downloads were exercised in all six industries. Pages were rendered with Poppler and visually inspected. Roofing QA used an illustrative manual rectangle and assumed 5/12 at 1715 2nd Ave N: 1,790 ft², original pre-rounding total $1,987.15. It is NOT a verified customer roof measurement. The automatic scope mismatch correctly blocked the estimate before replacement. Source label was corrected from Google segments to traced segments for manually measured roofs. Roof guards and 5/12 default remain intact.

Surface area-only fixtures at 2301 Ave C North: Snow 20,788 ft²/$2,307.47; Pressure 17,325/$1,923.08; Paving 17,152/$1,903.87; Landscaping 16,372/$1,817.29; Commercial 17,463/$1,938.39 before rounding fix. These are illustrative QA shapes, not certified property measurements. Initial Landscaping and early Commercial mixed exports had blank Street View during deployment; do not mark those files clean. Fresh post-rollout mixed exports below show both aerial and Street View correctly. Deployment/restart interruption of in-memory imagery sessions is not fixed by this work.

### Live area + linear verification

Sean specifically asked whether both had been measured together. Initially only automated mixed checks had passed; the subsequent LIVE mixed pass covered ALL FIVE surface industries:

- Commercial: fresh post-rollout area 17,152 ft² @ $0.10 + line 535.3 ft @ $0.25. Displayed services $1,715.20 + $133.82; subtotal $1,849.02; taxes $92.45 + $110.94; total CAD $2,052.41. Single page PDF visually inspected, both geometries/dimensions and Street View present.
- Landscaping: area 16,372 ft² @ $0.10 + line 463.2 ft @ $0.70. Displayed services $1,637.20 + $324.27; subtotal $1,961.47; taxes $98.07 + $117.69; total CAD $2,177.23.
- The same saved area/line fixture was switched through Snow, Pressure and Paving using the visible Business Type control. Geometry, independent rates and combined total stayed intact. Labelled QA estimates were saved and actual Single page PDFs downloaded/rendered/visually inspected in EACH industry. Each had the correct industry heading, both outlines/dimensions, both service prices, aerial and Street View.
- Paving's CURRENT estimate was reopened from Previous Estimates > View History. It retained both measured quantities/rates and $2,177.23. The actual reopened Expanded PDF was downloaded, rendered and inspected: two pages, aerial+area+line first, measurements/pricing/marketing/Street View second. Other mixed versions were visible in history, not individually reopened in this pass. Existing versions were not deleted.
- Combined Roofing services remain a separate feature; Roofing uses its selected AutoMeasure/Area/Linear mode, as before. Do not claim this mixed surface test adds combined Roofing pricing.

### Fixes and verification

Application 33b7b4d571d28fff26c68c846d98bb5a84209125: Snow + ADD AREA label restored, redundant initial Pressure/Paving area-rate fields hidden in Area view, optional blank phone label hidden, manual roof pitch source made truthful. Render live; both GitHub workflows passed.

Application a41feda17a3d89c47b51201337985dbfca2bc29b: displayed taxes and total rounded to cents consistently for regular, discount and tax-included modes. Live 17,463 ft² Commercial fixture now displays $1,746.30 + $87.32 + $104.78 = $1,938.40 (previous $1,938.39 exposed the bug). Existing saved historical prices are preserved. Exact geometry/raw subtotal precision is retained; current monetary tax base/discount/taxes/total use cents. Added independent regression for fractional roof quantities, half-cent tax, discount, included and zero taxes; updated the engine's tax expectation. Surface workspace, six-industry wording/edges, actual DOM/Leaflet controls, public UI and compilation passed locally; BOTH GitHub workflows passed; Render deploy dep-dbahrv942hec73dl5mc0 is live. Fresh mixed tests above used this version.

Checked QA Expanded sample saved as AeriQuote_QA_Area_and_Linear_Expanded.pdf, Library identity libfile_4e99ca6660148191b9de75dc141b21ce. Local transient copy /workspace/scratch/AeriQuote_QA_Area_and_Linear_Expanded.pdf. No customer correspondence was sent.

Remaining: live mobile visual QA; six separate fresh live signup accounts have NOT been created (one shared QA account was used); deployment/restart image-session recovery remains a known watch item. Do not call the entire prelaunch audit complete. Main untouched; AI Trace remains removed; payments deferred.

## Unit addresses and image-session recovery — October 18, evening

Application 5a56a43bb9ca301859c098e1d37b21926aefb28c is live on the Commercial recovery service; BOTH GitHub workflows passed. Canadian explicit unit formats are normalized for lookup, while the customer's unit remains on the estimate. Ambiguous `115 2301 Ave C North` now asks whether 115 is the unit before loading. Street View uses the building address and retries ZERO_RESULTS once using verified coordinates. Ownership-scoped, expiring property metadata is retained in the database so a new process can rebuild image access; keys and image bytes are not persisted. Simulated process-restart, ownership, expiry, current-key rotation and image-route regressions passed.

Live browser checks: bare `115 2301 Ave C North` showed the intended confirmation; acceptance used `2301 Ave C North #115` and loaded aerial plus July 2015 Street View. A labelled QA area estimate (19,924 ft² at $0.10; subtotal $1,992.40; taxes $99.62 + $119.54; total CAD $2,211.56) was saved. The actual PDF was downloaded, rendered and visually inspected: unit #115, aerial, dimensions, Street View and pricing were present. This export was WITHOUT a server restart, despite the fixture's 'Restart Recovery' label. Independent live `115-2301 Ave C North` lookup also verified #115 and loaded both images without the ambiguity confirmation.

A controlled redeploy of the SAME commit was attempted to verify recovery across a real server restart. It DID NOT EXECUTE: automatic approval review failed because of a usage limit. Do not bypass that review using another deployment route or a documentation push that causes deployment. Live controlled-restart verification remains INCOMPLETE; simulated restart evidence does not replace it. Live mobile visual QA also remains incomplete. These notes are saved locally and deliberately not pushed while the deployment review is blocked. No changes to main, AI Trace or customer correspondence.

### Live restart follow-up — October 18, 14:04–14:06 Edmonton

Sean reported topping up usage and authorized continuing. The same-commit redeploy retry succeeded: dep-dbaicfqjnfac73fr17fg, app 5a56a43bb9ca301859c098e1d37b21926aefb28c, live at 20:04:56Z. Using the browser job loaded BEFORE this redeploy, without reloading the property, changed only the QA customer label and generated a NEW estimate after the replacement process was live. The new actual Single page PDF was downloaded, rendered and visually inspected: aerial, saved 19,924 ft² outline and edge dimensions, Street View July 2015, #115 address, $1,992.40 subtotal + $99.62 + $119.54 = CAD $2,211.56 all present. Property lookup counter remained 1. This completes the controlled LIVE restart recovery check for this Commercial area fixture. It does not imply all industries/exact-pin/roof sessions received independent live-restart tests. Mobile visual QA remains outstanding. The earlier approval failure is resolved for this retry.

## Phone/tablet follow-up

Read docs/MOBILE_VISUAL_QA_2026_10_18.md. Application 95d61058415f6cb9d89330b1b6d4a144e7b1df47 is live and both CI workflows passed. Fixed missing phone viewport, clipped header/account actions, phone fields/tools/report actions, moving aerial during first drawing points, tablet overflow, and unreadably tiny Single page PDF exports from phones. Six workspace layouts and six setup-to-review flows inspected at phone widths; signup inspected without creating another account. Live phone-width area + line saved and reopened, actual Single page and Expanded PDFs rendered/inspected. Physical touch/keyboard/device-specific download/print checks remain; this browser used fixed-width same-origin frames, not device emulation.


## Saved-estimate editing review — October 18, 15:30 Edmonton

Sean authorized testing edits to saved jobs across all six industries. Live Head Office sign-in was completed securely by Sean; use labelled QA records only and do not save over its profile.

### Reproduced and corrected

- Viewing a historical estimate restored the report but Back to Dealer View left no usable property session, address fields or measurement controls. ADD AREA demanded a fresh property load. The report now offers EDIT MEASUREMENTS / PRICE and explicitly restores an editable workspace.
- Owned POST `/api/estimates/<id>/editing-session` restores the selected saved geometry into a new persisted imagery session without Google geocoding/Solar calls or consuming a property lookup. Other owners and invalid version indexes are rejected. Existing estimate payload/revisions stay unchanged until the user creates an updated estimate.
- Restores industry, customer, notes, selected source, country, rates, tax/discount, all area/line/roof geometry and saved Street View. Current job/payment metadata is retained even when editing an older revision. New properties clear stale saved imagery/context. Report viewing itself continues to use frozen measurements/prices.
- Follow-up keeps the restored first area saved/active so Create Estimate is enabled, and restores Roofing source after its dynamic control exists. Deployed application c9f405b3512c02d942942ac5b44a25fa58fa84c1; both GitHub workflows passed.
- Live price entry exposed a stale saved-area row amount beside its changed rate, although summary/report calculations were correct. Follow-up refreshes that row on committed rate/name changes; regression checks its displayed amount.

### Actual live evidence

Opened current QA TEST - New user Landscaping - DO NOT SEND at 2301 Ave C North #115, Saskatoon, SK, Canada. Original 10,107 ft², CAD $1,121.88. Restored address, aerial, Street View and controls with property lookup counter zero. Dragging an area corner then Cancel restored 10,107 ft² and the original total. Saving the same corner correction produced 10,420 ft²; added second area 3,655 ft², total 14,075 ft². Added a three-point line of 246.6 ft. Independently changed rates by normal keyboard entry to $0.13/ft², $0.21/ft² and $0.75/linear ft. Entered QA internal notes and CREATE CUSTOMER ESTIMATE succeeded.

Saved report showed $1,354.60 + $767.55 + $184.94 = $2,307.09 subtotal; taxes 5% $115.35 and 6% $138.43; CAD $2,560.87 total. Linear amount uses the unrounded saved length, with displayed quantity rounded to one decimal. No customer correspondence or profile save. Earlier QA history was not deleted.

Line Edit/Cancel returned the original 246.6 ft and prices. The attempted drag did not visibly change the length, so do not claim a live changed-line Save pass. Actual changed-line Save/Cancel/tool-switch cases pass the DOM/Leaflet regression suite in all six industries.

### Verification and exact remaining scope

Local six-industry restoration test uses actual app HTML/Leaflet, saved fixture rates/geometry/customer/source, nine aerial tiles per job, Cancel, ready-to-create state, independent rate entry and stale-row amount fix. Isolated Flask tests verify ownership, version validation, unchanged history, metadata, no lookup usage and no provider call. Full measurement/roof guard/PDF regression suite and five-surface workspace tests passed. These tests are separate from live browser evidence.

At the first revised PDF download, the browser refused further observation due to native credential-state protection, then reset its kernel. Its suggested fresh-tab recovery failed. Explicit runtime reset and one clean tab retry also failed. This is browser tooling restriction, not evidence of an app outage or bot block. Do not repeatedly probe protected browser state or claim revised PDFs were downloaded.

Remaining LIVE for this editing pass: reopen the newly saved Landscaping revision and verify its figures/notes; real changed-line Save, tax edits and tool switching; the equivalent saved-edit cycles in Snow, Pressure, Paving, Commercial and Roofing; actual Single and Expanded PDF downloads/rendered inspection after edits. Earlier first-estimate/mixed PDF and mobile passes documented above remain valid for their fixtures, not proof of completion of this saved-edit pass. Roofing retains selected-mode pricing, underquoting guards, manual 5/12 default and no AI Trace. Main untouched.


## Continued code audit — saved-data integrity, October 18

Reproduced two further save defects with controlled actual-function tests. The old duplicate key used only address/customer/contact/area/total/notes, dropping edits to an extra-service description, saved area name, geometry or industry when the numeric total stayed the same. It now compares the complete save payload. Exact repeated payloads still skip; changed measurement/source/pricing/detail/image metadata saves.

A network/HTTP save failure was only logged, allowing a customer report to open without an estimate saved to history. Save now returns explicit success/failure, shows a visible not-saved/retry message, keeps measurements in the workspace, releases the in-progress guard and Create button, and stops report opening on failure. Successful retry updates the duplicate key only after the server accepts the save. This is not unsaved-draft recovery across refresh or browser shutdown.

New test_estimate_save_integrity.cjs covers unchanged-total edits, exact duplicate, Booked/payment preservation and failed-save retry. Actual DOM saved-edit restoration test also exercises failed HTTP save through showCustomerEstimate and verifies no report opens and retry is enabled. Full DOM/Leaflet measurement/roof/PDF regression passed after these changes with zero script errors. Both new tests run in recovery CI. Live verification remains blocked by the previously documented browser credential-state restriction; no additional live PDF or save-failure test is claimed.


## Live saved-edit completion and isolation audit — October 18, 15:40–15:58 Edmonton

Resumed at 79c3459f44b08ac4636e8161e2d42c8a49ac216e. Built-in browser worked immediately, signed in to Head Office. Used only existing labelled QA properties; no profile save, customer correspondence, account permission changes or customer record edits. No main/production edits; AI Trace remains removed.

### Live saved editing and PDFs

All SIX industries received a saved-edit/reopen check and actual Single page plus Expanded PDF downloads rendered with Poppler and visually inspected. Expanded fixtures have two pages. All illustrative QA outlines and assumed roof pitch remain unsuitable for customer quoting. Five surface-industry checks used successive revisions of the SAME labelled 2301 Ave C North #115 property; they are not five separate properties/accounts. Earlier QA versions remain in history.

- Landscaping: reopened the earlier 14,075 ft²/$2,560.87 revision and verified its internal notes. A genuine endpoint drag changed 246.6 to 437.7 ft; SAVE LINE CHANGES confirmed it. Areas 10,420 ft² at $0.13 and 3,655 at $0.21 retained. Line $328.30; subtotal $2,450.45, taxes $122.52 + $147.03, total $2,720.00. Final revised version reopened with all figures intact. Single/Expanded inspected.
- Snow: same geometry, zero taxes; total $2,450.45. Reopened and changed first area name to QA Snow parking area without changing the total; the name survived another reopen. Single page and reopened Expanded with custom name inspected.
- Pressure: saved/reopened, changed second-area rate $0.21 to $0.22; row immediately became $804.10. Linear tool retained both areas and $0.75 line rate. Subtotal $2,487.00 + $124.35 + $149.22 = $2,760.57; final revision reopened intact; both PDF layouts inspected.
- Paving: saved/reopened, changed second-area rate $0.22 to $0.23. Linear -> Add Area starts a new area draft and correctly blocks Create. Cancel retained both saved areas/line. Subtotal $2,523.55 + $126.18 + $151.41 = $2,801.14. Final revision reopened intact; Single and reopened Expanded inspected.
- Commercial: independent line rate $0.80 survived reopening, then changed to $0.85. Line $372.07; subtotal $2,567.32 + $128.37 + $154.04 = $2,849.73. Final current revision reopened intact; both layouts inspected.
- Roofing: existing QA TEST - Pinehouse save flow - DO NOT SEND retained two corrected, dealer-traced roofs (rounded display 1,673 + 4,466 ft²), assumed confirmed 5/12 and selected roof pricing. Changed $0.10 to $0.12; actual saved precision gives $736.72 + $36.84 + $44.20 = $817.76. Revised total survived reopening. Single/Expanded inspected with both outlines, edge lengths and pitch labels. Existing placeholder image choice retained; no Street View is claimed for this fixture. This does not resolve whole-building AutoMeasure coverage.

Some immediate successive downloads returned paths with no file in the browser shared directory. Those files are NOT evidence. Missing final Snow/Paving Expanded exports were downloaded again from their reopened revisions and actual pages inspected. Browser locator fill did not always commit onchange; normal keyboard entry followed by Tab was used to establish the live name/rate edits. No application defect is inferred from those tooling behaviours.

### Small UI defect found

Frozen historical report aerials could retain stale interactive outline buttons from the previously viewed report, including Roofing buttons over a surface report. Historical report opening now hides the outline-control bar and clears its target buttons, preserving the underlying editor DOM for future editable reports. EDIT MEASUREMENTS / PRICE remains the route to edit the saved job. Regression seeds stale Roofing controls and asserts they are hidden/cleared while a new saved aerial loads; existing live editing/roof/PDF checks run afterward. Local regression passed. Post-deployment live verification will be recorded below.

### Employee permissions and business isolation

Code review plus new scripts/test_business_isolation.py exercises the REAL Flask app against an isolated temporary SQLite database with two labelled QA owners and two labelled QA employees. This is not a live employee-login browser test. It proves: employees can save/view their owner's jobs; body dealer_id cannot choose ownership; another business at the same address creates a separate estimate; foreign estimate reads/revisions, job-status/payment/date writes, editing tokens and imagery are rejected; owner profile changes remain private while employees can read their own business profile; employees cannot change settings, manage logins or enter Head Office; cross-business disable does nothing; disabling the real employee immediately invalidates that session; anonymous API reads reject access. Image ownership is checked with both warm memory and cold persisted metadata. No real logins or permissions were changed. New test added to recovery CI.

Local checks passed: full actual DOM/Leaflet controls including all roof scope/pitch/PDF safeguards (zero script errors), six-industry saved editing, save integrity/retry, real Flask business isolation, existing account access, saved editing session, property-session recovery and compilation.


### Deployment and final live confirmation — October 18, 16:02 Edmonton

Application 07bfe71beab7530246b8a6cc42a9c1b75eb60071 is live: Render dep-dbak2jgae00c739sef3g, finished 22:00:24Z. Both CI workflows completed successfully: application run 39170254981 and recovery run 39170254980, including the new business-isolation test. The initial local ece1b4c commit could not push with shell credentials; the connected GitHub tool published the exact same tree as 07bfe71 using an expected-head lease. Local checkout aligned to the remote app commit.

Fresh browser reload after deployment: opened Roofing QA history, confirmed historical outline controls hidden; EDIT MEASUREMENTS / PRICE restored the workspace; created its report and verified normal Main/Added roof outline buttons returned. Then opened current Commercial QA history after that Roofing report: outline control bar remained hidden, zero stale target buttons, correct two areas/437.7 ft/$2,849.73. Actual new Single and Expanded PDFs downloaded, all three pages rendered and inspected with correct aerial, area/line labels, prices and Street View. No actual customer record or company profile was changed.

This completes the requested six-industry saved-edit/reopen/PDF pass at the scope listed above, plus code review/isolated real-route employee/isolation auditing. It does not claim separately logged-in live employee browser QA, six independent new accounts, verified customer roof shapes, whole-building automatic roof accuracy, physical-device checks, live payment tests or backup restore. Keep those broader prelaunch items distinct.


### Live employee QA continuation — October 19

User signed into the existing Shingle Guard owner account (not a newly created QA business). Signup correctly reported the supplied owner email already existed. Owner profile identity verified read-only; no branding/settings saved. User created `QA TEST - Permissions - DO NOT SEND` with login `sean@aeriquote.com`; active employee creation verified. Password was entered by the user, never recorded here.

Live employee session: EMPLOYEES, ADMIN DASHBOARD and profile/branding controls absent. Direct `/dealer-employees` shows Dealer Owner permission required; direct `/head-office/dealers` shows Head Office permission required. Employee Previous Estimates initially empty, whereas the earlier Head Office account had the six-industry QA history. This is visible account separation evidence, not a full foreign-ID live API audit.

Employee loaded 455 Pinehouse Drive, Saskatoon, SK (one lookup). Provider scope mismatch correctly blocked estimate creation. Saved one synthetic QA manual roof trace with assumed default 5/12; area 3,774 ft² displayed. Fixture `QA TEST - Employee Save Oct19 - DO NOT SEND`, internal notes explicitly synthetic/not a customer measurement. At $0.80, subtotal $3,019.48 + $150.97 + $181.17 = CAD $3,351.62. Employee saved the estimate, found its persisted row, opened versions, opened historical report, then restored EDIT MEASUREMENTS / PRICE without another lookup. Area, pitch and price retained. Changed rate to $0.81: subtotal $3,057.23 + $152.86 + $183.43 = CAD $3,393.52; created updated estimate. No customer correspondence sent.

Remaining: owner-session visibility of this employee job/revision; live employee-disable/session-revocation check; separately logged-in cross-business foreign-ID read/write/image rejection. Isolated real-Flask checks for those routes already pass, as documented above. No new employee PDF inspection claimed. All six-industry PDF checks from October 18 remain distinct evidence. Application code unchanged at 8530eba during this continuation. QA employee remains active pending owner follow-up.


Owner follow-up, October 19 14:33 Edmonton: successful owner session verified by EMPLOYEES access. Previous Estimates shows the employee-created QA job at CAD $3,393.52. VIEW HISTORY shows current CAD $3,393.52 and previous version CAD $3,351.62, both 3,774 ft² and the same explicit QA label/notes. Owner then disabled ONLY `QA TEST - Permissions - DO NOT SEND` (`sean@aeriquote.com`); page verified Disabled with ACTIVATE available. No real employee touched; QA estimate/history retained. Owner visibility and disable action now live-verified. An already signed-in employee session was not retained separately, so immediate live session revocation is still not claimed; that case remains covered by the isolated real-Flask regression. Separate foreign-ID live API/image checks remain outstanding.
