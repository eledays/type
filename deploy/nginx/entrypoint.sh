#!/bin/sh
set -eu

certificate="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
if [ -f "$certificate" ]; then
    template="/etc/nginx/templates/type-https.conf.template"
else
    template="/etc/nginx/templates/type-http.conf.template"
fi

envsubst '${DOMAIN}' < "$template" > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
