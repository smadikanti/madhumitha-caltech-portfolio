#!/usr/bin/env bash
set -euo pipefail

THRESHOLD=80

while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold) THRESHOLD="$2"; shift 2 ;;
        *) shift ;;
    esac
done

check_docker_daemon() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "not_installed"
        return
    fi
    if docker info >/dev/null 2>&1; then
        echo "running"
    else
        echo "stopped"
    fi
}

get_container_stats() {
    local containers
    containers=$(docker ps --format '{{.ID}}|{{.Names}}|{{.Status}}|{{.Image}}' 2>/dev/null || echo "")

    if [[ -z "$containers" ]]; then
        echo "[]"
        return
    fi

    local result=""
    local first=true

    while IFS='|' read -r id name status image; do
        local health="unknown"
        local inspect_health
        inspect_health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id" 2>/dev/null || echo "unknown")
        health="$inspect_health"

        local running_status="running"
        if echo "$status" | grep -qi "exited\|dead\|created"; then
            running_status="stopped"
        fi

        [[ "$first" == true ]] && first=false || result="${result},"
        result="${result}{\"id\":\"${id}\",\"name\":\"${name}\",\"status\":\"${running_status}\",\"health\":\"${health}\",\"image\":\"${image}\"}"
    done <<< "$containers"

    echo "[${result}]"
}

get_image_disk_usage() {
    local total_size
    total_size=$(docker system df --format '{{.Size}}' 2>/dev/null | head -1 || echo "0B")
    echo "$total_size"
}

count_unhealthy_containers() {
    local unhealthy
    unhealthy=$(docker ps --filter health=unhealthy --format '{{.ID}}' 2>/dev/null | wc -l | xargs)
    echo "$unhealthy"
}

DAEMON_STATUS=$(check_docker_daemon)

if [[ "$DAEMON_STATUS" == "not_installed" ]]; then
    TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    cat <<EOF
{"check":"docker","status":"OK","value":0,"threshold":${THRESHOLD},"message":"Docker not installed, skipping","timestamp":"${TIMESTAMP}","details":{"daemon":"not_installed","containers":[],"image_disk_usage":"0B"}}
EOF
    exit 0
fi

if [[ "$DAEMON_STATUS" == "stopped" ]]; then
    TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    cat <<EOF
{"check":"docker","status":"WARNING","value":0,"threshold":${THRESHOLD},"message":"Docker daemon is not running","timestamp":"${TIMESTAMP}","details":{"daemon":"stopped","containers":[],"image_disk_usage":"0B"}}
EOF
    exit 0
fi

CONTAINER_JSON=$(get_container_stats)
IMAGE_USAGE=$(get_image_disk_usage)
UNHEALTHY=$(count_unhealthy_containers)
RUNNING_COUNT=$(docker ps -q 2>/dev/null | wc -l | xargs)
TOTAL_COUNT=$(docker ps -aq 2>/dev/null | wc -l | xargs)
STOPPED_COUNT=$((TOTAL_COUNT - RUNNING_COUNT))

if [[ "$UNHEALTHY" -gt 0 ]]; then
    STATUS="CRITICAL"
elif [[ "$STOPPED_COUNT" -gt 0 ]]; then
    STATUS="WARNING"
else
    STATUS="OK"
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cat <<EOF
{"check":"docker","status":"${STATUS}","value":${UNHEALTHY},"threshold":${THRESHOLD},"message":"${RUNNING_COUNT} running, ${STOPPED_COUNT} stopped, ${UNHEALTHY} unhealthy","timestamp":"${TIMESTAMP}","details":{"daemon":"${DAEMON_STATUS}","running":${RUNNING_COUNT},"stopped":${STOPPED_COUNT},"unhealthy":${UNHEALTHY},"containers":${CONTAINER_JSON},"image_disk_usage":"${IMAGE_USAGE}"}}
EOF
