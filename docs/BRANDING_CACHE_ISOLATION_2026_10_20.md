# October 20 branding cache isolation

Code audit found that sxDealerDefaults and sxDealerLogo browser caches were shared across logins, while loading an account with no saved logo did not clear the earlier cached logo. The initial profile fetch was asynchronous, allowing previous browser settings to populate before the current account responded.

The authenticated workspace now embeds its owner account ID and checks cache ownership synchronously before restoring any browser defaults. Changing owner accounts clears previous browser branding; same-owner employee/owner reloads retain local edits. Unattributed legacy cache is cleared rather than assigned to an unknown owner. Server-saved profile data and original logo/shield assets remain untouched. This can require re-uploading an older logo that existed only in an unattributed browser cache; saved account logos reload from the server.

Regression in test_warranty_shields.cjs covers legacy/unattributed cache, same-account edits and switching to a different account. Runtime/browser became unavailable on October 20 after secure sign-in returned to login; no live PDF visual test or local test execution is claimed. GitHub CI is the execution check for this revision. No live customer profile changed. Main and roof scope/pitch safeguards remain unchanged. No CRM or estimate email feature for launch.
