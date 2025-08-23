#!/usr/bin/env bash
set -euo pipefail

THRESHOLD=80
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold) THRESHOLD="$2"; shift 2 ;;
        *) shift ;;
    esac
done

get_cpu_usage_linux() {
    local idle_line
    idle_line=$(grep '^cpu ' /proc/stat)
    local user nice system idle iowait irq softirq steal
    read -r _ user nice system idle iowait irq softirq steal _ <<< "$idle_line"
    local total=$((user + nice + system + idle + iowait + irq + softirq + steal))
    local busy=$((total - idle - iowait))

    sleep 1

    idle_line=$(grep '^cpu ' /proc/stat)
    local user2 nice2 system2 idle2 iowait2 irq2 softirq2 steal2
    read -r _ user2 nice2 system2 idle2 iowait2 irq2 softirq2 steal2 _ <<< "$idle_line"
    local total2=$((user2 + nice2 + system2 + idle2 + iowait2 + irq2 + softirq2 + steal2))
    local busy2=$((total2 - idle2 - iowait2))

    local diff_total=$((total2 - total))
    local diff_busy=$((busy2 - busy))

    if [[ "$diff_total" -eq 0 ]]; then
        echo "0.0"
        return
    fi

    awk "BEGIN { printf \"%.1f\", ($diff_busy / $diff_total) * 100 }"
}

get_cpu_usage_macos() {
    local cpu_line
    cpu_line=$(top -l 2 -n 0 -s 1 | grep -E "^CPU usage" | tail -1)
    local user sys idle
    user=$(echo "$cpu_line" | awk '{print $3}' | tr -d '%')
    sys=$(echo "$cpu_line" | awk '{print $5}' | tr -d '%')
    awk "BEGIN { printf \"%.1f\", $user + $sys }"
}

get_load_average() {
    uptime | awk -F'load average[s]?:' '{print $2}' | awk -F',' '{gsub(/^ +/, "", $1); print $1}'
}

evaluate_status() {
    local value="$1"
    local threshold="$2"
    local critical_threshold
    critical_threshold=$(awk "BEGIN { printf \"%.0f\", $threshold * 1.1875 }")
    if [[ "$critical_threshold" -gt 100 ]]; then
        critical_threshold=95
    fi

    local int_value
    int_value=$(awk "BEGIN { printf \"%.0f\", $value }")

    if [[ "$int_value" -ge "$critical_threshold" ]]; then
        echo "CRITICAL"
    elif [[ "$int_value" -ge "$threshold" ]]; then
        echo "WARNING"
    else
        echo "OK"
    fi
}

OS="$(uname -s)"
case "$OS" in
    Linux)  CPU_USAGE=$(get_cpu_usage_linux) ;;
    Darwin) CPU_USAGE=$(get_cpu_usage_macos) ;;
    *)      CPU_USAGE="0.0" ;;
esac

LOAD_AVG=$(get_load_average)
NUM_CPUS=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)
STATUS=$(evaluate_status "$CPU_USAGE" "$THRESHOLD")
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cat <<EOF
{"check":"cpu","status":"${STATUS}","value":${CPU_USAGE},"threshold":${THRESHOLD},"message":"CPU usage at ${CPU_USAGE}%","timestamp":"${TIMESTAMP}","details":{"load_average":"${LOAD_AVG}","num_cpus":${NUM_CPUS}}}
EOF
