# Estimate save timing QA — 2026-10-20

Recovery branch only. Customer fields, pricing and quote geometry are frozen before awaiting Street View, preventing edits during image loading from mixing later details with the report already prepared. Deep copying preserves nested saved-area geometry and names.

Validation: actual save-function delayed-response test passed (later customer/address/service/area edits do not change pending payload); existing duplicate-skip, retry and metadata cases passed. Comprehensive test_landscaping_controls.cjs passed with Script errors: []. Python compilation and diff whitespace checks passed.

Live browser verification remains pending due to retained-data browser protection. No production/main, dealer accounts or credits changed. Previous QA evidence and launch gaps remain in RESUME_HERE_2026_10_20.md.
