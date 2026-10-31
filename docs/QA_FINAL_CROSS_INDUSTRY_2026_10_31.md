# End-of-day cross-industry integrity QA — October 31, 2026

## Outcome and deployment

No new high-severity application defect confirmed in this focused round. **No runtime code or infrastructure changes and no deployment.** Fresh PDF download verification could not be completed; do not mark it passed.

Starting GitHub HEAD b74bc3be2431df6e4d1d0746535a67dc4056c834 was verified current. Both workflows41242172010 /41242172011 succeeded. The latter includes recovery124658132737, PostgreSQL16 job124658132747 and PostgreSQL18 job124658132602, all SUCCESS. These cover the existing79-command full suite and isolated PostgreSQL checks. They were not manually rerun just to repeat passed work; application source remains60ae098f7f2010dea2c9bbde767b0a35d3395f57, live recovery deploydep-dbj5esc9v7es7395qou0.

The newly isolated QA PostgreSQL18 database dpg-dbj4f7lg1s2s73eob8t0-a was used through the recovery app only. No connection, credentials, network access, Render configuration, allowance, imagery, PDF layout or pricing code was edited. Main, production, original paid database and real accounts were not targeted.

## Fresh live browser verification

Used only fictional owner c417b9a2-51ea-4816-84da-1e597a7de98d /fictional customer/company, on the existing authorized Saskatoon QA property imagery. Outlines remain fictional QA data, not a measurement certification of that property.

- Created new saved revisions through the actual interface in all six industries: Roofing, Commercial, Snow, Pressure, Paving and Landscaping. Existing roof, Area and Linear history was retained. Same property correctly accumulates versions rather than duplicate property records.
- Commercial **Area2 RETRACE Cancel**: proposed7,508→6,227ft² /$1,570.25→$1,428.06. Cancel retained7,508ft² and$1,570.25 exactly. Repeated retrace/Save changed only Area2; Area1 remained6,125ft² and independent Linear205.4ft remained visible and priced.
- Commercial **Linear correction Cancel then Save**: mouse-drag proposed205.4→188.3ft /$1,428.06→$1,423.32. Cancel restored the original; repeated correction/Save retained188.2640110545814ft underlying length and both Areas. No accidental map movement observed in this desktop interaction. This is not a touch/physical-phone result.
- All four subsequent surface-industry revisions displayed both saved Areas(6,125+6,227=12,352ft²), the independent Linear188.3ft, correct industry wording and no Roofing pitch labels. Snow/Pressure/Paving/Landscaping rate$0.10 gives subtotal$1,254.03, GST$62.70, PST$75.24, total$1,391.97. Commercial’s existing$0.25 Linear rate gives$1,423.32; the plan/price defaults were not changed.
- After browser refresh, reopened **latest Landscaping → original Roofing version1 → older Commercial version7 → latest Landscaping**. Original Roofing still has7,348.380392728047ft², pitch22.62°, total$815.67 and no surface geometry. Older Commercial retains6,125+7,508ft² /205.3547041980894ft /$1,570.25, with no Roofing geometry. The latest corrected Landscaping remains12,352ft² /188.2640110545814ft /$1,391.97. These values were independently recalculated from the active canvas’s DOM-backed saved scope, not inferred from a hidden app global.
- Earlier versions remain listed; final history shows17 previous versions plus the current version. Only new fictional revisions/corrections were saved; no older version was edited or deleted. Fresh live line-item/tax totals match Decimal arithmetic using underlying length precision. The displayed length rounds to one decimal; amounts use the saved unrounded length.

## New adversarial and independent checks

Evidence and reproducible experiment scripts are in `docs/qa/final-cross-industry-2026-10-31/`.

| Experiment | Result | Evidence boundary |
|---|---|---|
|180 fictional mixed-family revisions,1,080 reverse/forward/random reopen renders across six industries | PASS; exactly selected geometry sent to the historical image renderer; no inactive roof labels and no source snapshot mutation | Actual renderer/label functions with DOM/image/network stubs; not1,080 live-provider requests |
|540 independent pricing cases | PASS; regular/discount/included taxes, individual Area rates, Linear, extras and Roofing pitch-adjusted quantities agree with server pricing | Standalone Decimal reference versus server pricing module; no database |
|WGS84 measurements and pitch reference | PASS within existing model tolerance; maximum Area0.187%, Linear0.320%, pitch-adjusted roof0.162% difference | GeographicLib ellipsoid versus current spherical model/rounding; not survey accuracy or imagery-edge certification |
|24 six-industry failed-save/retry cases | PASS; offline, timeout,409 and400 preserve original revisions/key/version until success; retry retains idempotency key | Controlled VM fetch responses; not actual deployed network interruption or PostgreSQL fault injection |
|Six live tax/total checks and three independently recalculated saved reopens | PASS | Actual QA browser observations plus standalone Decimal calculations |

These experiments extend revision-order and correction coverage. The standalone scripts are QA evidence, not changes to the production measurement engine or canonical release workflow.

## PDF transfer limitation — remains unverified

Two new Roofing Single download attempts returned browser-tool `Download ... failed` while the application reported “Estimate PDF downloaded.” The tab’s limited error log showed extension metadata-send errors, not a confirmed application calculation/PDF stack trace. One reasonable page refresh and an Expanded attempt on reopened Landscaping also failed and reset the browser tool runtime. The QA tab was safely rebound; repeated download attempts stopped.

**No new PDF file was obtained or visually verified in this round.** The evidence does not distinguish browser download/transfer failure from a product download problem conclusively. Do not mark Single/Expanded broken solely from these tool errors, and do not claim they passed. Previous actual PDFs at60ae098 were verified in the earlier focused PDF report; that historical evidence is preserved and not relabeled as these fresh revisions. No workaround, provider change, new browser security setting or speculative code fix was applied.

## Next session, in order

1. Verify PDF download in an ordinary browser/physical iPhone using only isolated QA data. Distinguish browser sharing/download instructions, actual product errors and Cloud Browser transfer limitations. Download and visually inspect both layouts for the newest corrected versions before additional PDF sign-off.
2. Confirm RETRACE/Linear Save/Cancel on Sean’s physical iPhone; fresh desktop mouse and simulated tests do not establish Safari/Messenger touch reliability.
3. If fresh defects are confirmed, use a separately scoped reversible recovery commit; preserve all previous history, active-scope fix, account and pricing protections. No new provider, billing or infrastructure work is authorized by this checkpoint.

All completed application fixes remain committed. The containing documentation/evidence commit is the final end-of-day checkpoint and intentionally skips Render. Stop for owner review; no further batch tonight.
