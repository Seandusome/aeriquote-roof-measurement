# Pricing plan copy review - November 10, 2026

**Tested application commit:** `adb214c00c11da34c7a7b1ca1cd0dca0f4661ede` on local review branch `qa/customer-copy-09e795d0`. Undeployed; not pushed.

## Change

Public pricing (`site/pricing.html`), account upgrade (`site/upgrade.html`) and the homepage plan summaries (`site/index.html`) now state **AI-assisted roof measurement where available** directly in each Basic, Pro and Business card. Every card explicitly includes **Branded PDF estimates**.

| Plan | Price USD/month | Measurements/month |
|---|---:|---:|
| Basic | 29 | 25 |
| Pro | 59 | 75 |
| Business | 99 | 200 |

Basic was included because the current public comparison already includes core aerial measurement on every plan and the shared roofing/property path has no Basic-specific restriction on automatic roof data. This is a copy update; no entitlement, plan price or allowance logic was added or changed. Advanced-tool distinctions remain as previously labelled.

Each set of cards is immediately followed by the requested exact explanation:

> Review automatic roof outlines and confirm pitch, or trace manually when needed. Measure areas and lengths for other services.

The account-upgrade benefits were enlarged to **14px**, with 1.5 line height, after the initial visual review found that the old default small type was too small for the added wording. AI remains expressly limited to **roof** measurement where available; surface-service tools are described as area/length measurement. Existing homepage copy attributes AI-derived roof data to Google.

## Verification

Real isolated Chromium **141.0.7390.37**, actual widths verified as **1440** and **390** pixels, each with a 900px viewport height. Disposable loopback Flask runtime and temporary fictional SQLite data. No hosted setting or customer data was used. No real provider lookup was necessary for this static pricing review.

Six page/width combinations passed:

- Public pricing, account upgrade, and homepage summaries at desktop and phone widths.
- All three cards present; correct prices and 25/75/200 allowances.
- Exact AI-assisted phrase and branded-estimate benefit inside every card.
- Exact explanation present once below each card group.
- No horizontal overflow or uncaught JavaScript error.
- All three upgrade selectors still update their pressed/selected state normally.
- Disabled-checkout notice retained, no card-entry form, zero external/payment requests.
- Upgrade benefit text at least 14px.

The final page screenshots and desktop card screenshots were visually inspected. Cards and text wrap without clipping; phone layouts stack vertically. Full-page captures are retained for phone review because oversized element captures in headless Chromium could incorrectly include an offscreen fixed skip link; this was a capture artifact, not a product change. No accessibility control was hidden or removed.

This is phone-sized browser testing, not a physical-phone pass. Previous unchanged controls/purchase-simulation evidence is carried forward rather than repeating the audit. No payment integration was performed.

## Screenshots and runner

`docs/qa/pricing-plan-copy-2026-11-10/` contains desktop/phone full-page screenshots, explanation captures, desktop card closeups, and `results.json` with actual viewport widths/browser version.

Primary review files:

- `pricing-cards-1440.png`
- `pricing-page-390.png`
- `upgrade-cards-1440.png`
- `upgrade-page-390.png`
- `home-page-1440.png`, `home-page-390.png`

Reproduce using the existing isolated supervisor:

```bash
PYTHONPATH=../qa-deps PYTHONDONTWRITEBYTECODE=1 \
NODE_PATH=../mapbox-review/node_modules \
QA_CHROMIUM_EXECUTABLE=/home/agent/.cache/ms-playwright/chromium_headless_shell-1194/chrome-linux/headless_shell \
QA_COPY_BROWSER_SCRIPT=scripts/test_pricing_plan_copy_browser.cjs \
python scripts/run_customer_copy_qa.py
```

Paths describe this workspace; adjust them to installed dependencies elsewhere. Official Playwright 1.56.1 headless shell was reused. The supervisor stopped its temporary server and removed its runtime directory after the batch.

## Hold

No push, deployment, merge or shared-setting change. Real payments remain inactive; hosted QA remains on Google with Auto-Deploy OFF, as directly verified in the preceding visual-review task. The Mapbox PDF visual-verification checkpoint remains pending and untouched.
