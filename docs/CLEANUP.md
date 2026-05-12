# Cleanup and Maintenance Operations

## 1. Overview

This document defines cleanup, maintenance, and operational recovery procedures for the Enterprise GenAI Platform in production environments. All operations follow security-first and audit-first principles.

## 2. Cache and Hot-Path Storage Cleanup

### 2.1 Redis Cache Purge

Redis caches are used for:
- Session state (conversation context, user preferences)
- Hot embeddings (frequently retrieved document vectors)
- Rate-limit and quota counters
- Temporary media metadata during generation workflows

**When to clean**:
- Quarterly routine maintenance
- After security incident remediation
- When cache hit ratio falls below 40%
- Before major config rollouts

**Procedure**:

```bash
# Option 1: Full cache flush (affects all users, requires maintenance window)
redis-cli --host $REDIS_HOST --port 6379 FLUSHALL

# Option 2: Selective pattern cleanup
redis-cli --host $REDIS_HOST --port 6379 KEYS "session:*" | xargs -I {} redis-cli --host $REDIS_HOST --port 6379 DEL {}
redis-cli --host $REDIS_HOST --port 6379 KEYS "embed:*" | xargs -I {} redis-cli --host $REDIS_HOST --port 6379 DEL {}

# Option 3: Expired key cleanup (automatic, but force if needed)
redis-cli --host $REDIS_HOST --port 6379 DEBUG OBJECT <key>  # Check TTL
```

**Validation**:
```bash
redis-cli --host $REDIS_HOST --port 6379 INFO stats | grep keys_
```

### 2.2 Blob Storage Archive and Cleanup

Blob Storage holds generated artifacts (images, videos, PPTs) and source documents. Cleanup follows retention policies tied to GDPR and cost optimization.

**Retention Policy**:
- Generated media: 90 days (logs persist in Cosmos; blobs deleted)
- Source documents: Permanent (unless GDPR deletion requested)
- Temporary working files: 7 days
- Audit logs in blob: 365 days

**Cleanup procedure**:

```bash
# List blobs older than 90 days
az storage blob list --account-name <storage> --container-name generated-media \
  --query "[?properties.creationTime < '$(date -d '90 days ago' -u '+%Y-%m-%dT%H:%M:%SZ')'].name"

# Delete archived blobs
az storage blob delete-batch --account-name <storage> --source <list-file>

# Monitor storage cost
az storage account show-usage --name <storage>
```

**Validation**:
```bash
# Check container sizes
az storage blob list --account-name <storage> --container-name <container> \
  --query "[*].[name, properties.contentLength]" -o table | tail -1
```

## 3. Database Cleanup and Vacuuming

### 3.1 PostgreSQL Telemetry and Event Log Cleanup

PostgreSQL stores:
- LLM inference logs (tokens, latency, cost, model)
- Request/response audit trails
- Search and retrieval audit records
- Feedback and friction signals

**Vacuum and analyze** (weekly):

```sql
-- Reclaim disk space from deleted records
VACUUM ANALYZE telemetry_logs;
VACUUM ANALYZE audit_trails;
VACUUM ANALYZE search_logs;

-- Check bloat
SELECT schemaname, tablename, 
       round(100.0 * (total_bytes - main_bytes) / total_bytes, 2) AS bloat_ratio
FROM (
  SELECT schemaname, tablename, 
         pg_total_relation_size(schemaname||'.'||tablename) AS total_bytes,
         pg_relation_size(schemaname||'.'||tablename) AS main_bytes
  FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
) bloat
WHERE round(100.0 * (total_bytes - main_bytes) / total_bytes, 2) > 10;
```

**Data retention cleanup** (monthly):

```sql
-- Delete telemetry older than 90 days
DELETE FROM telemetry_logs 
  WHERE timestamp < NOW() - INTERVAL '90 days'
  AND NOT indexed_for_analysis;

-- Delete audit records older than 365 days (except GDPR-relevant ones)
DELETE FROM audit_trails 
  WHERE timestamp < NOW() - INTERVAL '365 days'
  AND event_type NOT IN ('user_deletion_request', 'data_access_request');

-- Reindex
REINDEX INDEX CONCURRENTLY search_logs_timestamp_idx;
```

**Validation**:

```sql
-- Check record counts after cleanup
SELECT COUNT(*) FROM telemetry_logs;
SELECT COUNT(*) FROM audit_trails;
SELECT COUNT(*) FROM search_logs;
```

### 3.2 Cosmos DB Conversation and Media History Cleanup

Cosmos DB stores:
- Conversation state and turn history
- Media generation metadata (image/video/PPT)
- Evaluation and quality signals

**Archive and purge** (quarterly):

```bash
# Export older conversations to cold storage for archival
az cosmosdb query --resource-group <rg> --name <cosmos> --database <db> \
  --container conversations \
  --query "SELECT * FROM c WHERE c._ts < @cutoff" \
  --parameters "@cutoff=$(date -d '180 days ago' +%s)"

# Archive to Blob Storage (batch job)
# Then delete from Cosmos
az cosmosdb item delete --resource-group <rg> --name <cosmos> \
  --database-name <db> --container-name conversations \
  --id <conversation-id>
```

**Validation**:

```bash
az cosmosdb sql database throughput show --resource-group <rg> \
  --account-name <cosmos> --database-name <db>
```

## 4. Search Index Cleanup and Reoptimization

### 4.1 Azure AI Search Index Maintenance

Azure AI Search stores documents for RAG retrieval (hybrid: semantic, vector, keyword).

**Reindex schedule**:
- Monthly: full reindex (recreate all embeddings)
- Weekly: incremental patch (new/modified documents)
- On-demand: after document source update

**Reindex procedure**:

```bash
# Full reindex (takes ~30 min for 67 docs)
az search service reset-index --resource-group <rg> --service-name <search> \
  --index-name enterprise-knowledge --key <admin-key>

# Monitor reindex progress
az search service get-index-stats --resource-group <rg> \
  --service-name <search> --index-name enterprise-knowledge --key <admin-key>

# Validate document count
az search documents search --resource-group <rg> \
  --service-name <search> --index-name enterprise-knowledge \
  --search-text "*" --select "metadata_storage_path" --key <admin-key> | wc -l
```

**Index health check**:

```bash
# Check analyzer and field mappings
az search service get-analyzer --resource-group <rg> \
  --service-name <search> --index-name enterprise-knowledge

# Verify embedding model
az search service show --resource-group <rg> --service-name <search>
```

## 5. Log and Audit Trail Cleanup

### 5.1 Application Logs (Blob Storage)

Logs from main.py, agents, tools are written to:
- `logs/` local directory (development)
- Blob Storage container: `application-logs` (production)

**Cleanup procedure**:

```bash
# Archive application logs older than 30 days to cold tier
az storage blob set-tier --account-name <storage> --container-name application-logs \
  --name "*.log" --tier Archive \
  --query "[?properties.creationTime < '$(date -d '30 days ago' -u '+%Y-%m-%dT%H:%M:%SZ')'].name"

# Delete older than 365 days
az storage blob delete-batch --account-name <storage> \
  --source <(az storage blob list --account-name <storage> \
    --container-name application-logs --query \
    "[?properties.creationTime < '$(date -d '365 days ago' -u '+%Y-%m-%dT%H:%M:%SZ%')'].name")
```

### 5.2 Audit Trail Rotation

Audit logs are persisted in PostgreSQL and must be retained per GDPR Article 32 (accountability).

**Rotation procedure**:

```bash
# Export audit trail to immutable blob for legal hold
pg_dump --host <pg_host> --username <user> --format plain \
  -t audit_trails <database> | gzip > audit_trail_$(date +%Y%m%d).sql.gz

az storage blob upload --account-name <storage> --container-name audit-archive \
  --name audit_trail_$(date +%Y%m%d).sql.gz --file audit_trail_$(date +%Y%m%d).sql.gz

# Set legal hold
az storage blob legal-hold set --account-name <storage> \
  --container-name audit-archive --name audit_trail_$(date +%Y%m%d).sql.gz \
  --tags retained
```

## 6. GDPR Data Cleanup and Deletion

### 6.1 User Data Deletion Request Processing

When a user submits a GDPR deletion request (via `/governance/delete-user-data` endpoint):

**Automated cleanup**:

```python
# Triggered by: POST /governance/delete-user-data { user_id, request_reason }
# Cleanup operations:
# 1. PostgreSQL: Delete all telemetry_logs WHERE user_id = ?
# 2. PostgreSQL: Delete all audit_trails (entries only, keep deletion_record)
# 3. Cosmos: Delete all conversations WHERE user_id = ?
# 4. Cosmos: Delete all media_metadata WHERE user_id = ?
# 5. Blob Storage: Delete all user-specific artifacts
# 6. Redis: Flush user session keys
# 7. AI Search: Redact PII from indexed documents (if applicable)
# 8. Audit log: Add deletion_record with timestamp, reason, operator
```

**Validation**:

```bash
# Confirm complete deletion
psql -h <pg_host> -U <user> <database> \
  -c "SELECT COUNT(*) FROM telemetry_logs WHERE user_id = '<user_id>';"
  # Expected: 0

az cosmosdb query --resource-group <rg> --name <cosmos> \
  --database conversations --container conversations \
  --query "SELECT * FROM c WHERE c.user_id = '<user_id>'" 
  # Expected: empty array
```

### 6.2 Right to Access (Data Subject Access Request)

When a user requests all their data:

**Data gathering**:

```bash
# SQL export
pg_dump --host <pg_host> --username <user> \
  --table telemetry_logs --table audit_trails --table search_logs \
  --where "user_id = '<user_id>' OR requester_id = '<user_id>'" \
  <database> > user_data_export.sql

# Cosmos export
az cosmosdb database backup retrieve --resource-group <rg> \
  --account-name <cosmos> --database-name conversations \
  --filter "user_id = '<user_id>'" > user_conversations.json

# Blob listing
az storage blob list --account-name <storage> \
  --container-name user-artifacts --prefix "<user_id>/" \
  --output json > user_blobs.json
```

**Delivery**:
- Encrypt combined export (PGP or TDE)
- Send via secure channel with audit log
- Confirm receipt and destroy working copy

## 7. Performance and Capacity Cleanup

### 7.1 Index Optimization After High-Volume Ingestion

After bulk document ingestion into AI Search:

```bash
# Rebuild all indices
az search service reset-index --resource-group <rg> --service-name <search> \
  --all-indices --key <admin-key>

# Check index health
az search service get-index-stats --resource-group <rg> \
  --service-name <search> --all-indices --key <admin-key>
```

### 7.2 Database Connection Pool Tuning

After traffic spike or idle period:

```bash
# Check PostgreSQL connections
psql -h <pg_host> -U <user> <database> \
  -c "SELECT count(*) FROM pg_stat_activity;"

# Restart connection pool if stale
# (FastAPI lifespan handler in src/main.py manages this)

# Force reconnect
curl -X POST http://<api>:8000/health/reconnect
```

## 8. Disaster Recovery and Rebuilding

### 8.1 Restore from Snapshots

If data corruption is detected:

```bash
# PostgreSQL restore
pg_restore --host <pg_host> --username <user> --dbname <database> \
  /backups/postgres_snapshot_$(date +%Y%m%d).dump

# Cosmos restore (via Azure Portal or CLI)
az cosmosdb restore --resource-group <rg> --account-name <cosmos> \
  --restore-timestamp $(date -d '24 hours ago' -u '+%Y-%m-%dT%H:%M:%SZ') \
  --databases-to-restore "<db>"

# Blob restore
az storage blob restore --resource-group <rg> --account-name <storage> \
  --restore-range <start-time> <end-time>
```

### 8.2 Rebuild Services

If API, agents, or tools are corrupted:

```bash
# 1. Verify code integrity
git log --oneline -n 20
git status  # Should be clean

# 2. Restart services in order (respecting dependencies)
# Tools layer: storage, cache, db services
az container restart --resource-group <rg> --name <container>

# 3. API layer: FastAPI entrypoint
az webapp restart --resource-group <rg> --name <webapp>

# 4. Agents layer: reload skill definitions from SKILL.md
curl -X POST http://<api>:8000/agents/reload-skills

# 5. Health check
curl http://<api>:8000/health
```

## 9. Monitoring Cleanup Effectiveness

### 9.1 Cost Tracking

After cleanup, monitor cost reduction:

```bash
# Storage account cost report
az billing usage list --period <YYYY-MM> --output table | grep storage

# Compute cost
az container show --resource-group <rg> --name <container> \
  --query "properties.provisioningState"

# Total estimate for month
az cost analysis show --metric "ActualCost" --timeframe "MonthToDate" \
  --resource-group <rg>
```

### 9.2 Performance Baselines After Cleanup

Before and after cleanup, measure:

```bash
# Index query latency
time (curl -s "http://<api>:8000/search?q=test" | jq .latency_ms)

# Database query latency
psql -h <pg_host> -U <user> <database> \
  -c "EXPLAIN ANALYZE SELECT * FROM telemetry_logs LIMIT 1000;"

# Cache hit ratio
redis-cli --host $REDIS_HOST INFO stats | grep hit_ratio
```

## 10. Operational Checklist

### Monthly

- [ ] Redis cache purge (Option 2: selective pattern cleanup)
- [ ] PostgreSQL VACUUM ANALYZE
- [ ] Archive blob storage older than 90 days
- [ ] Check AI Search reindex status
- [ ] Validate audit trail persistence (no data loss)

### Quarterly

- [ ] Full cache flush (if acceptable downtime)
- [ ] Archive Cosmos DB conversations (180+ days)
- [ ] Full AI Search reindex
- [ ] Database bloat analysis
- [ ] Cost analysis report
- [ ] GDPR deletion queue audit

### Annually

- [ ] Full disaster recovery drill (restore from snapshots)
- [ ] Security audit of deletion and audit logs
- [ ] Archive old application logs to cold storage
- [ ] Performance baseline refresh
- [ ] Skill definition review and update

---

**Maintenance Ownership**: DevOps + SRE team  
**Audit Trail**: All cleanup operations logged in `audit_trails` table with operator, timestamp, reason, and rollback status.  
**Escalation**: If cleanup fails or deletes unexpected data, escalate to Platform Owner and Security team immediately.
