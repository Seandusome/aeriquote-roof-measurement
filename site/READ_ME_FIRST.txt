AeriQuote Snow Flow — Stable Replacement
========================================

Replace ONLY these five files inside the existing /site folder:
- trial-signup.html
- snow-setup.html
- onboarding.js
- choose-plan.html
- checkout.html

Do NOT replace app.py.
Do NOT change Render settings.
Do NOT delete the rest of /site.

This package fixes the click-through/routing layer:
Snow Removal -> trial signup -> Snow setup -> Measure My First Property -> /
and keeps plan choices going to checkout.html?plan=...

Important:
The current repository does not contain a working public account-creation/payment backend in these static pages.
This package therefore preserves the existing measurement application and stores Snow onboarding defaults in the browser.
Live subscription payment still requires a payment provider/backend connection.
