# Snow rate-field discrepancy — 2026-11-03

Resumed checkpoint 65512eed. Conclusion: the historical mismatch is reproducible with the cloud browser's fill action, but ordinary keyboard entry plus Tab or clicking away commits correctly. No application defect was reproduced through those user interactions. No application change or deployment was made.

## Evidence and failing stage

Same signed-in fictional QA job and unchanged live application efb2d29ba72306ef718c62f1de86070af1e33ef7:

| Action | Displayed rate | Preview rate | Result |
|---|---:|---:|---|
| Select all, ordinary sequential typing 0.10, Tab | 0.10 | 0.10 | Correct; CAD108.45 |
| Type 0.12, click customer field | 0.12 | 0.12 | Correct; CAD128.47 |
| Cloud fill 0.10, Tab | 0.10 | 0.12 | Mismatch reproduced |
| Retype same 0.10 after fill, Tab | 0.10 | 0.12 | Still mismatched |
| Type genuinely different 0.11, Tab | 0.11 | 0.11 | Correct; CAD118.46 |
| Type 0.10, click away | 0.10 | 0.10 | Correct; CAD108.45 |

A further cloud fill0.12 left field0.12 / preview0.10; this is recorded verbatim in `qa/snow-rate-2026-11-03/aq-snow-cloud-fill.json`. Ordinary typing restored the correct rate/preview. The rate input uses onchange to call commercialAreaField. Observable failure occurs between the cloud fill/blur sequence and committing the input into quote pricing. Keyboard input with a genuinely changed value reaches that handler; the original review began with fill and then retyped the same value, explaining why its follow-up was misleading.

This establishes an automation-specific reproduction, not the internal implementation of the cloud tool: its event dispatch is not exposed here. Do not claim that every possible human/browser input path was proved safe. Standard local Playwright fill+Tab also committed correctly, so the result is specific to the observed cloud fill path, not a general assertion about Playwright fill.

Live QA workspace was returned to the original Commercial industry, area rate0.27, linear0.25, total278.65. Customer and measurements preserved. No live estimate/revision was created in this batch; create count remained6. Only fictional QA workspace/draft interactions occurred. No real account settings or password changed.

## Disposable browser trace and regression

Added `scripts/test_snow_rate_browser.cjs` using the existing disposable loopback server, fictional accounts/providers and synthetic imagery. Final run used `scripts/job_revisions_browser_server.py`, which selects normal Basic allowance settings and removes complimentary bypass. No external database or imagery API was contacted.

- Two independently saved areas plus a saved line. Ordinary typing/Tab and typing/click-away passed with both Linear and Area active. Edit/Cancel preserved geometry.
- Browser event log records trusted input/change events; actual commercialAreas state, captureQuoteSnapshot, preview and displayed rates agree after commitment.
- Standard Playwright fill+Tab compared separately and passed.
- Blank and negative rates block Create and submit no estimate; geometry remains unchanged. Explicitly entered zero remains valid; final typed rates restored to0.10 and0.12. Existing explicit manual-rate and pricing safeguards unchanged.
- Captured POST bodies for the intentionally aborted request and successful retry. Both carried area rates0.10/0.12 and correct total178.14. Stored response and reopened quote retain the same rates/customer/measurements/total.
- Aborted save preserved the snapshot and blocked report opening. Retry succeeded.
- Both real PDF exporters ran after reopening. Single1page, Expanded2pages. All three final rendered pages inspected: intended rates, customer and total correct; both priced areas and line present. PDF export left stored geometry/pricing/customer unchanged. No uncaught browser errors or horizontal overflow.

Independent WGS84 quantity and Decimal arithmetic verifier passed. Area1:659×0.10=65.90; Area2:659×0.12=79.08; line62.04996065170652ft×0.25 rounds15.51. Subtotal160.49; GST5%=8.02; additional tax6%=9.63; totalCAD178.14. WGS840.6% tolerance is existing spherical geometry verification, not survey accuracy.

Commands (server and browser must share one execution/network namespace):

```sh
PYTHONPATH=/tmp/aq-snow-py python scripts/job_revisions_browser_server.py
NODE_PATH=/tmp/aq-snow-node/node_modules QA_BROWSER_OUTPUT=docs/qa/snow-rate-2026-11-03 node scripts/test_snow_rate_browser.cjs
PYTHONPATH=/tmp/aq-nov3-geodesic python scripts/verify_prelaunch_browser.py docs/qa/snow-rate-2026-11-03
```

Python dependencies are repository requirements. Node dependencies: Playwright1.56.1, Leaflet, html2canvas, jsPDF. Evidence includes event/state traces, actual save requests/stored payload, run/server logs, both PDFs, browser screenshots and rendered Expanded pricing. Local environment preparation initially lacked Flask/Chromium and required installing isolated dependencies; an initial generated-test string replacement was corrected before successful execution. Those attempts did not reach application assertions. Final focused run PASS, independent verifier PASS, JS syntax PASS.

## Preservation and pause

Application source unchanged: app.py blob50f3d4a7f7d87cd5c1ba8dadd07b7515c35df4a5, corresponding to live efb2d29b. Documentation/test checkpoint is the commit containing this report. Recovery auto-deploy OFF. Existing isolated QA binding unchanged: dpg-dbj4f7lg1s2s73eob8t0-a / aeriquote_recovery_qa. Main, production and customer data untouched. No deployment or new GitHub workflow run requested/started; no application fix required a full-suite rerun. Prior exact application workflows remain passing as recorded in resume notes.

Future QA should use actual key entry for this onchange-controlled field and assert displayed rate against preview/state before saving. Never trust a filled DOM value alone, and do not mask mismatches by manually calling application handlers. Manual desktop review and physical-phone testing remain pending. Original two untracked PDF copies preserved. Pause for Sean's next instruction; do not begin usability layout implementation.
