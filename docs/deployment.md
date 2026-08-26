# Production deployment

This deployment targets one Linux server with Docker Engine and the Docker
Compose plugin. Caddy is the only public container; it obtains and renews TLS
certificates and proxies requests to Gunicorn over the private frontend
network. PostgreSQL and Redis are attached only to the internal backend
network and publish no host ports.

## 1. Server and DNS

Use a supported 64-bit Linux distribution with at least 2 GB RAM and enough
disk space for Docker images, PostgreSQL data, and backups. Install Docker
Engine and the Compose plugin from Docker's official repository.

Create an `A` record for the production domain pointing to the server. Add an
`AAAA` record only if IPv6 routing and firewall rules are configured. Allow
incoming TCP traffic on ports 22, 80, and 443.

Do not publish ports 8000, 5432, or 6379. Docker-published ports may bypass
host-level UFW rules, so the production Compose configuration exposes only
Caddy on 80/443.

## 2. Application files and secrets

Clone the repository into a stable path such as `/opt/type`:

```bash
sudo mkdir -p /opt/type
sudo chown "$USER":"$USER" /opt/type
git clone <repository-url> /opt/type
cd /opt/type
```

Create the environment file and restrict its permissions:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -hex 32
openssl rand -hex 32
```

Put the generated values into `SECRET_KEY` and `POSTGRES_PASSWORD`. Replace
all remaining placeholders. `DOMAIN` must contain a host name without a scheme
or path. Register this exact callback URL in the Yandex OAuth application:

```text
https://<DOMAIN>/auth/yandex/callback
```

Never commit `.env.production`. The file is ignored by Git.

## 3. First start

Use the production wrapper on the server. It always passes both explicit
Compose files and therefore prevents the local `compose.override.yaml` from
publishing Gunicorn on port 8000:

```bash
scripts/compose_production.sh config --quiet
scripts/compose_production.sh up --build --detach
```

Caddy can obtain a public certificate only after the domain resolves to this
server and ports 80/443 are reachable. Inspect startup and certificate logs:

```bash
scripts/compose_production.sh ps
scripts/compose_production.sh logs --tail=200 app caddy
```

Verify the deployment:

```bash
curl --fail https://<DOMAIN>/health/live
curl --fail https://<DOMAIN>/health/ready
```

`/health/live` checks the HTTP process. `/health/ready` additionally checks
PostgreSQL and Redis. Neither endpoint creates an anonymous user.

## 4. Moving the existing data

Docker volumes do not travel with Git. Create a custom-format dump on the old
machine:

```bash
docker compose exec -T postgres \
  pg_dump -U type -d type --format=custom > type.dump
```

Treat the dump as sensitive user data and transfer it to the server over SSH.
Before the site receives traffic, stop the app and recreate the empty target
database. Substitute database/user names if they differ in `.env.production`:

```bash
scripts/compose_production.sh stop app caddy
scripts/compose_production.sh exec -T postgres dropdb -U type --force type
scripts/compose_production.sh exec -T postgres createdb -U type type
scripts/compose_production.sh exec -T postgres pg_restore \
  -U type -d type --no-owner --no-privileges < type.dump
scripts/compose_production.sh up --detach app caddy
```

Delete or securely archive the transferred dump after verification.

## 5. Backups and restore

Create a backup with the repository script:

```bash
scripts/backup_postgres.sh
```

The script writes a permission-restricted custom-format dump to `backups/`.
Copy backups to storage outside the server and define retention there. A backup
that exists only on the application server does not protect against disk or
server loss.

Test restoration periodically using a separate database:

```bash
scripts/compose_production.sh exec -T postgres \
  createdb -U type type_restore_test

scripts/compose_production.sh exec -T postgres pg_restore \
  -U type -d type_restore_test --no-owner --no-privileges \
  < backups/<backup-file>.dump
```

Drop only the dedicated restore-test database after checking it.

## 6. Deploying updates

Create a backup first, then update and rebuild:

```bash
cd /opt/type
scripts/backup_postgres.sh
git pull --ff-only

scripts/compose_production.sh build app caddy
scripts/compose_production.sh up --detach
```

The app entrypoint applies Alembic migrations before Gunicorn starts. Check
container health, logs, and the external readiness endpoint after every
deployment. Do not run `docker compose down --volumes` on the server: it
removes the PostgreSQL, Redis, and Caddy volumes.

## 7. Operations checklist

- Monitor HTTPS availability and `/health/ready` from another machine.
- Alert on disk usage, memory pressure, container restarts, and failed backups.
- Keep Ubuntu and Docker security updates current.
- Keep at least one recent database backup outside the VPS.
- Test restoration before relying on the backup process.
- Review `docker compose logs` after deployments and OAuth configuration
  changes.
