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
