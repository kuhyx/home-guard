#!/bin/bash

# ============================================================================
# set_release_secrets.sh -- push the shared Android release-signing material
# into this repo's GitHub Actions secrets, so release-apk.yml can sign.
#
# Reads the values from an existing android/key.properties (this repo's own by
# default) rather than from a note or an argument: the keystore path and the
# passwords already live there, gitignored, and retyping them is how a wrong
# password becomes a "CN=Android Debug" APK three steps later. Never prints a
# value. Idempotent -- re-run to rotate.
# ============================================================================

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_NAME
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_DIR
KEY_PROPERTIES="${REPO_DIR}/app/android/key.properties"
GH_REPO="kuhyx/home-guard"

usage() {
    echo "Usage: $SCRIPT_NAME [--key-properties <file>] [--repo <owner/name>]"
    exit 0
}

prop() {
    # Value of key $1 from key.properties; fails loudly when absent.
    local value
    value="$(grep -m1 "^$1=" "$KEY_PROPERTIES" | cut -d= -f2-)"
    [[ -n "$value" ]] || { echo "Error: $1 missing from $KEY_PROPERTIES" >&2; exit 1; }
    printf '%s' "$value"
}

validate_requirements() {
    command -v gh >/dev/null || { echo "Error: gh is not installed" >&2; exit 1; }
    [[ -r "$KEY_PROPERTIES" ]] || {
        echo "Error: $KEY_PROPERTIES is missing or unreadable" >&2
        echo "  (copy one from a sibling app: it is the same shared key)" >&2
        exit 1
    }
    [[ -r "$(prop storeFile)" ]] || {
        echo "Error: keystore $(prop storeFile) is not readable" >&2; exit 1
    }
}

main() {
    validate_requirements
    echo "setting 4 secrets on $GH_REPO from $KEY_PROPERTIES"
    base64 -w0 "$(prop storeFile)" | gh secret set ANDROID_KEYSTORE_BASE64 -R "$GH_REPO"
    prop storePassword | gh secret set ANDROID_KEYSTORE_PASSWORD -R "$GH_REPO"
    prop keyAlias | gh secret set ANDROID_KEY_ALIAS -R "$GH_REPO"
    prop keyPassword | gh secret set ANDROID_KEY_PASSWORD -R "$GH_REPO"
    echo "done:"
    gh secret list -R "$GH_REPO"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --key-properties) KEY_PROPERTIES="$2"; shift 2 ;;
        --repo) GH_REPO="$2"; shift 2 ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

main "$@"
