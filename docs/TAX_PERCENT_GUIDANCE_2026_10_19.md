# Tax percentage guidance — October 19 2026

Sean mistook a fractional tax input for 5%. Added explicit Enter 5 for 5% (not 0.05) guidance to all six shared onboarding flows and workspace profile settings. Decimal tax rates remain accepted (step any); stored values and tax calculations are unchanged. Alberta's provincial tax remains disabled/zero in setup. No automatic reinterpretation of existing rates.

Local onboarding regression (12 flows including Alberta) and full DOM/Leaflet controls regression passed, zero script errors. Main untouched, AI Trace remains removed, roof scope and manual pitch safeguards preserved. Live deployment verification pending at commit creation.
