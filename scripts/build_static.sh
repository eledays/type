#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v terser >/dev/null 2>&1; then
    echo "terser is required to build browser assets" >&2
    exit 1
fi

terser "$project_root/app/static/js/feed.js" \
    --compress \
    --mangle \
    --output "$project_root/app/static/js/feed.min.js"
