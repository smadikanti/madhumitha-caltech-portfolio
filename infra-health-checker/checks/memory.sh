#!/usr/bin/env bash
set -euo pipefail

THRESHOLD=80

while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold) THRESHOLD="$2"; shift 2 ;;
        *) shift ;;
    esac
done

get_memory_linux() {
    local total used available swap_total swap_used
    total=$(awk '/^MemTotal/ {print $2}' /proc/meminfo)
    available=$(awk '/^MemAvailable/ {print $2}' /proc/meminfo)
    used=$((total - available))
    swap_total=$(awk '/^SwapTotal/ {print $2}' /proc/meminfo)
    swap_used=$((swap_total - $(awk '/^SwapFree/ {print $2}' /proc/meminfo)))

    local total_mb=$((total / 1024))
    local used_mb=$((used / 1024))
    local available_mb=$((available / 1024))
    local swap_total_mb=$((swap_total / 1024))
    local swap_used_mb=$((swap_used / 1024))

    echo "${total_mb} ${used_mb} ${available_mb} ${swap_total_mb} ${swap_used_mb}"
}

get_memory_macos() {
    local page_size
    page_size=$(sysctl -n hw.pagesize)

    local total_bytes
    total_bytes=$(sysctl -n hw.memsize)
    local total_mb=$((total_bytes / 1024 / 1024))

    local vm_stat_output
    vm_stat_output=$(vm_stat)

    local pages_free pages_active pages_inactive pages_speculative pages_wired
    pages_free=$(echo "$vm_stat_output" | awk '/Pages free/ {gsub(/\./, "", $3); print $3}')
    pages_active=$(echo "$vm_stat_output" | awk '/Pages active/ {gsub(/\./, "", $3); print $3}')
    pages_inactive=$(echo "$vm_stat_output" | awk '/Pages inactive/ {gsub(/\./, "", $3); print $3}')
    pages_speculative=$(echo "$vm_stat_output" | awk '/Pages speculative/ {gsub(/\./, "", $3); print $3}')
    pages_wired=$(echo "$vm_stat_output" | awk '/Pages wired/ {gsub(/\./, "", $4); print $4}')

    : "${pages_free:=0}"
    : "${pages_active:=0}"
    : "${pages_inactive:=0}"
    : "${pages_speculative:=0}"
    : "${pages_wired:=0}"

    local available_pages=$((pages_free + pages_inactive + pages_speculative))
    local available_mb=$(( (available_pages * page_size) / 1024 / 1024 ))
    local used_mb=$((total_mb - available_mb))

    local swap_info
    swap_info=$(sysctl -n vm.swapusage 2>/dev/null || echo "total = 0.00M  used = 0.00M  free = 0.00M")
    local swap_total_mb swap_used_mb
    swap_total_mb=$(echo "$swap_info" | awk '{gsub(/M/, "", $3); printf "%.0f", $3}')
    swap_used_mb=$(echo "$swap_info" | awk '{gsub(/M/, "", $6); printf "%.0f", $6}')

    echo "${total_mb} ${used_mb} ${available_mb} ${swap_total_mb} ${swap_used_mb}"
}

evaluate_status() {
    local pct="$1"
    local threshold="$2"
    local critical=$((threshold + (100 - threshold) * 3 / 4))

    local int_pct
    int_pct=$(awk "BEGIN { printf \"%.0f\", $pct }")

    if [[ "$int_pct" -ge "$critical" ]]; then
        echo "CRITICAL"
    elif [[ "$int_pct" -ge "$threshold" ]]; then
        echo "WARNING"
    else
        echo "OK"
    fi
}

OS="$(uname -s)"
case "$OS" in
    Linux)  read -r TOTAL USED AVAILABLE SWAP_TOTAL SWAP_USED <<< "$(get_memory_linux)" ;;
    Darwin) read -r TOTAL USED AVAILABLE SWAP_TOTAL SWAP_USED <<< "$(get_memory_macos)" ;;
    *)      TOTAL=0; USED=0; AVAILABLE=0; SWAP_TOTAL=0; SWAP_USED=0 ;;
esac

if [[ "$TOTAL" -gt 0 ]]; then
    USAGE_PCT=$(awk "BEGIN { printf \"%.1f\", ($USED / $TOTAL) * 100 }")
else
    USAGE_PCT="0.0"
fi

STATUS=$(evaluate_status "$USAGE_PCT" "$THRESHOLD")
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cat <<EOF
{"check":"memory","status":"${STATUS}","value":${USAGE_PCT},"threshold":${THRESHOLD},"message":"Memory usage at ${USAGE_PCT}% (${USED}MB / ${TOTAL}MB)","timestamp":"${TIMESTAMP}","details":{"total_mb":${TOTAL},"used_mb":${USED},"available_mb":${AVAILABLE},"swap_total_mb":${SWAP_TOTAL},"swap_used_mb":${SWAP_USED}}}
EOF
