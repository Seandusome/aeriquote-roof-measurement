# AeriQuote website review — November 18, 2026
Base: 7b8a12a28df87757d8d34818d211110dc2a28147. Isolated draft, not deployed or legally approved.

Confirmed: operator Shingle Guard Ltd., Alberta corporation (Sean's instruction); no ownership/identity/banking data added. Existing public pricing is USD29/59/99 with25/75/200 separate lookup/new-estimate allowances; retained as existing advertised proposal, not newly approved paid sale. Trial3/no card remains existing offer. No Stripe integration or payment/security compliance claim added.

Implementation evidence:
- app.py property_data prepare/savepoint, accept_property receipt+consume: prepared/failed images do not commit a debit; acceptance uses lookup channel. New operation can debit again even same address.
- app.py estimate_history_api: new property estimate consumes estimate channel; existing property revisions bypass new-estimate consumption; unchanged/replayed operation uses receipt. Loading property can independently consume lookup.
- account_credits.py consume/paid_usage: monthly channel before relevant extra channel; provisional UTC account-anniversary paid allowance; complimentary calendar month differs. No promise future paid charge dates align.
- workspace_drafts.py TTL/put/close/purge:24h fromlatestwrite; save/discard clearsworkspace,expirycleanuprequest-driven. app.py draftrestore doesnotconsume.
- No estimate/account purge or user-facing deletion implementation found in reviewed source. Earlier six-month/year retention statements not an enforced schedule.
- extra_allowance_ledger.py:granted extras carryforward; future purchase/refund eligibility explicitly simulation/policy-dependent.
- site/support.js and support_inbound.py:existing anonymous supportform; no messages submitted inreview.

Small changes: common footer identity/allowance link, About factual explanation, pricingusage section/ambiguousFAQcorrections, reviewlabels onproposedbilling/legalpolicies, privacyretentionfacts. App code, Step3rates, auth, measurement, imagery, save/recovery and payment code unchanged.

## Sean's grouped decisions — required before publication/paid review
1. Confirm advertised USD29/59/99,25/75/200,three-free/noautomaticconversion. Are subscription prices taxexclusive? Which countries/jurisdictions offered, registered taxes, permittedtaxcollection? Do not confuse contractor estimate currency/tax settings with SaaS subscription taxes.
2. Monthly automatic renewal consent, firstpaidcharge/renewaldate, subscriptionperiodalignment, timezone/shortmonths, expiry/rollover, complimentaryperioddifferences. Current account-anniversary basis is provisional.
3. Cancellation method, effective date, endofperiodaccess, downgrade/upgrade/proration, failedpayment/grace/access and notifications. Existing clauses are proposals, not approved working billing features.
4. Refund eligibility, deadline, unusedtime/units,duplicatecharges,servicefailureexceptions,purchasedextras aftercancellation/refund. No no-refundpromise newly authorized; existing non-refundablepolicy remains marked DRAFT.
5. Approved direct support email and/or phone, business postal address appropriateforpublication, servicehours, privacy accountable title/contact and reply expectations. Existing anonymous form is not invented emailcontact.
6. Actual retention schedule by category (estimates/revisions/customerrecords,drafts,accounts,logs,support,auditledger,backups), deletionrequest verification/process/time, backup expiry/legalholds,postcancellationaccess. No6monthpurge or backupencryption asserted.
7. Provider inventory/dataflows,actualhosting/processinglocations,cookies/analytics/emailproviders,security/incidentprocedures and any privacy data-sale/sharing claims. Legal review ofterms/privacy,governinglaw/liability/consumer rights.
8. Imagery/providerlicensing remains OPEN for tracing,deriveddata,storage/StreetView/PDFexport. No permissionclaim. Independentfield/pitchaccuracy and physicalphone save/reopen remainOPEN; previouslostgeometryunrecovered.

No newtermsaccepted, sitevisibilitychanged, livecheckout, cardlogos/PCIclaim, email, deployment,push,hostedsetting orcredentialchange.

## Current official Stripe references reviewed November18
- https://support.stripe.com/questions/business-website-for-account-activation-faq — businessidentity,description,contacts,policies,password-free eventualreview.
- https://docs.stripe.com/get-started/checklist/website — currency,directcontacts,refund/cancellation,privacy,promotions,HTTPS/security.
- https://stripe.com/en-ca/legal/ssa-service-terms — recurringbillingdisclosure andcancellationmethodbeforeinitialcharge.
This is preparation, notStripeapprovalorlegalclearance. Keep privatepreviewprivate. Final publishedreviewpagesmustbeanonymousaccessibleonlyafterseparateauthorizationandbusinessdecisions.

