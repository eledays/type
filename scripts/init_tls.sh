#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$project_root/scripts/compose_production.sh" up --build --detach \
    app postgres redis nginx

"$project_root/scripts/compose_production.sh" run --rm --no-deps certbot -c '
    exec certbot certonly \
        --webroot \
        --webroot-path /var/www/certbot \
        --domain "$DOMAIN" \
        --email "$CERTBOT_EMAIL" \
        --agree-tos \
        --no-eff-email \
        --non-interactive
'

"$project_root/scripts/compose_production.sh" up --detach --force-recreate --no-deps nginx

echo "TLS initialized. Check the external /health/ready endpoint."
