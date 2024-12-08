#!/usr/bin/env bash
set -euo pipefail

readonly MAX_RETRIES="${HEALTH_CHECK_RETRIES:-10}"
readonly RETRY_INTERVAL="${HEALTH_CHECK_INTERVAL:-5}"
readonly TIMEOUT="${HEALTH_CHECK_TIMEOUT:-5}"

usage() {
    cat <<EOF
Usage: $(basename "$0") <url>

Verify that the application at <url> is healthy.
Retries up to $MAX_RETRIES times with ${RETRY_INTERVAL}s intervals.

Environment variables:
  HEALTH_CHECK_RETRIES   Number of attempts (default: 10)
  HEALTH_CHECK_INTERVAL  Seconds between retries (default: 5)
  HEALTH_CHECK_TIMEOUT   Curl timeout in seconds (default: 5)
EOF
}

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$@"; exit 1; }

check_health() {
    local url="$1"
    local health_url="${url%/}/health"

    local http_code body
    body=$(curl -sf --max-time "$TIMEOUT" -w '\n%{http_code}' "$health_url" 2>/dev/null) || return 1
    http_code=$(echo "$body" | tail -1)
    body=$(echo "$body" | sed '$d')

    if [[ "$http_code" -ne 200 ]]; then
        err "Health endpoint returned HTTP $http_code"
        return 1
    fi

    local status
    status=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null) || {
        err "Failed to parse health response JSON"
        return 1
    }

    if [[ "$status" != "healthy" ]]; then
        err "Application status: $status (expected: healthy)"
        return 1
    fi

    return 0
}

main() {
    if [[ $# -lt 1 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
        usage
        [[ $# -lt 1 ]] && exit 1 || exit 0
    fi

    local url="$1"
    log "Health check: $url (max ${MAX_RETRIES} attempts, ${RETRY_INTERVAL}s interval)"

    local attempt=1
    while [[ $attempt -le $MAX_RETRIES ]]; do
        log "Attempt $attempt/$MAX_RETRIES..."

        if check_health "$url"; then
            log "Health check passed ✓"
            return 0
        fi

        if [[ $attempt -lt $MAX_RETRIES ]]; then
            log "Retrying in ${RETRY_INTERVAL}s..."
            sleep "$RETRY_INTERVAL"
        fi

        ((attempt++))
    done

    die "Health check failed after $MAX_RETRIES attempts"
}

main "$@"
