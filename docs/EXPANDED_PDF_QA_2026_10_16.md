# Expanded estimate PDF checkpoint - October 16, 2026

Branch: landscaping-multi-area-recovery-oct11 only. Main is unchanged.

Customer report has a PDF layout selector. Single page retains the existing export. Expanded export dedicates page 1 to the approved aerial and area reference legend; following pages contain measurements, itemized pricing, company information and enabled property imagery. Overflow adds pages at readable text size. The browser estimate preview remains the existing layout; the selected layout controls the PDF download.

Live QA: Snow Removal, 2301 Ave C North #115, Saskatoon. Customer: QA TEST - Seven Areas - DO NOT SEND. Seven illustrative test polygons, not verified customer service boundaries. Areas: 5,503; 10,034; 5,176; 5,977; 6,815; 3,537; 6,475 square feet. Total 43,517 square feet. Each rate $0.10/ft². Subtotal $4,351.70; 5% tax $217.59; 6% tax $261.10; total CAD $4,830.39. Saved quote reopened after deployment with unchanged quantities and total.

Actual downloads verified one-page legacy PDF and three-page expanded PDF (aerial; all measurements and pricing; enabled company benefits and Street View). All downloaded pages were rendered and inspected. Numbered badges avoid measurement labels using the existing collision layout, with leaders when displaced. Continuations reuse the first-page header image. Historical aerial view and label coordinates are retained for export. Saved quote businessType restores industry-specific report wording and marketing defaults.

Regression coverage includes temporary export cleanup on capture failure, seven measurement/pricing rows, page numbering, unchanged snapshot, saved-aerial number references and saved Snow reopening from the Commercial route. Existing roof coverage guard remains in force: unresolved known area/outline mismatches block customer estimates and PDFs. Whole-building automatic roofing remains unresolved and is not certified by these PDF changes.

Scope: multiple measured areas on one property. A combined estimate spanning different property addresses is not implemented by this change. PDF layout selection is an export choice, not a saved per-account preference.
