#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
readonly STATE_DIR="${PROJECT_ROOT}/.deploy-state"
readonly REGISTRY="${REGISTRY:-ghcr.io}"
readonly IMAGE_NAME="${IMAGE_NAME:-ci-cd-toolkit}"
readonly DEPLOY_STRATEGY="${DEPLOY_STRATEGY:-rolling}"

usage() {
    cat <<EOF
Usage: $(basename "$0") <environment> <image-tag> [--strategy rolling|blue-green]

Deploy the application to the specified environment.

Arguments:
  environment   One of: dev, staging, prod
  image-tag     Docker image tag to deploy

Options:
  --strategy    Deployment strategy (default: rolling)
  -h, --help    Show this help
EOF
}

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
err() { log "ERROR: $*" >&2; }
die() { err "$@"; exit 1; }

validate_environment() {
    local env="$1"
    case "$env" in
        dev|staging|prod) return 0 ;;
        *) die "Invalid environment: $env. Must be dev, staging, or prod." ;;
    esac
}

save_deploy_state() {
    local env="$1" tag="$2"
    mkdir -p "$STATE_DIR"
    local state_file="${STATE_DIR}/${env}.state"

    if [[ -f "$state_file" ]]; then
        cp "$state_file" "${state_file}.prev"
    fi

    cat > "$state_file" <<STATE
DEPLOYED_TAG=${tag}
DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DEPLOYED_BY=${USER:-ci}
STATE
    log "Deploy state saved to $state_file"
}

deploy_rolling() {
    local env="$1" tag="$2"
    local full_image="${REGISTRY}/${IMAGE_NAME}:${tag}"

    log "Rolling deployment: $full_image → $env"

    if command -v kubectl &>/dev/null; then
        local namespace="ci-cd-toolkit-${env}"

        kubectl set image "deployment/ci-cd-toolkit" \
            "app=${full_image}" \
            --namespace="$namespace" \
            --record 2>/dev/null || true

        log "Waiting for rollout to complete..."
        kubectl rollout status "deployment/ci-cd-toolkit" \
            --namespace="$namespace" \
            --timeout=300s 2>/dev/null || {
                err "Rollout timed out — triggering automatic rollback"
                kubectl rollout undo "deployment/ci-cd-toolkit" \
                    --namespace="$namespace" 2>/dev/null || true
                die "Deployment failed and was rolled back"
            }
    else
        log "[dry-run] kubectl not available — simulating rolling deploy"
        log "[dry-run] Would set image to $full_image in namespace ci-cd-toolkit-${env}"
    fi
}

deploy_blue_green() {
    local env="$1" tag="$2"
    local full_image="${REGISTRY}/${IMAGE_NAME}:${tag}"
    local namespace="ci-cd-toolkit-${env}"

    log "Blue-green deployment: $full_image → $env"

    if ! command -v kubectl &>/dev/null; then
        log "[dry-run] kubectl not available — simulating blue-green deploy"
        log "[dry-run] Would create green deployment with $full_image"
        log "[dry-run] Would switch service selector after health check passes"
        return 0
    fi

    local current_color
    current_color=$(kubectl get svc ci-cd-toolkit -n "$namespace" \
        -o jsonpath='{.spec.selector.slot}' 2>/dev/null || echo "blue")

    local new_color
    if [[ "$current_color" == "blue" ]]; then
        new_color="green"
    else
        new_color="blue"
    fi

    log "Current slot: $current_color → deploying to: $new_color"

    kubectl set image "deployment/ci-cd-toolkit-${new_color}" \
        "app=${full_image}" \
        --namespace="$namespace" 2>/dev/null || true

    kubectl rollout status "deployment/ci-cd-toolkit-${new_color}" \
        --namespace="$namespace" \
        --timeout=300s

    log "Running health check on $new_color slot..."
    bash "${SCRIPT_DIR}/health-check.sh" \
        "http://ci-cd-toolkit-${new_color}.${namespace}.svc.cluster.local" || {
            die "Health check failed on $new_color — aborting switch"
        }

    log "Switching traffic to $new_color"
    kubectl patch svc ci-cd-toolkit -n "$namespace" \
        -p "{\"spec\":{\"selector\":{\"slot\":\"${new_color}\"}}}"

    log "Traffic switched. Old slot ($current_color) kept for rollback."
}

main() {
    local strategy="$DEPLOY_STRATEGY"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --strategy) strategy="$2"; shift 2 ;;
            -h|--help) usage; exit 0 ;;
            *) break ;;
        esac
    done

    if [[ $# -lt 2 ]]; then
        usage
        die "Missing required arguments"
    fi

    local env="$1"
    local tag="$2"

    validate_environment "$env"

    log "═══════════════════════════════════════"
    log "Deploying to: $env"
    log "Image tag:    $tag"
    log "Strategy:     $strategy"
    log "═══════════════════════════════════════"

    save_deploy_state "$env" "$tag"

    case "$strategy" in
        rolling)    deploy_rolling "$env" "$tag" ;;
        blue-green) deploy_blue_green "$env" "$tag" ;;
        *) die "Unknown strategy: $strategy" ;;
    esac

    log "Running post-deployment health check..."
    bash "${SCRIPT_DIR}/health-check.sh" "${HEALTH_CHECK_URL:-http://localhost:8000}" || {
        err "Post-deploy health check failed"
        exit 1
    }

    log "Deployment to $env complete ✓"
}

main "$@"
