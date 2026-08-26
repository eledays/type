#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${ENV_FILE:-$project_root/.env.production}"

if [[ ! -r "$env_file" ]]; then
    echo "Production env file is not readable: $env_file" >&2
    exit 1
fi

exec docker compose \
    --env-file "$env_file" \
    --file "$project_root/compose.yaml" \
    --file "$project_root/compose.production.yaml" \
    "$@"
