#!/usr/bin/env bash
# Nightly Postgres backup: compressed pg_dump into ./backups, keep 14 days, optionally copy off-server.
#   crontab -e  ->  15 3 * * * cd /opt/ccl && ./deploy/backup.sh >> backups/backup.log 2>&1
# Off-server copy (recommended): set BACKUP_S3_URI (e.g. s3://ccl-backups/db) and configure the aws CLI
# (works with Hetzner Object Storage via AWS_ENDPOINT_URL).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
file="backups/ccl-$stamp.sql.gz"
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U ccl -d ccl --no-owner | gzip -9 > "$file"
echo "$(date -u) wrote $file ($(du -h "$file" | cut -f1))"
find backups -name 'ccl-*.sql.gz' -mtime +14 -delete
if [ -n "${BACKUP_S3_URI:-}" ]; then
  aws s3 cp "$file" "$BACKUP_S3_URI/$(basename "$file")" --only-show-errors
  echo "copied to $BACKUP_S3_URI"
fi
