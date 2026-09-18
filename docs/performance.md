# Production performance

The application emits immutable, versioned URLs and `Cache-Control` headers
for static assets. The default Apache topology proxies them through Gunicorn.
For higher traffic, synchronize `/app/static/` to Apache or a CDN and serve
`/static/` there without removing the application's cache headers.

Enable Brotli or gzip for text responses at the reverse proxy. Compress HTML,
JSON, CSS, JavaScript, and SVG; do not recompress WebP, PNG, JPEG, or ICO files.
Add `Vary: Accept-Encoding` and keep the application's existing
`Cache-Control` headers. A typical Apache VirtualHost configuration includes:

```apache
AddOutputFilterByType DEFLATE \
    text/html text/plain text/css \
    application/json application/javascript image/svg+xml
```

Use multiple Gunicorn workers for concurrent requests and a shared Redis
backend for rate limits. SQLite is suitable for development and light traffic;
use PostgreSQL when concurrent writes become regular. Track route p50/p95
latency and database query duration before changing worker counts.

The production analytics dashboard caches complete filtered responses in
Redis for `ANALYTICS_CACHE_SECONDS` (60 seconds by default). Set the value to
`0` while diagnosing live queries. Exercise search uses the PostgreSQL
`pg_trgm` extension and `ix_practice_item_search_trgm`; CSV export streams one
server-side result and does not use offset pagination.
