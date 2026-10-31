# Launch blockers - October 31, 2026

Operational and commercial launch sign-off remains pending. Passing regressions is bounded evidence, not proof that every customer scenario is safe.

| Priority | Item | Status / release condition |
|---|---|---|
| P0 | Imagery rights and coverage | Blocked. Stadia standard tracing explicitly rejected per Sean; Spexi verbal and Mapbox indicative only. Require written tracing/storage/PDF/history/SaaS rights and property coverage; migration not authorized |
| P0 | Production versus recovery database isolation | Unverified; masked service/DB/role/env group mapping required before real customer release |
| P0 | Managed recovery points and recovery access | Active WAL archives verified, actual usable base backups/PITR window/retention unverified; approved new-instance drill and RPO/RTO needed |
| P0 | Production deployment approval | On Commit/unprotected metadata and recovery-only full CI are inadequate; apply reviewed proposal only after approval; require full checks and explicit owner release approval |
| P1 | DB network/credential scope | Paid external allowlist permits any IP with valid credentials; dependency inventory and approved restriction/role review pending |
| P1 | Monitoring and response | TCP-only checks, inherited unverified notifications, no central PDF/error reporting; approve minimal monitoring/readiness, verify delivery, name primary/backup responder |
| P1 | Expiring QA database | November20 expiry; historical unused intent confirmed, current contents/dependencies inaccessible. Do not certify safe expiry without final read-only host/inventory checks |
| P1 | Priced roof overlap | Confirmed duplicate charge across manual/automatic sources fixed at e9edb23; target/full/PG checks and recovery deployment verified. Existing invalid snapshots blocked from download/Print; no geometry deleted |
| P1 | Server small-area numerical stability | Confirmed cancellation defect corrected with equivalent spherical arithmetic at764f1ff; independent model/reference tests and full checks recorded in batch report. No client model, saved data or units changed |
| P1 | Billing for commercial subscriptions | Stripe integration on hold; real billing-period alignment, payments and operational billing lifecycle require separately approved work. Existing25/75/200 provisional allowances preserved |
| P2 | Physical-device confirmation | Prior RETRACE visual approval retained; fresh tests use Chromium/VM/disposable data. Real Safari/Messenger, physical PDF sharing and provider-image coverage remain separately unverified |
| P2 | Saved work/recovery boundaries | Transaction/idempotency/concurrency guards tested; confirmed browser discard/crash draft recovery is not guaranteed. No autosave or DB persistence redesign authorized |
| P2 | Geometry/imagery limitations | Sphere versus WGS84 tolerance is documented, not survey certification. Shadows, outdated imagery and missing roof coverage require contractor review; never synthesize missing sections |

Do not implement new UI/CRM/Stripe/imagery services to close this checklist without approval. Preserve RETRACE, all six industry calculations/permissions, PDF designs, historical data and QA-only features; AI Trace removed and AutoMeasure retained. Read the October31 batch report, database audit, monitoring/release approval plan and resume before the next scoped assignment.
