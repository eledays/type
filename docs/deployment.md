# Production deployment

The supported production topology uses two machines:

```text
Internet -> Apache (TLS) -> private/VPN HTTP -> Type application server
```

Apache owns the public domain, ports 80/443, Let's Encrypt certificate, and
proxy configuration. The application server publishes Gunicorn only on an
explicit private address. PostgreSQL and Redis remain inside Docker networks.

For an executable Russian step-by-step guide, including Apache templates and
certificate setup, see [`production-runbook.md`](production-runbook.md).

The regular `docker compose up --build --detach` development stack still works
without any reverse proxy at `http://localhost:8000`. The production stack is
different: secure cookies, HSTS, OAuth callbacks, and trusted forwarding
headers require a trusted HTTPS reverse proxy or load balancer. Do not expose
the production origin directly to the public internet.

## Application server

Create the environment file:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -hex 32
openssl rand -hex 32
```

Set `DOMAIN` to the public hostname and `APP_BIND_IP` to the private/VPN
address of the application server. Use different generated values for
`SECRET_KEY` and `POSTGRES_PASSWORD`. Register this exact Yandex OAuth callback:

```text
https://<DOMAIN>/auth/yandex/callback
```

Validate and start the origin:

```bash
scripts/compose_production.sh config --quiet
scripts/compose_production.sh up --build --detach
scripts/compose_production.sh ps
```

Allow `${APP_PORT}` through the application-server firewall only from the
Apache server. The connection must use a trusted private network or VPN; do not
send authenticated origin traffic as plain HTTP over the public internet.

Test from the Apache server while preserving the public host:

```bash
curl --fail --header 'Host: <DOMAIN>' \
  http://<APP_BIND_IP>:<APP_PORT>/health/ready
```

Apache must preserve `Host`, append the client address to `X-Forwarded-For`,
and set `X-Forwarded-Proto: https`. The application trusts exactly one proxy
hop. Do not make the origin port publicly reachable, because direct clients
could otherwise forge trusted forwarding headers.

Example Apache configurations are stored in:

- [`type-http.conf.example`](../deploy/apache/type-http.conf.example) for the
  first ACME webroot challenge;
- [`type.conf.example`](../deploy/apache/type.conf.example) for HTTPS and
  reverse proxying.

## Moving existing PostgreSQL data

Docker volumes do not travel with Git. Create a custom-format dump on the old
machine:

```bash
docker compose exec -T postgres \
  pg_dump -U type -d type --format=custom > type.dump
```

Treat the dump as sensitive user data and transfer it over SSH. Before the
site receives traffic, recreate the empty target database. Substitute names if
they differ in `.env.production`:

```bash
scripts/compose_production.sh stop app
scripts/compose_production.sh exec -T postgres dropdb -U type --force type
scripts/compose_production.sh exec -T postgres createdb -U type type
scripts/compose_production.sh exec -T postgres pg_restore \
  -U type -d type --no-owner --no-privileges < type.dump
scripts/compose_production.sh up --detach app
```

Delete or securely archive the transferred dump after verification.

## Backups and restore tests

Create a permission-restricted custom-format dump:

```bash
scripts/backup_postgres.sh
```

Copy backups outside the application server. Periodically test restoration in
a dedicated database:

```bash
scripts/compose_production.sh exec -T postgres \
  createdb -U type type_restore_test

scripts/compose_production.sh exec -T postgres pg_restore \
  -U type -d type_restore_test --no-owner --no-privileges \
  < backups/<backup-file>.dump
```

Drop only the dedicated restore-test database after checking it.

## Deploying updates

Apache is independent of ordinary application deployments:

```bash
cd /opt/type
scripts/backup_postgres.sh
git pull --ff-only
scripts/compose_production.sh build app
scripts/compose_production.sh up --detach
scripts/compose_production.sh ps
```

The application entrypoint applies Alembic migrations before Gunicorn starts.
Check container logs, the origin readiness endpoint, and the external HTTPS
endpoint after every deployment.

Never run `docker compose down --volumes` in production. It removes PostgreSQL
and Redis data volumes.
