# Deploying to a Hetzner server

One Linux server runs everything with Docker Compose: Caddy (HTTPS), the Next.js frontend, the FastAPI backend, a
scoring/media worker and PostgreSQL. Audio, recordings and imports live in S3-compatible object storage (AWS S3 or
Hetzner Object Storage).

```
Internet ─▶ Caddy :443 ─┬─ /api/* ─▶ backend (FastAPI, 2 workers) ─┬─ PostgreSQL (volume)
                        └─ /*     ─▶ frontend (Next.js)            └─ S3 / Hetzner Object Storage
                                     worker (scoring, media ingest) ─┘
```

## 1. Server

- A Hetzner Cloud server with Ubuntu 24.04. Start with 4 vCPU / 8 GB RAM (ffmpeg packaging and scoring run on it);
  resize later if the worker queue backs up.
- Add your SSH key when creating it. Enable Hetzner's automatic snapshots/backups as an extra safety net.
- Firewall (Hetzner Cloud Firewall or ufw): allow inbound 22 (SSH, ideally restricted to your IPs), 80 and 443
  (TCP), 443 (UDP, HTTP/3). Nothing else; Postgres is not exposed.

```bash
ssh root@SERVER_IP
adduser --disabled-password deploy && usermod -aG sudo deploy
apt update && apt -y upgrade && apt -y install ca-certificates curl git ufw
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443 && ufw --force enable
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
```

## 2. DNS

Point the domain at the server before the first start (Caddy requests the certificate on first boot):

| Record | Name | Value |
|---|---|---|
| A | `ccl.example.com` | server IPv4 |
| AAAA | `ccl.example.com` | server IPv6 |
| CNAME | `www.ccl.example.com` | `ccl.example.com` (optional; redirected) |

## 3. Object storage

Create a private bucket (no public access; the app serves audio only through signed, session-bound URLs):

- **Hetzner Object Storage**: create a bucket and S3 credentials in the Hetzner console. Set
  `S3_ENDPOINT_URL=https://<location>.your-objectstorage.com` (e.g. `fsn1`), `S3_REGION=<location>`.
- **AWS S3**: leave `S3_ENDPOINT_URL` empty, set `S3_REGION` (e.g. `ap-southeast-2`) and an IAM user limited to
  that bucket (`s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket`).

## 4. Configure

```bash
su - deploy
sudo mkdir -p /opt/ccl && sudo chown deploy /opt/ccl
git clone <repository-url> /opt/ccl && cd /opt/ccl
cp .env.example .env && chmod 600 .env
nano .env
```

Production values in `.env` (everything else in `.env.example` has a sensible default):

| Variable | Value |
|---|---|
| `DOMAIN`, `ACME_EMAIL` | your domain; an email for certificate notices |
| `POSTGRES_PASSWORD` | long random string (`openssl rand -hex 24`) |
| `SECRET_KEY` | long random string (`openssl rand -hex 32`). Changing it signs everyone out |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | the first admin account (kept in sync by the seed on each start) |
| `S3_*` | from step 3 |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | speech-to-text and AI evaluation. Without them scoring runs in a labelled mock mode |
| `STRIPE_SECRET_KEY`, `STRIPE_PRICE_SELF_STUDY` (+ `STRIPE_PRICE_COACHING`) | live keys and price IDs |
| `STRIPE_WEBHOOK_SECRET` | from step 6 |
| `EMAIL_PROVIDER=smtp` or `resend`, `EMAIL_FROM`, SMTP/Resend settings | transactional email |

`APP_URL`, `DATABASE_URL`, `COOKIE_SECURE=true` and `ENVIRONMENT=production` are set by `docker-compose.prod.yml`.

## 5. Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps          # all services "healthy"
docker compose -f docker-compose.prod.yml logs -f backend worker
```

The backend runs `alembic upgrade head` and the idempotent seed (languages, EN<->FIL pair, topics, Filipino scoring
config, plans, admin) on every start. Visit `https://DOMAIN`, sign in as the admin, then:

1. **CSV import** (`/admin/imports`): import dialogues (audio is downloaded, encrypted and packaged by the worker;
   follow progress on the import page) and courses.
2. **Dialogues**: check each dialogue, publish it; mark the intro dialogue as Free.
3. **Mock tests**: create mock tests (two published dialogues each) and publish them.
4. **Courses**: publish the courses; mark free lessons.
5. Public copy, FAQ, reviews, Terms and Privacy come from `backend/content/site_content.json`, overridable per key
   with a `site_content` row. Replace the draft legal pages before launch.

## 6. Stripe

In the Stripe dashboard (live mode): Developers → Webhooks → Add endpoint

- URL: `https://DOMAIN/api/stripe/webhook`
- Events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
  `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`,
  `invoice.paid`, `invoice.payment_failed`
- Copy the signing secret into `STRIPE_WEBHOOK_SECRET`, then `docker compose -f docker-compose.prod.yml up -d backend`.

Also enable the **Customer portal** (Settings → Billing → Customer portal) so students can manage or cancel.
Events are stored once by id, so Stripe's retries are safe.

Testing first in Stripe test mode: use `sk_test_` keys and run `stripe listen --forward-to https://DOMAIN/api/stripe/webhook`
or a test-mode endpoint; pay with card `4242 4242 4242 4242`.

## 7. Backups

```bash
chmod +x deploy/backup.sh
crontab -e
# 15 3 * * * cd /opt/ccl && BACKUP_S3_URI=s3://ccl-backups/db ./deploy/backup.sh >> backups/backup.log 2>&1
```

`deploy/backup.sh` writes a compressed `pg_dump` to `/opt/ccl/backups` (kept 14 days) and copies it off-server when
`BACKUP_S3_URI` is set (install and configure the `aws` CLI; for Hetzner set `AWS_ENDPOINT_URL`). Object storage
holds the audio and recordings; enable versioning or replication on the bucket if you need point-in-time recovery.

Restore:

```bash
docker compose -f docker-compose.prod.yml stop backend worker
gunzip -c backups/ccl-YYYYMMDDTHHMMSSZ.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres psql -U ccl -d ccl
docker compose -f docker-compose.prod.yml start backend worker
```

Test a restore on a spare server at least once before launch.

## 8. Updates

```bash
cd /opt/ccl && git pull
docker compose -f docker-compose.prod.yml up -d --build
docker image prune -f
```

Migrations run automatically on backend start. The worker finishes its current job before stopping (2 minute grace).

## 9. Operations

- Logs: `docker compose -f docker-compose.prod.yml logs --since 1h backend worker caddy` (rotated, 5 x 10 MB each).
- Scoring problems: Admin → Review queue lists failed and flagged segments; each attempt shows every AI run
  (request, raw response, parsed result). Failed jobs are retried automatically (4 tries with backoff).
- Emails that failed to send are counted on the admin overview; details in the `email_logs` table.
- Scale scoring: run more workers with `docker compose -f docker-compose.prod.yml up -d --scale worker=3`
  (jobs are claimed with `SKIP LOCKED`, so workers never double-process).
- Content protection events (denied media requests, rate limits) are in the `security_events` table.
