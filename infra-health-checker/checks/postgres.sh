#!/usr/bin/env bash
set -euo pipefail

THRESHOLD=80

PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-postgres}"
PG_DBNAME="${PG_DBNAME:-postgres}"
MAX_REPLICATION_LAG="${MAX_REPLICATION_LAG:-1048576}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold) THRESHOLD="$2"; shift 2 ;;
        --host)      PG_HOST="$2"; shift 2 ;;
        --port)      PG_PORT="$2"; shift 2 ;;
        --user)      PG_USER="$2"; shift 2 ;;
        --dbname)    PG_DBNAME="$2"; shift 2 ;;
        *) shift ;;
    esac
done

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if ! command -v psql >/dev/null 2>&1; then
    cat <<EOF
{"check":"postgres","status":"WARNING","value":0,"threshold":${THRESHOLD},"message":"psql client not installed","timestamp":"${TIMESTAMP}","details":{"connectivity":"unknown","reason":"psql not found"}}
EOF
    exit 0
fi

run_query() {
    local query="$1"
    PGCONNECT_TIMEOUT=5 psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DBNAME" \
        -t -A -c "$query" 2>/dev/null
}

CONNECTIVITY="false"
CONNECTION_COUNT=0
MAX_CONNECTIONS=100
REPLICATION_LAG=0
PG_VERSION="unknown"
UPTIME="unknown"

if pg_result=$(run_query "SELECT 1;" 2>/dev/null) && [[ "$pg_result" == "1" ]]; then
    CONNECTIVITY="true"
else
    cat <<EOF
{"check":"postgres","status":"CRITICAL","value":0,"threshold":${THRESHOLD},"message":"Cannot connect to PostgreSQL at ${PG_HOST}:${PG_PORT}","timestamp":"${TIMESTAMP}","details":{"connectivity":false,"host":"${PG_HOST}","port":${PG_PORT}}}
EOF
    exit 0
fi

CONNECTION_COUNT=$(run_query "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null || echo "0")
MAX_CONNECTIONS=$(run_query "SHOW max_connections;" 2>/dev/null || echo "100")
PG_VERSION=$(run_query "SELECT version();" 2>/dev/null | head -1 || echo "unknown")

UPTIME=$(run_query "SELECT now() - pg_postmaster_start_time();" 2>/dev/null || echo "unknown")

REPLICATION_LAG=$(run_query "
    SELECT COALESCE(
        (SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)
         FROM pg_stat_replication
         ORDER BY replay_lsn ASC
         LIMIT 1),
        0
    );" 2>/dev/null || echo "0")

if [[ -z "$CONNECTION_COUNT" ]]; then CONNECTION_COUNT=0; fi
if [[ -z "$MAX_CONNECTIONS" ]]; then MAX_CONNECTIONS=100; fi
if [[ -z "$REPLICATION_LAG" ]]; then REPLICATION_LAG=0; fi

CONN_PCT=0
if [[ "$MAX_CONNECTIONS" -gt 0 ]]; then
    CONN_PCT=$(awk "BEGIN { printf \"%.1f\", ($CONNECTION_COUNT / $MAX_CONNECTIONS) * 100 }")
fi

CONN_PCT_INT=$(awk "BEGIN { printf \"%.0f\", $CONN_PCT }")
REPLICATION_LAG_INT=$(echo "$REPLICATION_LAG" | awk '{printf "%.0f", $1}')

if [[ "$CONN_PCT_INT" -ge 95 ]] || [[ "$REPLICATION_LAG_INT" -ge "$MAX_REPLICATION_LAG" ]]; then
    STATUS="CRITICAL"
elif [[ "$CONN_PCT_INT" -ge "$THRESHOLD" ]]; then
    STATUS="WARNING"
else
    STATUS="OK"
fi

PG_VERSION_ESCAPED=$(echo "$PG_VERSION" | tr '"' "'")
UPTIME_ESCAPED=$(echo "$UPTIME" | tr '"' "'")

cat <<EOF
{"check":"postgres","status":"${STATUS}","value":${CONN_PCT},"threshold":${THRESHOLD},"message":"${CONNECTION_COUNT}/${MAX_CONNECTIONS} connections (${CONN_PCT}%)","timestamp":"${TIMESTAMP}","details":{"connectivity":true,"host":"${PG_HOST}","port":${PG_PORT},"connections":${CONNECTION_COUNT},"max_connections":${MAX_CONNECTIONS},"connection_pct":${CONN_PCT},"replication_lag_bytes":${REPLICATION_LAG_INT},"version":"${PG_VERSION_ESCAPED}","uptime":"${UPTIME_ESCAPED}"}}
EOF
