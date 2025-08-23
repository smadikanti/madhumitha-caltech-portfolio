#!/usr/bin/env bash
set -euo pipefail

THRESHOLD=80

while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold) THRESHOLD="$2"; shift 2 ;;
        *) shift ;;
    esac
done

evaluate_status() {
    local pct="$1"
    local threshold="$2"
    local critical=$(( threshold + (100 - threshold) * 3 / 4 ))

    if [[ "$pct" -ge "$critical" ]]; then
        echo "CRITICAL"
    elif [[ "$pct" -ge "$threshold" ]]; then
        echo "WARNING"
    else
        echo "OK"
    fi
}

get_disk_info() {
    local os="$1"
    local mount_details=""
    local worst_pct=0
    local worst_mount="/"
    local first=true

    while IFS= read -r line; do
        local filesystem size used avail pct mount
        read -r filesystem size used avail pct mount <<< "$line"
        pct="${pct%\%}"

        if [[ "$pct" -gt "$worst_pct" ]]; then
            worst_pct="$pct"
            worst_mount="$mount"
        fi

        if [[ "$first" == true ]]; then
            first=false
        else
            mount_details="${mount_details},"
        fi

        mount_details="${mount_details}{\"mount\":\"${mount}\",\"filesystem\":\"${filesystem}\",\"size_kb\":${size},\"used_kb\":${used},\"available_kb\":${avail},\"usage_pct\":${pct}}"
    done < <(df -Pk 2>/dev/null | awk 'NR>1 && $1 !~ /^(tmpfs|devtmpfs|overlay|none|devfs|map)/ && $2 ~ /^[0-9]+$/ {print}')

    echo "${worst_pct}|${worst_mount}|${mount_details}"
}

result=$(get_disk_info "$(uname -s)")
WORST_PCT=$(echo "$result" | cut -d'|' -f1)
WORST_MOUNT=$(echo "$result" | cut -d'|' -f2)
MOUNT_DETAILS=$(echo "$result" | cut -d'|' -f3-)

STATUS=$(evaluate_status "$WORST_PCT" "$THRESHOLD")
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cat <<EOF
{"check":"disk","status":"${STATUS}","value":${WORST_PCT},"threshold":${THRESHOLD},"message":"Worst disk usage at ${WORST_PCT}% on ${WORST_MOUNT}","timestamp":"${TIMESTAMP}","details":{"mounts":[${MOUNT_DETAILS}]}}
EOF
