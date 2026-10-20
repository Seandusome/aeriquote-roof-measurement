# October 20 live warranty QA checkpoint

Application 0135a4e remains deployed on the recovery branch. Main and roof safeguards were not changed.

- Sean completed password recovery manually and signed in. Fresh live profile confirmed `sean@shinglextra.com`, company AeriQuote QA, approved brand `shingle_guard`, no complimentary allowance or extra credits. The recovery page was reachable; no underlying recovery defect was established. The earlier automated reset submission was denied by browser security review and was not retried through another mechanism.
- Reopened `QA TEST Roofing First Estimate DO NOT SEND`, then its current version. The stored report showed 1,790 ft², manual trace with 5/12 pitch, $1,987.15. Old historical snapshots correctly did not acquire a new warranty shield.
- Entered saved-job edit mode; measurements and pitch restored. Selected the approved Shingle Guard logo and saved this QA profile with the shield checked. Profile saving applies its default job rate; explicitly restored this QA job's original $1.00 rate afterward.
- Created a labelled revision: `QA TEST - Shingle Guard Warranty Oct20 - DO NOT SEND`. Notes identify synthetic manual roof, assumed 5/12, not a customer measurement. Live report displayed the dealer logo and 6-Year Transferable Warranty shield, retained the roof and dimensions, and showed $1,790.22 + $89.51 + $107.41 = $1,987.14. The one-cent difference from the old snapshot is consistent with the previously fixed rounding calculation; no new pricing fix was made.
- First live Single-page PDF download attempt hit native credential-data protection and reset the browser kernel. No completed PDF download, visual PDF inspection, Expanded download, hide/re-export, ShingleXtra live export, or reopen of the NEW revision is claimed.
- Local `node scripts/test_warranty_shields.cjs` passed, including both brands, hidden preference, ordinary-account absence, Roofing-only display, historical choice and Expanded header inclusion/exclusion. This mocks export capture and is not actual live PDF visual verification.

Next: reopen the new QA revision, confirm persistence, inspect actual Single/Expanded PDFs with shield on/off, then ShingleXtra. Continue pending live isolation checks with QA accounts only. Leave real dealer Blake and all other real accounts unchanged. Never restore AI Trace or alter main.
