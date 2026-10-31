> Later read-only verification: [Database recovery assessment](DATABASE_RECOVERY_VERIFICATION_2026_10_31.md) updates archive statistics, connector-role findings and recovery planning. Recovery inventory and environment mapping are still unverified. Earlier observations below are preserved.

# Database safety and expiring QA dependency audit - October 31, 2026

Read-only audit. No database writes, exports, recovery/restore, upgrades, credentials, connection changes or network-rule changes. No customer records, password hashes, active SQL text or private estimate data read. Resource names alone are not proof of runtime dependency.

## Current verified evidence

| Item | Paid AeriQuote DB | Expiring Batch4 QA DB |
|---|---|---|
| ID | `dpg-db019ijncjis7383g3a0-a` | `dpg-dbcjg2brjlhs73dn1g7g-a` |
| Status/compute | Available, paid0.1c-256mb | Available, Free |
| Version | Metadata18; system SELECT18.6 | Metadata16; SQL inaccessible |
| External allowlist | `0.0.0.0/0`, authenticated access | Empty: external access disabled |
| Expiry | No expiry reported | November20,2026 at22:09:13.900851Z |
| Actual archiving | `archive_mode=on`, `wal_level=replica`;4591 successful WAL archives,0 recorded failures; last archive October31 17:28:05.620181Z; stats reset October2 | Unknown; Free plan has no managed backups under published policy |
| Actual recovery points | Not exposed by available connector | Not available under Free policy; contents cannot be queried with current access |
| Application dependency | Environment mapping not exposed | Environment mapping not exposed; none found in tracked application/CI configuration |

System-only paid query: `SELECT current_setting('server_version'), current_setting('archive_mode'), current_setting('wal_level'), archived_count, failed_count, last_archived_time, last_failed_time, stats_reset FROM pg_stat_archiver;`. No data tables queried.

Render's paid policy supplies continuous PITR: Hobby workspace3days, Pro+7days, with a new target instance and the newest10minutes excluded. Logical exports retain7days. This describes entitlement, not actual backup inventory. The connector cannot list available recovery timestamps/base-backup history or workspace retention tier. Successful WAL archiving does not prove the base backup/recovery chain is usable. No managed recovery was tested.

## Service and connection isolation

The connected workspace lists four web services, including AeriQuote recovery and the old main service, and no separate workers/cron services. No secrets were returned or requested. Actual runtime environment variables, env group membership, database URLs/credentials, alternate PGHOST-style variables, external scripts and prior deployment environment values cannot be inspected through the available read-only tools. Thus separate database instances/credentials for production versus recovery are NOT confirmed. Do not infer that both use the paid database or that either uses the expiring one.

Recovery remains branch-only; production/main was not modified. Same-region Render applications can still use an internal database URL even when the external allowlist is empty. Therefore the QA allowlist cannot establish absence of internal dependencies. No new privileged access or temporary allowlist exception was introduced.

## Expiring QA contents and purpose

`docs/QA_INTENSIVE_BATCH4_2026_10_21.md` and `docs/RESUME_HERE_2026_10_21.md` state this database was created during Batch4 but never populated; connector access was blocked then too. Actual tests moved to disposable GitHub PostgreSQL16 containers. Current CI still uses localhost `aeriquote_qa`, not a Render database, and guarded test scripts refuse customer storage. Repository search found the expiring database name/ID only in those historical notes, not active code/CI wiring.

An October31 attempt requested only database name, table count, estimated row count and aggregate other-client count. The connector rejected access because the external allowlist is empty; no inventory was obtained. Historical empty/unused status is evidence of intended use, not verification of current contents. Data-retention value and live dependencies remain unverified. No private row inspection or export attempted.

**Recommendation:** leave unchanged now; do not pay merely because of the expiration email, and do not yet certify unattended expiry as harmless. Before November20 obtain a masked service-host/environment-group comparison and a schema/table-count inventory through an existing authorized internal read-only connection. If no dependencies/valuable data, allow expiry without upgrading. If data matters, obtain approval for a scoped secure export; if an active dependency exists, obtain approval for a retention/remediation plan before suspension. Do not weaken network rules to make this audit convenient. Free expiry has a published14-day upgrade grace period before deletion; do not use that as a preservation strategy.

## Proposed network/credential restrictions - not applied

1. Inventory required app services, trusted admin paths and backup tooling; compare only normalized host/database IDs and role identifiers. Compare secrets locally without displaying their values or publishing reusable hashes. A one-time equality result is sufficient; do not copy credentials into reports.
2. Separate production and QA instances/roles/environment groups if they are shared. This requires a separately approved plan and data/access review; no migration is authorized today.
3. Prefer internal networking for same-region app connections. Restrict the paid database's external allowlist to approved admin/backup egress addresses, or disable external access only after proving those paths are unnecessary. This can break hosted MCP access; plan a trusted internal audit/admin path first.
4. Verify least-privilege app roles and credential rotation ownership. Rotate only with an approved coordinated dependent-service plan; no passwords or env variables were read or changed here.
5. Verify Recovery page timestamps, an approved new-instance drill, RPO/RTO, backup access and responder contacts before launch. Do not restore over a live database.

Sources: https://render.com/docs/postgresql-backups ; https://render.com/docs/postgresql-creating-connecting ; https://render.com/docs/free . The primary limitations remain unresolved access questions, not confirmed customer data loss or a verified safe deletion decision. Stop before any infrastructure/data modification.
