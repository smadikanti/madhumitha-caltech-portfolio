#!/usr/bin/env bash
set -euo pipefail

readonly VERSION_FILE="app/__init__.py"

usage() {
    cat <<EOF
Usage: $(basename "$0") <major|minor|patch> [--tag] [--push]

Bump the semantic version, update source files, and optionally create a git tag.

Arguments:
  major    Bump major version (X.0.0)
  minor    Bump minor version (x.Y.0)
  patch    Bump patch version (x.y.Z)

Options:
  --tag    Create a git tag for the new version
  --push   Push the tag to origin (implies --tag)
  -h       Show this help
EOF
}

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

get_current_version() {
    local version
    version=$(grep -oP '__version__\s*=\s*"\K[^"]+' "$VERSION_FILE" 2>/dev/null) || {
        die "Could not read version from $VERSION_FILE"
    }
    echo "$version"
}

bump_version() {
    local current="$1" part="$2"

    IFS='.' read -r major minor patch <<< "$current"

    case "$part" in
        major) major=$((major + 1)); minor=0; patch=0 ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        patch) patch=$((patch + 1)) ;;
    esac

    echo "${major}.${minor}.${patch}"
}

update_version_file() {
    local new_version="$1"

    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "s/__version__ = \".*\"/__version__ = \"${new_version}\"/" "$VERSION_FILE"
    else
        sed -i "s/__version__ = \".*\"/__version__ = \"${new_version}\"/" "$VERSION_FILE"
    fi

    log "Updated $VERSION_FILE → $new_version"
}

update_k8s_configmap() {
    local new_version="$1"
    local configmap="k8s/configmap.yaml"

    if [[ -f "$configmap" ]]; then
        if [[ "$(uname)" == "Darwin" ]]; then
            sed -i '' "s/APP_VERSION: \".*\"/APP_VERSION: \"${new_version}\"/" "$configmap"
        else
            sed -i "s/APP_VERSION: \".*\"/APP_VERSION: \"${new_version}\"/" "$configmap"
        fi
        log "Updated $configmap → $new_version"
    fi
}

main() {
    local do_tag="false"
    local do_push="false"
    local bump_part=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            major|minor|patch) bump_part="$1"; shift ;;
            --tag) do_tag="true"; shift ;;
            --push) do_tag="true"; do_push="true"; shift ;;
            -h|--help) usage; exit 0 ;;
            *) die "Unknown argument: $1" ;;
        esac
    done

    if [[ -z "$bump_part" ]]; then
        usage
        die "Version bump type required"
    fi

    local current new
    current=$(get_current_version)
    new=$(bump_version "$current" "$bump_part")

    log "Version bump: $current → $new ($bump_part)"

    update_version_file "$new"
    update_k8s_configmap "$new"

    if [[ "$do_tag" == "true" ]]; then
        git add "$VERSION_FILE" k8s/configmap.yaml 2>/dev/null || true
        git commit -m "chore: bump version to ${new}" || true
        git tag -a "v${new}" -m "Release v${new}"
        log "Created git tag: v${new}"

        if [[ "$do_push" == "true" ]]; then
            git push origin "v${new}"
            log "Pushed tag v${new} to origin"
        fi
    fi

    echo "$new"
}

main "$@"
