#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${ENV_FILE:-$project_root/.env.production}"
backup_dir="${BACKUP_DIR:-$project_root/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

if [[ ! -r "$env_file" ]]; then
    echo "Production env file is not readable: $env_file" >&2
    exit 1
fi

umask 077
mkdir -p "$backup_dir"

ENV_FILE="$env_file" "$project_root/scripts/compose_production.sh" \
    exec -T postgres sh -c \
    'exec pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom' \
    > "$backup_dir/type-$timestamp.dump"

echo "Backup created: $backup_dir/type-$timestamp.dump"
