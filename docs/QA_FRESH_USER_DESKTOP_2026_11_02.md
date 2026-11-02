# Fresh-user desktop readiness — November 2, 2026

Starting checkpoint: `8e956dcd9b0a49a256982cdf1ff5ca78133650f7`. Recovery remains on `69ab066c67cb429d4e12c8dad2d902140fbbc405`, deployment `dep-dbke60u1egvs73cafea0`. Auto-deploy OFF. No deployment is authorized for this batch.

## Scope and isolation

This batch selects a distinct case: actual fictional signup and four-step Paving onboarding with **I set each job’s rate**, followed by the first mixed area/linear job. Earlier browser baselines injected an existing account/profile and rates. New signup and allowance tests use a disposable loopback-only SQLite database with synthetic imagery; no live account, customer, subscription or payment integration is changed. The existing policy adapter disables SQLite's demo allowance bypass by supplying a non-network marker and a local DB adapter. Normal trial and paid-account allowance functions still execute. PostgreSQL 16/18 integrity jobs independently run the established charged-save/database regressions.

The recovery service and dedicated QA PostgreSQL configuration remain unchanged. No main, production, customer data, account settings, imagery integration, allowance policy or database connection is modified.

## Reproduced defect and narrow correction

Onboarding stores `pricingMethod: manual, price: 0`. The measurement screen ignored the method: a blank-intent manual profile populated a numeric zero, and saved service areas inherited it. Existing deliberate-zero validation consequently allowed a zero-dollar quote without an entered rate. Pressure Washing instead substituted its default rate. Before-fix DOM reproduction: rate `0`, saved-area rate `0`, total `0`, pricing error empty, Create enabled.

The correction leaves a manual profile's default/job/linear rates blank and preserves that missing value when adding areas, switching measurement tools or starting another property. Existing validation supplies the instruction and blocks incomplete quotes. An explicitly entered zero remains allowed. Rates, quantities, tax arithmetic, allowance rules and saved-estimate validation are not relaxed.

Six-industry DOM coverage verifies blank fields, blocked quotes after measurement, and explicit-zero acceptance. Existing surface workspace controls/rate independence also pass locally. Application source changed once; later commits correct only the new browser fixture and strengthen its checks.

## Browser and regression evidence

Final tested application/source commit: `3344821509fd3ef82c37cbacdfed04d1fbc88140` (not deployed).

- Actual fresh signup → missing-region correction → four-step business setup → synthetic property load → two native-click measured areas plus a saved line → manually entered rates/customer details → successful first save → fresh history reopen → actual Single and Expanded PDF downloads: PASS at desktop width 1440.
- Missing per-job rates and tax 101% block Create, show field-specific instructions and create no estimate. Correcting tax preserves measured areas, line and customer name. Explicit-zero acceptance is additionally covered across all six industry profiles in the DOM regression.
- First saved state: exactly one estimate, zero revisions and one estimate-save receipt, separately counted from lookup receipts. Fresh account is a normal trial, complimentary false, initial lookup count zero.
- Three accepted trial lookups succeed; fourth returns the normal limit warning and retains the existing snapshot/customer/job. The test closes the normal account-history dialog before continuing. A disposable paid Basic account at 24/25 keeps 24 after aborted imagery, shows retry and retains the snapshot; successful retry reaches 25 once; the next attempt stays capped at 25. Estimates remain one. No live bypass used.
- Separate local disposable-policy probe confirms prepare alone does not charge, repeat acceptance is idempotent, trial 0→3 then 403, paid 24→25 then 403, zero estimates created. See `disposable-policy-checks.json`.
- No uncaught browser errors or horizontal overflow. The unchanged property-failure browser suite additionally executes provider 503, failed imagery and expired acceptance cases at desktop/phone-sized widths. Physical device testing is not implied.
- Source snapshot, both PDFs, desktop screenshot and successful browser transcript are in [the evidence directory](qa/fresh-user-desktop-2026-11-02/). Single: one page. Expanded: three pages. All four pages rendered and visually reviewed; geometry labels include both 659 ft² areas and the 62.0 ft line; customer/business details match. Both quotes show 65.90 + 65.90 + 6.20 = 138.00, 5% tax 6.90, 6% tax 8.28, total CAD153.18. The assessment placeholder is expected for the chosen image policy.
- Independent WGS84 geometry and Decimal arithmetic: PASS (`independent-checks.txt`); existing spherical measurements remain within the documented 0.6% WGS84 tolerance, not survey accuracy. Browser captures verify PDF exports do not mutate stored geometry/pricing/customer/branding; Expanded imagery proportions are checked.

Required workflows all PASS on exact final source `33448215`:

| Workflow | Run | Result |
| --- | --- | --- |
| Validate AeriQuote application | 41518595816 | PASS |
| Validate landscaping recovery | 41518595807 | PASS, full recovery and PostgreSQL16/18 |
| Isolated browser crash and recovery QA | 41518595902 | PASS, all nine jobs including fresh-user |

`ci-results.json` records exact final commit, jobs and results. No unresolved failure remains on this final source. Earlier fixture-only runs are superseded by these successful complete workflows.

## CI fixture failures tracked directly

- `41518241524` fresh-user job: SQLite boolean returned numeric `0` against strict `false`. Fixture now emits an actual boolean. Count queries separately exclude prepared/accepted lookup receipts when asserting estimate-save receipts.
- `41518372659` fresh-user job: trial-limit BACK TO MY ACCOUNT correctly opened the estimate-history dialog; the new test attempted another property click without closing it. Fixture now clicks the visible CLOSE button. No application protection or assertion was weakened.
- Invalid-tax controls are opened using the visible dealer-settings summary before editing.

## Pending / handoff

No changes from this batch are deployed; the manual-pricing correction needs a separately authorized recovery deployment and live verification after review. Owner manual desktop review and physical-phone/Safari/Messenger testing remain pending. Disposable synthetic providers establish application recovery and allowance behavior, not external imagery provider availability or payment integration. Stop after checkpointing this batch.
