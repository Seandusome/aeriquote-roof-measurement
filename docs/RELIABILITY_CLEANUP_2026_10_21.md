# GitHub and Render reliability cleanup — 2026-10-21

Starting checkpoint: a62cd85c058fcf0056cb01e9bdd498dc045a4564. Work exclusively on landscaping-multi-area-recovery-oct11. No application-code change, main modification, account change or restoration of AI Trace.

## Seven historical notifications investigated

| Notification | Actual failure | Resolution / verification |
| --- | --- | --- |
| GitHub 39674947826, landscaping benefits | Old patch expected the pre-fix benefitText5 markup; zero matches | Six benefit editor rows, landscaping defaults, fillLandscapingBenefits and service-specific wording already shipped. Verified current source and rendered industry/landscaping regressions. Retired workflow and one-shot script. |
| GitHub 39674947755, admin and estimate area | Old patch expected the obsolete limit>0 quota conditional; zero matches | Persisted Head Office access and allowance bypass already implemented; saved-area correction and returnToAreaCorrection already present. Account/allowance and saved editing/outline regressions cover replacements. Retired workflow and script. |
| GitHub 39674947843, area outline | Old patch expected an older updateAreaUi function prefix; zero matches | Saved outlines have draggable handles, correction, Save/Cancel and industry instructions. Rendered controls, multi-area engine and live Batch3 mouse checks already verified them. Retired workflow and script. |
| GitHub 39674947854, landscaping recovery | Assertion failed on old savedServiceAreas priceCalc search | Current commercialAreas-based implementation supersedes it, preserving separate area/linear quantities and rates. Actual-function engine, rendering, pricing and geometry regressions cover all services. Reapplying the old patch would mix square and linear feet and regress the current implementation. Retired workflow and script. |
| GitHub 39669385233, regression | ReferenceError: estimatePeriodValue is not defined at priceCalc in VM harness on 314ffa2 | App already defined helper; isolated test had not extracted it. Extraction was repaired in 2fbb280 and is present in a62cd85. Current actual-function test further asserts all six period values, invalid fallback, nonrecurring-industry restriction and unchanged money. No production helper stub introduced. |
| Render 66bba8ac6e8dc8054ecd2b164843039ebc8c30fb | Build at20:50 UTC: pip could not open requirements.txt | Commit contained only two documentation files, omitting runtime source. Complete tree restored in c5367155cd775a7ed6165b1275fa9d1e56c7fd23; deployment finished20:59:29 UTC. |
| Render 2fbb280c0082e0be0eb11959d164ec3d7861a1d8 | Build at20:57 UTC: same missing requirements.txt | Commit contained only a partial tree. Same complete-tree restoration resolved it; later Batch1–3 builds succeeded. No missing dependency installation or environment secret change was needed. |

Historical red runs are retained as honest history; obsolete patches were not rerun to manufacture green checks. Their original files remain retrievable from Git at a62cd85. No workflow that mutates/commits code replaces them.

## Reliability changes

- Removed only the four obsolete correction workflows and their four one-shot source-replacement scripts, after verifying intended outcomes above. Other workflows remain.
- Active recovery validation explicitly uses contents: read and a recovery-ref guard. Lightweight application validation now runs on every recovery push, including documentation-only commits, and rejects manual dispatch for another ref. The existing main/PR validation file was left untouched.
- New read-only check_release_files.py verifies17 essential runtime/source/static files and parses Python without importing app or accessing a database. It explicitly rejects both failed historical trees (tested in isolated temporary directories), including the missing requirements.txt. Both active checks run it before further validation.
- Strengthened recurring-period harness checks using the actual application helper. The preexisting fix is preserved, not duplicated.
- Published trees must contain every repository entry; never assume this connector preserves base_tree_sha. Compare the complete result against the intended local tree before considering a checkpoint valid.

## Verification

Before cleanup: a62cd85 was confirmed LIVE (dep-dbcja38u01pc73bd0h40, finished21:57:20 UTC); GitHub regression run39682750540 succeeded. Prior source commit991b410 passed both application and full regression checks (39682456587 /39682456649). Public website /site/ and /dealer-login returned200 with expected content. The service uses TCP health checks (empty configured HTTP path); /health returning404 is not a failed configured health probe.

After cleanup: 53/53 full local regression commands passed, plus both historical incomplete-tree rejection probes. git diff --check passed. No new browser, PDF, physical-device or live-account testing claimed in this infrastructure-only batch. The final response records the published cleanup commit, actual GitHub check outcomes and Render deployment state; Actions and Render retain their authoritative run records.

Remaining limitations from Batch3 persist: physical touch, live reset email delivery, external roof ground truth and PostgreSQL concurrency are not established by this cleanup. CI checks validate the source tree after publication; they do not prevent an authorized client from publishing an incomplete Git tree. This service currently auto-deploys on commit; its Render settings were not changed.
