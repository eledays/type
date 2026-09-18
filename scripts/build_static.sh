#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

terser_binary="${TERSER_BINARY:-$project_root/node_modules/.bin/terser}"
output_path="${OUTPUT_PATH:-$project_root/app/static/js/feed.min.js}"

if [[ ! -x "$terser_binary" ]]; then
    echo "Run npm ci before building browser assets" >&2
    exit 1
fi

"$terser_binary" \
    "$project_root/app/static/js/feed-helpers.js" \
    "$project_root/app/static/js/feed-api.js" \
    "$project_root/app/static/js/feed.js" \
    --compress \
    --mangle \
    --output "$output_path"
