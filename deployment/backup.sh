#!/usr/bin/env bash
# Nightly + pre/post-exam PostgreSQL backup. A backup is not proven until restored.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/viva}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

docker compose exec -T db pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
  | gzip > "$BACKUP_DIR/viva-$STAMP.sql.gz"

# Keep 14 days
find "$BACKUP_DIR" -name 'viva-*.sql.gz' -mtime +14 -delete

echo "Backup written: $BACKUP_DIR/viva-$STAMP.sql.gz"
echo "Restore with: gunzip -c FILE | docker compose exec -T db psql -U \$POSTGRES_USER \$POSTGRES_DB"
