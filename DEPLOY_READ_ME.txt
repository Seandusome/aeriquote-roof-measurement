SHINGLE GUARD DEALER BETA 1.0B - HOSTED / NO DEALER API KEY

WHAT THIS BUILD CHANGES
- Dealers no longer see or enter the Google API key.
- GOOGLE_API_KEY is read only from the host/server environment.
- Dealers use Shingle Guard in a normal web browser.
- No .BAT file, local Python install, Flask install, or black command window is needed by dealers.

WHAT THIS BUILD DOES NOT CHANGE
- Roof measurement calculations
- Google automatic-measurement workflow
- Manual measurement calculations
- Garage/additional-structure workflow
- Pricing calculations
- Customer estimate/PDF calculations
- Wadena/small-community address fix from Beta 1.0B

DEPLOYMENT
This folder is ready for a Python web host. render.yaml and Procfile are included.

Required server secret:
  GOOGLE_API_KEY=<the Shingle Guard Google API key>

IMPORTANT
Set GOOGLE_API_KEY in the hosting provider's secret/environment settings. Do NOT put the key into app.py, HTML, JavaScript, a ZIP sent to dealers, or a public repository.

After deployment, dealers only need the HTTPS website address. They do not install anything.

GOOGLE KEY RESTRICTIONS
Because Google calls now originate from the hosted server, configure the Google key restrictions for the hosting environment and only the APIs Shingle Guard uses. Confirm Geocoding, Solar API, Street View Static API, and Maps Static API are enabled as required by the app.

BETA SECURITY NOTE
Before broader dealer rollout, add dealer login/authentication and persistent server-side session storage. This package is a controlled dealer Beta deployment build.
