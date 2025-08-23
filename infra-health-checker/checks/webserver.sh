#!/usr/bin/env bash
set -euo pipefail

THRESHOLD=5000

while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold) THRESHOLD="$2"; shift 2 ;;
        *) shift ;;
    esac
done

ENDPOINTS="${ENDPOINTS:-http://localhost:8080/health}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-5}"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if ! command -v curl >/dev/null 2>&1; then
    cat <<EOF
{"check":"webserver","status":"WARNING","value":0,"threshold":${THRESHOLD},"message":"curl not installed","timestamp":"${TIMESTAMP}","details":{"reason":"curl not found","endpoints":[]}}
EOF
    exit 0
fi

check_endpoint() {
    local url="$1"
    local expected_status="${2:-200}"
    local timeout="${3:-5}"

    local http_code time_total
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}|%{time_total}" \
        --connect-timeout "$timeout" --max-time "$((timeout * 2))" \
        "$url" 2>/dev/null || echo "000|0")

    http_code=$(echo "$response" | cut -d'|' -f1 | awk '{printf "%d", $1}')
    time_total=$(echo "$response" | cut -d'|' -f2)

    local time_ms
    time_ms=$(awk "BEGIN { printf \"%.0f\", $time_total * 1000 }")

    local status="OK"
    if [[ "$http_code" -eq 0 ]]; then
        status="CRITICAL"
    elif [[ "$http_code" -ne "$expected_status" ]]; then
        status="WARNING"
    elif [[ "$time_ms" -ge "$THRESHOLD" ]]; then
        status="WARNING"
    fi

    echo "${status}|${http_code}|${time_ms}|${url}"
}

endpoint_details=""
worst_status="OK"
worst_time=0
total_endpoints=0
failed_endpoints=0
first=true

IFS=',' read -ra ENDPOINT_ARRAY <<< "$ENDPOINTS"
for endpoint in "${ENDPOINT_ARRAY[@]}"; do
    endpoint=$(echo "$endpoint" | xargs)
    [[ -z "$endpoint" ]] && continue
    total_endpoints=$((total_endpoints + 1))

    result=$(check_endpoint "$endpoint" "200" "$CONNECT_TIMEOUT")
    ep_status=$(echo "$result" | cut -d'|' -f1)
    ep_code=$(echo "$result" | cut -d'|' -f2)
    ep_time=$(echo "$result" | cut -d'|' -f3)
    ep_url=$(echo "$result" | cut -d'|' -f4-)

    if [[ "$ep_time" -gt "$worst_time" ]]; then
        worst_time="$ep_time"
    fi

    if [[ "$ep_status" == "CRITICAL" ]]; then
        worst_status="CRITICAL"
        failed_endpoints=$((failed_endpoints + 1))
    elif [[ "$ep_status" == "WARNING" ]] && [[ "$worst_status" != "CRITICAL" ]]; then
        worst_status="WARNING"
    fi

    [[ "$first" == true ]] && first=false || endpoint_details="${endpoint_details},"
    endpoint_details="${endpoint_details}{\"url\":\"${ep_url}\",\"status\":\"${ep_status}\",\"http_code\":${ep_code},\"response_time_ms\":${ep_time}}"
done

if [[ "$total_endpoints" -eq 0 ]]; then
    worst_status="OK"
    worst_time=0
fi

cat <<EOF
{"check":"webserver","status":"${worst_status}","value":${worst_time},"threshold":${THRESHOLD},"message":"${failed_endpoints}/${total_endpoints} endpoints failing, worst response ${worst_time}ms","timestamp":"${TIMESTAMP}","details":{"endpoints":[${endpoint_details}],"total":${total_endpoints},"failed":${failed_endpoints},"worst_response_ms":${worst_time}}}
EOF
