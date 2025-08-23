#!/usr/bin/env bash
set -euo pipefail

THRESHOLD=1000

while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold) THRESHOLD="$2"; shift 2 ;;
        *) shift ;;
    esac
done

PING_TARGETS="${PING_TARGETS:-8.8.8.8,1.1.1.1}"
DNS_TARGETS="${DNS_TARGETS:-google.com,github.com}"
PORT_CHECKS="${PORT_CHECKS:-}"

OS="$(uname -s)"

ping_host() {
    local host="$1"
    local result
    case "$OS" in
        Linux)  result=$(ping -c 3 -W 5 "$host" 2>&1) ;;
        Darwin) result=$(ping -c 3 -t 5 "$host" 2>&1) ;;
        *)      result=$(ping -c 3 "$host" 2>&1) ;;
    esac

    if [[ $? -ne 0 ]]; then
        echo "FAIL|0"
        return
    fi

    local avg_ms
    avg_ms=$(echo "$result" | tail -1 | awk -F'/' '{print $5}')
    : "${avg_ms:=0}"
    echo "OK|${avg_ms}"
}

check_dns() {
    local domain="$1"
    if nslookup "$domain" >/dev/null 2>&1; then
        echo "OK"
    elif host "$domain" >/dev/null 2>&1; then
        echo "OK"
    else
        echo "FAIL"
    fi
}

check_port() {
    local host="$1"
    local port="$2"
    local timeout=5

    if command -v nc >/dev/null 2>&1; then
        case "$OS" in
            Linux)  nc -z -w "$timeout" "$host" "$port" >/dev/null 2>&1 ;;
            Darwin) nc -z -G "$timeout" "$host" "$port" >/dev/null 2>&1 ;;
            *)      nc -z "$host" "$port" >/dev/null 2>&1 ;;
        esac
    elif command -v bash >/dev/null 2>&1; then
        timeout "$timeout" bash -c "echo >/dev/tcp/${host}/${port}" >/dev/null 2>&1
    else
        return 1
    fi

    if [[ $? -eq 0 ]]; then
        echo "OK"
    else
        echo "FAIL"
    fi
}

failures=0
total_checks=0
ping_details=""
dns_details=""
port_details=""
worst_latency=0

IFS=',' read -ra PING_ARRAY <<< "$PING_TARGETS"
ping_first=true
for target in "${PING_ARRAY[@]}"; do
    target=$(echo "$target" | xargs)
    [[ -z "$target" ]] && continue
    total_checks=$((total_checks + 1))

    result=$(ping_host "$target" || echo "FAIL|0")
    status=$(echo "$result" | cut -d'|' -f1)
    latency=$(echo "$result" | cut -d'|' -f2)

    if [[ "$status" == "FAIL" ]]; then
        failures=$((failures + 1))
    fi

    latency_int=$(awk "BEGIN { printf \"%.0f\", $latency }")
    if [[ "$latency_int" -gt "$worst_latency" ]]; then
        worst_latency="$latency_int"
    fi

    [[ "$ping_first" == true ]] && ping_first=false || ping_details="${ping_details},"
    ping_details="${ping_details}{\"host\":\"${target}\",\"status\":\"${status}\",\"latency_ms\":${latency}}"
done

IFS=',' read -ra DNS_ARRAY <<< "$DNS_TARGETS"
dns_first=true
for target in "${DNS_ARRAY[@]}"; do
    target=$(echo "$target" | xargs)
    [[ -z "$target" ]] && continue
    total_checks=$((total_checks + 1))

    result=$(check_dns "$target")
    if [[ "$result" == "FAIL" ]]; then
        failures=$((failures + 1))
    fi

    [[ "$dns_first" == true ]] && dns_first=false || dns_details="${dns_details},"
    dns_details="${dns_details}{\"domain\":\"${target}\",\"status\":\"${result}\"}"
done

if [[ -n "$PORT_CHECKS" ]]; then
    IFS=',' read -ra PORT_ARRAY <<< "$PORT_CHECKS"
    port_first=true
    for entry in "${PORT_ARRAY[@]}"; do
        entry=$(echo "$entry" | xargs)
        [[ -z "$entry" ]] && continue
        total_checks=$((total_checks + 1))

        local_host=$(echo "$entry" | cut -d':' -f1)
        local_port=$(echo "$entry" | cut -d':' -f2)
        result=$(check_port "$local_host" "$local_port")
        if [[ "$result" == "FAIL" ]]; then
            failures=$((failures + 1))
        fi

        [[ "$port_first" == true ]] && port_first=false || port_details="${port_details},"
        port_details="${port_details}{\"host\":\"${local_host}\",\"port\":${local_port},\"status\":\"${result}\"}"
    done
fi

if [[ "$total_checks" -eq 0 ]]; then
    fail_pct=0
else
    fail_pct=$(awk "BEGIN { printf \"%.0f\", ($failures / $total_checks) * 100 }")
fi

if [[ "$failures" -gt $((total_checks / 2)) ]]; then
    STATUS="CRITICAL"
elif [[ "$failures" -gt 0 ]] || [[ "$worst_latency" -ge "$THRESHOLD" ]]; then
    STATUS="WARNING"
else
    STATUS="OK"
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cat <<EOF
{"check":"network","status":"${STATUS}","value":${failures},"threshold":${THRESHOLD},"message":"${failures}/${total_checks} checks failed, worst latency ${worst_latency}ms","timestamp":"${TIMESTAMP}","details":{"ping":[${ping_details}],"dns":[${dns_details}],"ports":[${port_details}],"total_checks":${total_checks},"failures":${failures}}}
EOF
