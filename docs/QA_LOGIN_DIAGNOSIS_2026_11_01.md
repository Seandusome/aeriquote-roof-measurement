# Recovery login diagnosis — November 1, 2026

## Scope and current deployment

Only recovery `landscaping-multi-area-recovery-oct11` and its fictional QA owner were inspected. No production/customer-data access or application-code change.

Owner approved upgrading recovery compute to US$7/month. Render automatically deployed documentation checkpoint `b1562019b4007bc760640366c9aa01fd494574ae` as `dep-dbjq0jcs728c738gen3g`, verified live; auto-deploy remains Off. Application code is unchanged from `60ae098`. The separate QA database remains on its existing configuration.

## Authoritative observations

- Browser login: `https://aeriquote-commercial-test.onrender.com/dealer-login`.
- Shell git HEAD: `b1562019b4007bc760640366c9aa01fd494574ae`.
- Deployed `app.py` SHA256: `a9132ac9506f3c212ba4bf382f91da322cfc8516ea683adcee1ea89388c4aecc`; matches local reviewed source.
- Running Gunicorn process environment checks matched database host `dpg-dbj4f7lg1s2s73eob8t0-a`. Read-only SQL reports logical database `aeriquote_recovery_qa`.
- Exact QA owner `c417b9a2-51ea-4816-84da-1e597a7de98d` exists, email `qa-browser-oct31-2026@example.invalid`, status active. One matching owner; no matching employee. Stored credential format valid. No credential values or hashes exposed.
- Owner explicitly authorized and personally completed a QA-only password reset through hidden terminal entry. Transaction updated this owner's credential, revoked reset tokens and incremented owner auth version (now 1). No estimate data was modified by this reset. This does not establish the previous rejection's cause; do not repeat/reset again without authorization.
- At 20:46:41 UTC, read-only current email attempt counter was absent; later lookup across retained windows also found none. Expired counters can be deleted by normal login processing. Absence does NOT prove that earlier attempts used a different email or never occurred.

## Existing failed request evidence

Render app logs scoped to November 1 20:40–20:47 UTC show authentication POST responses on the upgraded `pr9j4` instance:

| UTC | HTTP status | Response bytes |
|---|---:|---:|
|20:41:09.117506|200|1757|
|20:41:40.112247|200|1757|
|20:42:00.726646|200|1757|
|20:44:37.927287|200|1757|

GET at 20:43:38 returned 200 / 1690 bytes. Browser displayed `Email or password is incorrect.` after failure. Form inspection confirms POST to the exact same recovery URL, with required `email` and `password` fields and standard username/current-password autocomplete.

Reviewed handler: the displayed rejection is returned after owner/employee authentication conditions fail. A successful owner match sets the Flask session and returns a redirect to `/`; the rejection branch does not reach that session-creation path. Thus existing evidence places these failures before the normal successful redirect, not at a demonstrated post-login cookie/redirect failure. It does not independently establish which email/password bytes were submitted, or distinguish identity selection from credential verification for a particular logged POST.

No response cookie values, session tokens, passwords, request bodies or authorization headers were captured. Cookie issuance/acceptance on a successful login remains unverified; there is no evidence supporting a cookie-specific fix.

## Correlated attempt limitation and next action

Prepared a secure browser-auth submission after recording database/account baseline and form mapping. The credential request returned `declined`; no new correlated request was submitted, and no repeat prompt was issued. Existing sanitized logs deliberately omit submitted identity and verification decisions, so the exact failure stage within credential handling is NOT yet proven. Do not assert that the user's password is wrong, that stale POST replay is the root cause, or that opening a fresh tab fixes it.

Next diagnostic action, if owner elects to resume secure entry: record the known QA email counter before/after one secure sign-in, correlate timestamp/instance/status with Render authentication logs, and inspect the final browser destination/error. A success should show POST redirect then authenticated GET; a failure plus a known-identity counter increment and unchanged active account can narrow the rejection to the verifier path. Any additional instrumentation must record only fixed decision flags, never credential values, lengths, hashes, bodies or cookies. No bypass or replacement account.

## Testing boundaries

This session's controlled checks passed: `scripts/test_failure_recovery.cjs`, `scripts/test_saved_editing_session.py`, `scripts/test_saved_diagram_scope.cjs`. They do not constitute live login or fresh PDF verification. Original measurement/PDF assignment remains pending live sign-in; no fresh PDFs obtained.

## Prepared diagnostic change — not deployed

`app.py` now has default-off instrumentation scoped to the existing recovery-service guard and a single configured `AERIQUOTE_LOGIN_DIAGNOSTIC_EMAIL`. Fixed stages distinguish receipt, rate limiting, owner lookup, owner activity, password verifier result, employee fallback, session creation and rejection. A random non-secret request ID groups these events and is attached as a diagnostic response header. No authentication condition, password algorithm, redirect target, cookie configuration, account or estimate is changed by this instrumentation.

`safe_logging.py` permits only the exact diagnostic event template, an allowlisted stage and a 32-character hexadecimal random ID. Everything else retains existing redaction. Tests use only synthetic credentials and disposable local storage. Deployment and setting the diagnostic-email variable still require owner approval; no environment change or live instrumentation has occurred.

Validation passed: new `test_login_diagnostics.py` (verifier rejection, session creation, cookie/profile continuity, inactive and rate-limited cases, unmatched identity, default-off and production exclusion); existing `test_password_recovery.py`; existing `test_sensitive_logging.py` with six secret canaries and real Gunicorn normal/preload/worker-boot-failure modes. The logging test initially could not start because the local test runtime lacked Gunicorn; after installing declared dependencies in a disposable virtual environment, it passed without application changes for that environment issue.

The user confirms they have used only the QA email throughout this session. Do not attribute their failures to `sean@shingleguard.ca`; that later-mentioned address was checked read-only, found absent, and was not used for their attempts.
