# Customer copy visual review - November 10, 2026

**Application tested:** exact `cd2786f1a6ce1194d92f5865fd0686271f650fd6`, based on hosted `09e795d0fb30761a9b5e37a62dbe181e8ee18d2a`.

No application changes were needed in this review. `git diff cd2786f1 -- app.py site/index.html site/pricing.html site/trial-signup.html` was empty. Only disposable test runners and evidence were added. The application remains local and undeployed on `qa/customer-copy-09e795d0`.

## Browser and isolation

Actual **Chromium 141.0.7390.37** (official Playwright 1.56.1 headless shell), viewports **1440 x 900** and **390 x 900**. `window.innerWidth` was explicitly checked and reported 1440 and 390. This is phone-sized browser QA, **not a physical phone test**.

The system Chromium launcher still fails with its ProcessSingleton socket error. The latest bundled browser download was invalid; the official Playwright 1.56.1 headless shell downloaded and launched successfully. No system packages were installed.

The app ran at loopback `127.0.0.1:8765`, with a fresh temporary SQLite database and fictional business accounts from `prelaunch_browser_server.py`. The fixture profile was set to Roofing before login and the manual-only fixture flag was switched off, allowing the actual normal Google-roofing copy to appear. These are runner-only changes, not application bypasses. Normal email/password sign-in was used; no session injection. No property/provider API call or real payment was needed.

Initial attempts stopped because the pre-existing fixture's saved Snow profile/manual-only mode overrode the requested roofing query. Correcting fixture setup resolved that test setup issue; no customer-facing code was changed to satisfy the test.

## Passed at both widths

| Check | Result |
|---|---|
| Owner's orange **PLANS / EXTRA MEASUREMENTS** link is visible | PASS |
| Click opens `/site/pricing#extra-measurements` | PASS |
| Full offer: **25 extra property measurements for US$25** | PASS |
| **Estimates included** | PASS |
| Purchased extras **carry forward without expiry** | PASS |
| **Active paid or complimentary subscription** requirement | PASS |
| **Applicable tax** and final USD total before any future payment | PASS |
| **Purchasing is not available yet** | PASS |
| No purchase form, payment control or payment request | PASS; zero Stripe requests |
| `/qa/purchases` stays unavailable with simulation disabled | PASS; 404 |
| Homepage AI wording specifically applies to roofing and Google's data where available | PASS |
| Outline review, pitch confirmation, manual tracing fallback and branded estimates explained | PASS |
| Roofing signup copy and measurement-help copy displayed | PASS |
| Landscaping signup uses manual service-area/length copy, without AI/automatic-roof claims | PASS |
| No horizontal overflow or uncaught JavaScript errors | PASS |

## Visual inspection

Every saved screenshot was opened and inspected. Desktop and phone owner links are legible and visible in the header. The phone button wraps onto two lines within its existing button grid. The entire offer fits its section at both widths, with all required terms visible and no clipping. The AI callout wraps cleanly on the phone and explicitly says Google data is available only where covered, with review and manual fallback. Signup and measurement instructions were also inspected at both widths. No visual defect requiring an application change was found.

Evidence directory: `docs/qa/customer-copy-visual-2026-11-10/`:

- `owner-1440.png`, `owner-390.png`: where the owner clicks.
- `offer-1440.png`, `offer-390.png`: complete offer and inactive-purchase notice.
- `roofing-ai-1440.png`, `roofing-ai-390.png`: Google-scoped AI wording and manual fallback.
- `measurement-copy-1440.png`, `measurement-copy-390.png`.
- `signup-1440.png`, `signup-390.png`.
- `results.json`: actual widths, browser version and assertions.

Earlier passing control and disposable purchase tests from `QA_CUSTOMER_FACING_REVIEW_2026_11_10.md` are carried forward: application code is unchanged. The browser runner independently exercised the new owner navigation and offer rather than relying on source-text assertions. No real checkout was started.

## Reproduction

Use the tested code and ordinary project dependencies. The screenshot runner requires Playwright and Leaflet; this workspace reused them from `../mapbox-review/node_modules`, and Flask dependencies from `../qa-deps`.

```bash
npm exec --yes --package=playwright@1.56.1 -- playwright install chromium-headless-shell
PYTHONPATH=../qa-deps PYTHONDONTWRITEBYTECODE=1 \
NODE_PATH=../mapbox-review/node_modules \
QA_CHROMIUM_EXECUTABLE=/home/agent/.cache/ms-playwright/chromium_headless_shell-1194/chrome-linux/headless_shell \
python scripts/run_customer_copy_qa.py
```

Adjust dependency and executable paths to the local installation. The supervisor starts both server and browser runner in one process environment, stops the server in `finally`, and removes its disposable runtime directory. Matching temporary fixture databases from failed setup attempts were also removed. Browser contexts closed normally. No secrets or tokens were used.

## Hold state

Render metadata freshly confirms `aeriquote-commercial-test` Auto-Deploy **OFF** (`autoDeploy=no`, trigger `off`). Hosted app/provider settings remain untouched on Google. No push, deploy, merge, payment activation or customer-data change.

Mapbox PDF checkpoint is preserved: application `b08406339b8b4822c6ef99c832a76338a6558e66`, evidence checkpoint `b4e1cb17b47ff3bc4affc5946347ec0557e67b51`, document `../mapbox-review/docs/QA_MAPBOX_PDF_OUTLINE_2026_11_10.md`. **Its native PDF visual verification remains pending**; it was not resumed during this copy task. The now-working headless-shell route is available for a separately authorized continuation.

Remaining review items: Sean's approval of copy/navigation, optional physical-phone review, and separately scoped Stripe integration/test-mode verification before any real purchases. This visual pass does not authorize deployment or payments.
