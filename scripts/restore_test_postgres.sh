#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${ENV_FILE:-$project_root/.env.production}"
backup_dir="${BACKUP_DIR:-$project_root/backups}"
compose_script="${COMPOSE_SCRIPT:-$project_root/scripts/compose_production.sh}"
age_identity_file="${BACKUP_AGE_IDENTITY_FILE:-}"
backup_path="${1:-}"
restore_database="type_restore_test_$(date -u +%Y%m%d%H%M%S)_$$"

if [[ ! -r "$env_file" ]]; then
    echo "Production env file is not readable: $env_file" >&2
    exit 1
fi
if [[ -z "$backup_path" ]]; then
    backup_path="$(find "$backup_dir" -maxdepth 1 -type f \
        \( -name 'type-*.dump' -o -name 'type-*.dump.age' \) \
        -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"
fi
if [[ -z "$backup_path" || ! -r "$backup_path" ]]; then
    echo "No readable backup found" >&2
    exit 1
fi
if [[ "$backup_path" == *.age ]] && ! command -v age >/dev/null; then
    echo "age is required to restore encrypted backups" >&2
    exit 1
fi

compose() { ENV_FILE="$env_file" "$compose_script" "$@"; }
drop_restore_database() {
    compose exec -T postgres sh -c \
        'exec dropdb --if-exists --force --username "$POSTGRES_USER" "$1"' \
        sh "$restore_database" >/dev/null 2>&1 || true
}
trap drop_restore_database EXIT

compose exec -T postgres sh -c \
    'exec createdb --username "$POSTGRES_USER" "$1"' sh "$restore_database"

restore_plain() {
    compose exec -T postgres sh -c \
        'exec pg_restore --username "$POSTGRES_USER" --dbname "$1" --no-owner --no-privileges' \
        sh "$restore_database"
}

if [[ "$backup_path" == *.age ]]; then
    if [[ -n "$age_identity_file" ]]; then
        age --decrypt --identity "$age_identity_file" "$backup_path" | restore_plain
    else
        age --decrypt "$backup_path" | restore_plain
    fi
else
    restore_plain < "$backup_path"
fi

compose exec -T postgres sh -c \
    'exec psql --username "$POSTGRES_USER" --dbname "$1" --tuples-only --command "$2"' \
    sh "$restore_database" "SELECT 1 FROM alembic_version LIMIT 1" >/dev/null

echo "Restore test passed: $(basename "$backup_path")"
