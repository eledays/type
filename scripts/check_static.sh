#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary_output="$(mktemp)"
cleanup() { rm -f -- "$temporary_output"; }
trap cleanup EXIT

OUTPUT_PATH="$temporary_output" "$project_root/scripts/build_static.sh"
if ! cmp --silent "$temporary_output" "$project_root/app/static/js/feed.min.js"; then
    echo "Browser bundle is stale; run npm run build" >&2
    exit 1
fi
