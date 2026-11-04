# Single PDF guard diagnostic closeout — November 4, 2026

Run 41928348039: GitHub confirms 12/13 jobs successful. Job-revisions (126918591571) checked out 210ed412. Log recorded SINGLE_FIT points 6.951282431430689, minimumPoints 7, readable false immediately before mixed_job_history_checks.cjs:23 waited 45 seconds for a download.

Source inspection confirms assertSinglePageLegible throws SINGLE_PAGE_DENSE below 7pt before rasterization/save. downloadEstimatePDF catches it, selects expanded and displays an explanation that the estimate has too much detail for a readable Single page, instructs DOWNLOAD ESTIMATE PDF, and says the saved estimate is unchanged. Thus the absent Single download is expected guard behavior; the run itself did not assert the displayed explanation.

Existing commit 8f7a06fe already corrected mixed-history export handling. Test-only follow-up 26e3ebbc explicitly checks measured fit, unchanged minimumPoints 7, readable/points agreement, no Single download when blocked, Expanded selection, and each part of the explanation. Expanded still downloads. All original revision, geometry, customer, pricing, totals, allowance and immutable-history assertions remain. No application source change in this diagnostic.

Validation: node syntax check passed; existing Single readability unit checks passed against source 7a467e1d, including ordinary/dense/wide and exact 7pt boundary cases. No browser workflow was started or rerun in this session. End-to-end execution of the updated mixed-history test remains pending; do not describe the original failed run as passing or claim both layout PDFs exist for blocked dense cases.

Paused per session limit. No deployment, hosted account/balance/customer data or deployment-setting changes made. Auto-deploy must remain OFF; its live value was not independently re-read in this diagnostic. Continue only in isolated disposable QA when a new testing session is authorized.
