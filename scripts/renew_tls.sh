#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$project_root/scripts/compose_production.sh" run --rm --no-deps certbot -c '
    exec certbot renew \
        --webroot \
        --webroot-path /var/www/certbot \
        --quiet \
        --non-interactive
'

"$project_root/scripts/compose_production.sh" exec -T nginx nginx -s reload
