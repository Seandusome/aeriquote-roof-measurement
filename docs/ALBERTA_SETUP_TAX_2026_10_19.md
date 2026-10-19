# Alberta setup tax fields — October 19, 2026

Sean reported setup blocking an Alberta business at the required tax fields. His displayed message named missing Federal / HST Tax %. Reproduced the live Alberta pricing screen: both federal and provincial inputs blank/required, with no Alberta-specific guidance.

Shared onboarding now labels Alberta's primary field GST %, hides/disables the inapplicable provincial input and saves PST 0. GST remains explicitly entered and editable, including 0; no assumption of business registration is made. Stale saved PST is cleared when hydrating an Alberta profile. Changing from Alberta to another Canadian province restores a required blank provincial input so an Alberta zero is not silently applied elsewhere. Other rates remain user-entered defaults, not a full location/place-of-supply tax engine. All six setup pages use a new shared-script cache version.

Regression covers all six Alberta pages, stale saved PST, GST 5 and 0, missing GST validation and Alberta/Saskatchewan switching. Existing 12 setup flows, actual isolated six-account Flask profile persistence and public UI checks pass. No account profile saved during browser QA. Only the recovery branch is changed; main, measurement/PDF engine and roof guards remain unchanged. Live post-deployment outcome is reported in the conversation.

Official reference: https://www.alberta.ca/about-tra (Alberta has no provincial sales tax).
