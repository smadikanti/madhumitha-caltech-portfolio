#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
readonly STATE_DIR="${PROJECT_ROOT}/.deploy-state"

usage() {
    cat <<EOF
Usage: $(basename "$0") [--dry-run] <environment>

Rollback to the previously deployed version.

Arguments:
  environment   One of: dev, staging, prod

Options:
  --dry-run     Show what would be rolled back without executing
  -h, --help    Show this help
EOF
}

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$@"; exit 1; }

get_previous_state() {
    local env="$1"
    local prev_file="${STATE_DIR}/${env}.state.prev"

    if [[ ! -f "$prev_file" ]]; then
        die "No previous deployment state found for '$env'. Cannot rollback."
    fi

    # shellcheck source=/dev/null
    source "$prev_file"
    echo "${DEPLOYED_TAG}"
}

rollback_kubernetes() {
    local env="$1" dry_run="$2"
    local namespace="ci-cd-toolkit-${env}"

    if ! command -v kubectl &>/dev/null; then
        log "[dry-run] kubectl not available — simulating rollback"
        return 0
    fi

    if [[ "$dry_run" == "true" ]]; then
        log "[dry-run] Would run: kubectl rollout undo deployment/ci-cd-toolkit -n $namespace"
        kubectl rollout history "deployment/ci-cd-toolkit" \
            --namespace="$namespace" 2>/dev/null || true
        return 0
    fi

    log "Rolling back deployment in namespace $namespace..."
    kubectl rollout undo "deployment/ci-cd-toolkit" \
        --namespace="$namespace"

    kubectl rollout status "deployment/ci-cd-toolkit" \
        --namespace="$namespace" \
        --timeout=300s
}

restore_state_file() {
    local env="$1"
    local state_file="${STATE_DIR}/${env}.state"
    local prev_file="${state_file}.prev"

    if [[ -f "$prev_file" ]]; then
        cp "$prev_file" "$state_file"
        log "State file restored from previous deployment"
    fi
}

main() {
    local dry_run="false"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) dry_run="true"; shift ;;
            -h|--help) usage; exit 0 ;;
            *) break ;;
        esac
    done

    if [[ $# -lt 1 ]]; then
        usage
        die "Missing required environment argument"
    fi

    local env="$1"

    case "$env" in
        dev|staging|prod) ;;
        *) die "Invalid environment: $env" ;;
    esac

    local prev_tag
    prev_tag=$(get_previous_state "$env")

    log "═══════════════════════════════════════"
    log "Rollback environment: $env"
    log "Target version:       $prev_tag"
    log "Dry run:              $dry_run"
    log "═══════════════════════════════════════"

    if [[ "$dry_run" == "true" ]]; then
        log "[dry-run] Would rollback $env to tag: $prev_tag"
        rollback_kubernetes "$env" "$dry_run"
        return 0
    fi

    rollback_kubernetes "$env" "$dry_run"
    restore_state_file "$env"

    log "Running post-rollback health check..."
    bash "${SCRIPT_DIR}/health-check.sh" "${HEALTH_CHECK_URL:-http://localhost:8000}" || {
        err "Health check failed after rollback"
        exit 1
    }

    log "Rollback to $prev_tag complete ✓"
}

main "$@"
