# AeriQuote commercial test: account and storage recovery checklist

## Confirm the running deployment
The current application exposes /api/development-build. Compare the revision reported there to the commit shown as Live on Render. Do not rely on GitHub's branch head alone.

## Protect existing data
Before making any database, login, or account changes, create a Render database backup or snapshot if the service has persistent storage. Never create a replacement dealer account to work around a missing account.

## Determine which database is used
In Render > commercial test service > Environment, check only whether DATABASE_URL is SET (do not reveal its value) and whether ESTIMATE_DB_PATH is SET. If neither is set, app.py uses a local SQLite file at aeriquote_estimates.db, which may not persist across deployments. Check whether a persistent disk is mounted to that file's directory.

## Verify account storage
Use a trusted Render shell or authorized database console to verify that the expected dealer record exists, is active, and that saved estimates are present. Do not print passwords, password hashes, or private customer information.

## Resolve login
If the dealer record is absent, identify and restore the original database/volume or a backup. If it exists, investigate the login lookup and password-hash verification before resetting credentials. Do not assume an incorrect-password message means the password was changed.

## Only then test
Verify login and one property lookup with an authorized test account, followed by aerial panning and PDF satellite image capture. Preserve main and production settings.
