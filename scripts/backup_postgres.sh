#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${ENV_FILE:-$project_root/.env.production}"
backup_dir="${BACKUP_DIR:-$project_root/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-30}"
mirror_dir="${BACKUP_MIRROR_DIR:-}"
age_recipient="${BACKUP_AGE_RECIPIENT:-}"
compose_script="${COMPOSE_SCRIPT:-$project_root/scripts/compose_production.sh}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

if [[ ! -r "$env_file" ]]; then
    echo "Production env file is not readable: $env_file" >&2
    exit 1
fi
if [[ ! "$retention_days" =~ ^[0-9]+$ ]]; then
    echo "BACKUP_RETENTION_DAYS must be a non-negative integer" >&2
    exit 1
fi
if [[ -n "$age_recipient" ]] && ! command -v age >/dev/null; then
    echo "age is required when BACKUP_AGE_RECIPIENT is set" >&2
    exit 1
fi

umask 077
mkdir -p "$backup_dir"
temporary_dump="$(mktemp "$backup_dir/.type-$timestamp.XXXXXX.dump")"
encrypted_temp=""
cleanup() {
    rm -f -- "$temporary_dump"
    if [[ -n "$encrypted_temp" ]]; then
        rm -f -- "$encrypted_temp"
    fi
}
trap cleanup EXIT

ENV_FILE="$env_file" "$compose_script" \
    exec -T postgres sh -c \
    'exec pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom' \
    > "$temporary_dump"

if [[ ! -s "$temporary_dump" ]]; then
    echo "Backup is empty" >&2
    exit 1
fi
ENV_FILE="$env_file" "$compose_script" exec -T postgres \
    pg_restore --list < "$temporary_dump" >/dev/null

final_path="$backup_dir/type-$timestamp.dump"
if [[ -n "$age_recipient" ]]; then
    encrypted_temp="$backup_dir/.type-$timestamp.dump.age.tmp"
    age --recipient "$age_recipient" --output "$encrypted_temp" "$temporary_dump"
    final_path="$backup_dir/type-$timestamp.dump.age"
    mv -- "$encrypted_temp" "$final_path"
else
    mv -- "$temporary_dump" "$final_path"
fi

if [[ -n "$mirror_dir" ]]; then
    mkdir -p "$mirror_dir"
    mirror_temp="$mirror_dir/.$(basename "$final_path").tmp"
    cp -- "$final_path" "$mirror_temp"
    mv -- "$mirror_temp" "$mirror_dir/$(basename "$final_path")"
fi

find "$backup_dir" -maxdepth 1 -type f \
    \( -name 'type-*.dump' -o -name 'type-*.dump.age' \) \
    -mtime "+$retention_days" -delete

echo "Backup created and verified: $final_path"
if [[ -n "$mirror_dir" ]]; then
    echo "Backup mirrored to: $mirror_dir/$(basename "$final_path")"
fi
