FROM nginx:1.28.3-alpine

COPY app/static /usr/share/nginx/html/static
COPY deploy/nginx/http.conf.template /etc/nginx/templates/type-http.conf.template
COPY deploy/nginx/https.conf.template /etc/nginx/templates/type-https.conf.template
COPY deploy/nginx/entrypoint.sh /usr/local/bin/type-nginx-entrypoint

RUN chmod +x /usr/local/bin/type-nginx-entrypoint \
    && rm -f /etc/nginx/conf.d/default.conf

ENTRYPOINT ["/usr/local/bin/type-nginx-entrypoint"]
