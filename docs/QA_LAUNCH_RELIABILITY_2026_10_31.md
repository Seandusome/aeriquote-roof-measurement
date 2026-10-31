# October 31 launch reliability batch

## Outcome and confirmed defects

Work stayed on `landscaping-multi-area-recovery-oct11`. Starting checkpoint: `b4e69d4`. No production, main, real accounts, imagery integrations, approved PDF designs, plan prices or allowances were changed.

1. **High: duplicate billable roof footprints.** A crafted snapshot could bypass client QA flags and bill the same footprint twice through mixed automatic/manual structures or duplicate manual planes. An isolated route accepted $2,105.12 where the single footprint cost $1,052.56 including 5% and 6% taxes. Commit `e9edb235236a8a09874a0c90a54fb680b732e490` validates the actual priced roof scopes server-side and blocks unsafe client quote/PDF/Print paths before capture. Shared edges and detached roofs remain valid. Existing historical records are not rewritten or deleted.
2. **High accuracy risk: tiny-polygon numerical cancellation.** Independent testing found the server reference returning 2.015244263 ft² for a polygon independently measuring about 2.519765 ft². Commit `764f1ff67d1d86f53fdefb44b28182ae8cc6dbbf` evaluates the same spherical formula stably; it does not change the Earth model, units, tolerances, saved geometry or client measurement engine. No claim is made that a real customer received this incorrect estimate.

Both fixes are independently committed and live on the recovery test service.

## Verification

- Complete local regression suite: **78/78 commands passed** after both fixes.
- GitHub regression and PostgreSQL jobs passed on both fix commits. Latest application commit: validation run `41226577977`; recovery run `41226578063`; PostgreSQL job `124611878682`; recovery job `124611879016`.
- Deterministic adversarial seed 10312026: 1,200 independently checked polygon cases, 72 successful all-industry estimate API cases, 276 rejected manipulations, 60 selected-Area revision/stale-conflict cases. WGS84 comparisons differ by at most 0.449538% area and 0.343963% length, reflecting the unchanged spherical model; this is not survey certification.
- Roof-scope targeted API tests: 12 attacks rejected, 11 valid adjoining/detached/ignored-cache scenarios accepted. Rejections preserved existing estimates, revision history and usage.
- Actual isolated Chromium: 18 complete create/save/reopen workflows across six industries at 390, 768 and 1440 px; 36 Single/Expanded downloads. One additional 390 px roof case proved flag-stripped duplicate geometry blocks PDF and Print before capture without changing the saved record; the original fictional fixture then produced two further PDFs.
- Independent browser-source WGS84/Decimal verifier passed all 18 baseline cases.
- **38 actual PDFs, 69 rendered pages visually inspected.** All 36 baseline PDFs carried the expected branding. OCR matched totals in 34; full-page visual review confirmed the other two totals ($153.18 paving, $79.30 roofing). Image-based PDF text extraction is not an application failure. Existing Expanded marketing continuation pages/white space were retained rather than redesigned.
- Browser and PDF tests used clearly marked fictional imagery on loopback and temporary QA databases. Street View was deliberately unavailable in this fixture. They do not establish live-provider quality, real-property alignment, physical iPhone, Safari or Messenger reliability.
- Current batch browser input was mouse-driven Chromium viewport emulation, not physical touch. Existing RETRACE/edit safeguards passed the complete DOM regression suite; fresh physical-device repeated retracing remains an owner test.
- Actual PostgreSQL concurrency, lifecycle, allowance, account-isolation and disposable backup-drill checks passed in GitHub. No real database restore was attempted.

## Live deployment

Recovery service `srv-db5a2g5ckfvc739fui70`: live deployment `dep-dbj2ldrm8hqs73fc0ao0`, application commit `764f1ff67d1d86f53fdefb44b28182ae8cc6dbbf`.
Production was inspected read-only and remains on `c049a04b2ac5cc4df3d5c253fe9ca12f1d85806a`, deployment `dep-db5b726k1f9s73e862ug`. Final documentation uses [skip render]; its GitHub checks are verified separately in the closing report.

## Infrastructure and launch blockers

Read [database findings](DATABASE_SAFETY_2026_10_31.md), [monitoring and unapplied approval proposals](MONITORING_DEPLOYMENT_APPROVAL_PLAN_2026_10_31.md), [launch blockers](LAUNCH_BLOCKERS_2026_10_31.md) and [supplier status](SUPPLIER_STATUS_2026_10_31.md).

Paid PostgreSQL system metadata confirms healthy WAL archiving, not a verified restoration chain. Actual retained recovery points, test/production database/credential separation, shared environment groups, and QA database contents/dependencies remain unverified because the available connector does not expose environment mappings/recovery inventory and its external SQL access to the QA instance was refused. Do not infer safe expiry from its name or empty external allowlist. No database changes, exports, account access or production settings changes occurred.

## Preserved evidence

`qa/launch-reliability-2026-10-31/` includes randomized results, regression summary, fictional saved source snapshots, browser results, independent checks, PDF inventory and contact sheets. Two downloadable examples: [Snow Expanded](qa/launch-reliability-2026-10-31/snow-390-expanded.pdf) and [Roofing Expanded](qa/launch-reliability-2026-10-31/roofing-390-expanded.pdf). These are fictional QA examples, not actual property photographs. The remaining downloads were inspected as temporary test artifacts.

No new feature or autosave was introduced. Stop after this batch.
