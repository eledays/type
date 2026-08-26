# Production performance

The application emits immutable, versioned URLs for static assets. Serve
`/static/` directly from the reverse proxy or a CDN instead of routing those
requests through Gunicorn.

Enable Brotli or gzip for text responses at the reverse proxy. Compress HTML,
JSON, CSS, JavaScript, and SVG; do not recompress WebP, PNG, JPEG, or ICO files.
Add `Vary: Accept-Encoding` and keep the application's existing
`Cache-Control` headers. A typical nginx configuration includes:

```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types application/json application/javascript image/svg+xml text/css;

location /static/ {
    alias /path/to/type/app/static/;
    try_files $uri =404;
}
```

Use multiple Gunicorn workers for concurrent requests and a shared Redis
backend for rate limits. SQLite is suitable for development and light traffic;
use PostgreSQL when concurrent writes become regular. Track route p50/p95
latency and database query duration before changing worker counts.
