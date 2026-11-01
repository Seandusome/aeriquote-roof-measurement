# Browser exceptions and failure recovery — November 1, 2026

## Results and test boundaries

Natural timed-expiry testing was completed and checkpointed first at f30833ff: original cookie retained, actual age-based expiry, unsaved work recovered under the same account, exactly one revision/receipt and matching PDFs. Temporary timeout restored to ordinary Flask31day lifetime; QA override disabled. This report adds browser exception/retry testing requested afterward.

Final isolated Chromium workflow **41355170665**, commit **167a3ece1f48b73e1a15a2f727a4d7101de43e0e**, SUCCESS. All five jobs actually executed and passed: recovery124993566797, PDF failure124993567005, public124993567036, baseline124993567129 and property failure124993567333. Full recovery41355170615 (including PostgreSQL16/18) and application41355170587 also SUCCESS. These results replace failed/incomplete attempts; a readiness failure is never counted as browser coverage.

Every browser job starts a fresh loopback Flask server with a TemporaryDirectory SQLite database, fictional owners/customer data and provider fixtures. The server forces DATABASE_URL empty, denies unexpected provider calls, and Chromium routes abort all non-loopback traffic except locally fulfilled Leaflet/html2canvas/jsPDF assets. No production/customer/Render QA database connection or credentials is used in these CI jobs. Each baseline industry/width and each public-login/signup case receives a fresh Chromium browser context, not merely a new tab. Physical phones and real mobile Safari/Messenger remain pending.

| Check | Executed coverage | Outcome |
|---|---|---|
| Signup/login initialization and retry | Fresh1440px and390px contexts; incorrect fictional login then correct login; signup dropped request, HTML/non-JSON503 and server429, then successful signup/setup navigation | PASS; entered details retained and retry possible; no uncaught page errors |
| Property load, measuring, preview, saved reopen, Single/Expanded export | Six industries×two widths=12 fresh-context workflows; real UI drawing of Areas/Linear/manual Roofing, actual local API saves and real Chromium PDF downloads | PASS; zero uncaught page errors, no horizontal workspace overflow, quote/customer/pricing unchanged by exports |
| Property API failure | Desktop and390px Snow; provider503 after unsaved geometry/customer data exists | PASS; geometry/customer/lookup count retained and clear retry message |
| Imagery decode/network failure | Desktop and390px Snow; wide/fallback image requests aborted | PASS; old property/work retained, no lookup count increase, retry message |
| Session expires during property acceptance | Desktop and390px Snow; acceptance401 | PASS; old geometry/customer/usage retained, retry message |
| Expired save, wrong-account login and original-account recovery |390px Snow with real local login/session/API responses | PASS; original draft retained, foreign-account save blocked, foreign branding cache cleared before profile hydration |
| Refresh/navigation warning |390px unsaved draft; cancel actual beforeunload dialog | PASS; exact geometry/customer retained |
| Saved-image503 and renderer interruption |390px; missing saved aerial, successful retry, html2canvas throw, invalid quantity, rapid duplicate downloads | PASS; handled errors, retry controls restored, exact saved snapshot retained, stale image-error placeholder removed, one download for rapid duplicate calls |
| Forced tab close | Actual target forcibly closed despite normal warning | **KNOWN LIMITATION**: never-saved in-memory draft is not restored; explicit saved estimate survives |

The matrix observes real Chromium `pageerror` events (including uncaught script errors/unhandled promise rejections), rather than treating expected failed HTTP requests as crashes. Intentional provider/image failures and handled fixed-code console errors are expected. It does not certify every browser, arbitrary CDN-library failure, browser-process/OS crash durability or every live provider response. The forced-close limitation is kept separate from exception recovery and is not marked passed as draft preservation. Durable unsaved-draft restore has not been implemented in this batch.

Independent verifier scripts/verify_prelaunch_browser.py passed all12 downloaded source snapshots against WGS84 geometry (existing model tolerance0.6%) and Decimal price/tax arithmetic. This uses fictional grid imagery, not a new live-imagery or survey-accuracy claim. Sample390px screenshots were inspected; physical touch behavior is not inferred.

## Reproduced and fixed product issue

Signup's catch handler showed raw browser messages `Failed to fetch` and JSON parse errors without explaining recovery. The strengthened six-industry executable signup test first FAILED on `Failed to fetch`. The narrow fix maps TypeError/SyntaxError failures to: “Could not connect to create your account. Your details are still here. Please try again.” Server validation errors retain their specific messages, retry buttons re-enable, and inputs stay intact. Local tests passed after the fix; real Chromium network/non-JSON/server-error/success-retry tests then passed at both widths. No signup API, authentication, password, account, pricing, allowance or measurement behavior changed.

Recovery-only deploy dep-dbjrg1m7bikc738bl84g at167a3ece publishes this message fix and the already-disabled QA-only timeout helper. Verified LIVE22:07:57UTC and running checkout167a3ece. New runtime: timeout_overrideFalse; normal lifetime2678400seconds; exact QA databaseTrue; login diagnostics disabledTrue; signup fix presentTrue. Fresh live signup loads without application exception; observed console errors come only from the browser extension. Main/production/customer data untouched; recovery auto-deploy Off, isolated QA connection unchanged, temporary login diagnostics and session-timeout overrides disabled.

## Failed startup run: exact diagnosis

Run **41354803554** stopped all four original jobs before browser execution. Downloaded artifact13102996311 and inspected qa-browser-server.log (preserved as initial-server.log): it contains Flask startup and redacted runtime/access events, rather than a startup traceback. The readiness probe requested `/health`, which is whitelisted in authentication middleware but has no actual handler in this application. A disposable fixture reproduction returns `/health`404 and `/dealer-login`200. urllib treats404 as an exception, so the runner incorrectly reported “Disposable QA server did not start” even though Flask was serving.

Changed only the QA readiness probe to the existing public login endpoint, and print the synthetic server log if readiness still fails. No production health/config or logging redaction weakened. The subsequent336d17c run41355033207 executed: baseline/recovery/property/PDF jobs passed; public reached the successful signup destination but its wait expected `.html`, while canonical routing redirected to extensionless `/site/pressure-setup`. Corrected that test expectation, preserving the navigation assertion. Final167a3ece run41355170665 executed all five jobs successfully.

Local Chromium installation was unavailable (missing binary; vendor browser download returned a truncated archive), so actual browser execution was moved to disposable GitHub runners. Local simulated tests are not presented as those browser runs.

## Evidence and ongoing QA plan

Durable repository evidence in docs/qa/browser-crash-2026-11-01: initial server log; final job-evidence.json; baseline/public result JSON; all12 saved source JSON snapshots; sample Snow/Roofing/signup390px screenshots. Complete fictional PDFs/screenshots and other job output are retained in final run41355170665 artifacts for14days. Artifact IDs/digests and file hashes belong in evidence-manifest.json; do not preserve expiring download URLs.

Keep this sequence for future release checks: fresh-context signup/login → property and provider/image failures with an existing draft → actual measurement/price/customer entry → preview/save failures and expired/wrong-account recovery → Single/Expanded PDF capture/retry → fresh reopen and independent quantities/totals. Run desktop plus phone-sized contexts; separately record physical-phone touch. Treat beforeunload cancellation, caught JavaScript/API errors, natural session age expiry and forced process/tab loss as different evidence boundaries. Fix only reproduced application failures, retain failed-test evidence, and checkpoint verified results.
