# Hosting capacity and costs — October 15, 2026

Planning scenarios for 100 and 250 customer businesses. No services, plans or production/main code changed.

## Measurement status
Code inspection confirms saved estimates may contain Street View image data; saving another quote for an existing property keeps the preceding payload in estimate_revisions. Therefore image sizes and revisions must be included.
The local scratch SQLite database has zero estimates/revisions and is NOT representative of Render. Live database size, average saved payload and runtime load have not been measured. Do not describe the scenarios below as an actual audit or guaranteed capacity.

## Assumptions
- 40 new estimates/business/month: 4,000 at 100 businesses; 10,000 at 250.
- Illustrative mean stored payload: 0.25 MB, not measured.
- 50% additional payload allowance for revisions.
- One year retained: about 18 GB / 45 GB of payload before indexes/other tables.
- Illustrative allocated storage: 25 GB / 60 GB. It can start lower and grow; these allocations are not verified requirements.
- At 1 MB/estimate instead, payload grows to roughly 72 GB / 180 GB per year with the same revision allowance. 100 GB / 225 GB allocations illustrate extra headroom. Actual compression, revisions and image behavior affect physical size.
- Customer count is not simultaneous users. Load testing and runtime measurements must determine compute; the larger 250-customer configuration is a planning reserve rather than a proven requirement.

## Published Render rate inputs, checked October 15
USD/month, before tax:
- Web 1 CPU / 2 GB: $25.
- Web 2 CPU / 4 GB: $85.
- Postgres 0.5 CPU / 1 GB: $19 plus storage.
- Postgres 1 CPU / 2 GB: $40 plus storage.
- Postgres storage: $0.30 per allocated GB/month (model conservatively charges the whole allocation).
- Pro workspace: $25/month; allows horizontal application autoscaling. Not mandatory solely because customer count reaches 100.
- Paid Postgres includes continual backups/PITR. Recovery window is 3 days on Hobby, 7 on Pro+. Long-term independent backup retention is separate.

## Illustrative base configurations
| Item | 100 customers | 250 customers |
| --- | ---: | ---: |
| Web compute | $25 | $85 |
| PostgreSQL compute | $19 | $40 |
| Database allocation | 25 GB / $7.50 | 60 GB / $18 |
| Pro workspace | $25 | $25 |
| Base monthly sum | $76.50 | $168 |
| Working core-hosting budget with contingency | $100–125 | $200–250 |

At 1 MB average estimate with 100 GB / 225 GB allocated, base sums become about $99 / $217.50. Actual workload can require more/less compute and storage. Baseline is one production web service, one production database, one workspace; not high availability or a multi-instance deployment.
Excluded: Google Maps/imagery APIs, Resend subscription/overages, card fees, tax, exchange rates, separate test services, additional replicas/workers, bandwidth/build overages and independent long-term backup storage. This is not the total cost to operate AeriQuote. Runtime autoscaling bills every additional instance.

## Provider responsibilities
Render provides managed infrastructure, database services, paid database recovery, metrics, and configurable storage autoscaling. We still choose architecture, configure alerts/limits, validate isolation, test restores and optimize image storage. Render support can advise; it does not automatically audit AeriQuote's usage or guarantee that a specific plan supports a customer count.
Storage autoscaling must be enabled. At 90% used it expands by 50%, rounded to a 5 GB multiple; extra capacity is billed and cannot be reduced afterward.
Large image/object storage could reduce database growth, but the current app has not been migrated to that architecture. Map imagery retention terms must be reviewed before changing storage policy.

## Read-only measurements to collect when work resumes
Confirm connected backend and live persistence first. For Postgres, obtain pg_database_size(current_database()) and aggregate COUNT/AVG/MAX/SUM(octet_length(payload)) separately for estimates and estimate_revisions. Do not export customer details or secrets.
Also inspect database/web RAM/CPU, latency, concurrent activity and bandwidth. Use these aggregates to replace the 0.25 MB assumption, validate the 40/month assumption against usage, and tune the plan. No database upgrade is authorized by this forecast alone.

## Official sources
- https://render.com/pricing (current compute, workspace, storage rates)
- https://render.com/docs/compute-plans (plan sizes and names)
- https://render.com/docs/postgresql-creating-connecting (storage autoscaling)
- https://render.com/docs/postgresql-backups (recovery and retention)
- https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses (billing components/overages)
