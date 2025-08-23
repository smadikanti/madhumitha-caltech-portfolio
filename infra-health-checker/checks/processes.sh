#!/usr/bin/env bash
set -euo pipefail

THRESHOLD=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold) THRESHOLD="$2"; shift 2 ;;
        *) shift ;;
    esac
done

CRITICAL_PROCESSES="${CRITICAL_PROCESSES:-sshd,cron}"

check_process_running() {
    local proc_name="$1"
    if pgrep -x "$proc_name" >/dev/null 2>&1; then
        echo "running"
    elif pgrep -f "$proc_name" >/dev/null 2>&1; then
        echo "running"
    else
        echo "stopped"
    fi
}

count_zombies() {
    local os="$1"
    case "$os" in
        Linux)
            local count
            count=$(ps aux 2>/dev/null | awk '$8 ~ /^Z/ {count++} END {print count+0}')
            echo "$count"
            ;;
        Darwin)
            local count
            count=$(ps aux 2>/dev/null | awk '$8 ~ /^Z/ {count++} END {print count+0}')
            echo "$count"
            ;;
        *)
            echo "0"
            ;;
    esac
}

get_top_processes() {
    ps aux --sort=-%cpu 2>/dev/null | head -6 | tail -5 | awk '{printf "{\"pid\":%s,\"cpu\":%s,\"mem\":%s,\"command\":\"%s\"}", $2, $3, $4, $11}' | paste -sd',' - 2>/dev/null || \
    ps aux -r 2>/dev/null | head -6 | tail -5 | awk '{printf "{\"pid\":%s,\"cpu\":%s,\"mem\":%s,\"command\":\"%s\"}", $2, $3, $4, $11}' | paste -sd',' - 2>/dev/null || \
    echo ""
}

OS="$(uname -s)"
missing_count=0
process_details=""
proc_first=true

IFS=',' read -ra PROC_ARRAY <<< "$CRITICAL_PROCESSES"
for proc_name in "${PROC_ARRAY[@]}"; do
    proc_name=$(echo "$proc_name" | xargs)
    [[ -z "$proc_name" ]] && continue

    proc_status=$(check_process_running "$proc_name")
    if [[ "$proc_status" == "stopped" ]]; then
        missing_count=$((missing_count + 1))
    fi

    [[ "$proc_first" == true ]] && proc_first=false || process_details="${process_details},"
    process_details="${process_details}{\"name\":\"${proc_name}\",\"status\":\"${proc_status}\"}"
done

ZOMBIE_COUNT=$(count_zombies "$OS")
TOTAL_PROCS=$(ps aux 2>/dev/null | wc -l | xargs)
TOP_PROCS=$(get_top_processes)

total_issues=$((missing_count + ZOMBIE_COUNT))

if [[ "$missing_count" -gt 0 ]]; then
    STATUS="CRITICAL"
elif [[ "$ZOMBIE_COUNT" -gt "$THRESHOLD" ]]; then
    STATUS="WARNING"
else
    STATUS="OK"
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cat <<EOF
{"check":"processes","status":"${STATUS}","value":${total_issues},"threshold":${THRESHOLD},"message":"${missing_count} critical process(es) missing, ${ZOMBIE_COUNT} zombie(s)","timestamp":"${TIMESTAMP}","details":{"critical_processes":[${process_details}],"zombie_count":${ZOMBIE_COUNT},"total_processes":${TOTAL_PROCS},"top_by_cpu":[${TOP_PROCS}]}}
EOF
