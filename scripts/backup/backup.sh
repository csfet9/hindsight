#!/bin/bash
# Hindsight Database Backup Script
# Backs up the PostgreSQL database to ~/.hindsight/backups/
# Keeps last 30 backups by default

set -e

BACKUP_DIR="${HINDSIGHT_BACKUP_DIR:-$HOME/.hindsight/backups}"
CONTAINER_NAME="${HINDSIGHT_DB_CONTAINER:-hindsight-db}"
DB_USER="${POSTGRES_USER:-hindsight}"
DB_NAME="${POSTGRES_DB:-hindsight}"
KEEP_BACKUPS="${HINDSIGHT_KEEP_BACKUPS:-30}"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate timestamp for backup filename
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/hindsight_backup_${TIMESTAMP}.sql.gz"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting backup..."

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Error: Container '$CONTAINER_NAME' is not running"
    exit 1
fi

# Create backup using pg_dump
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists | gzip > "$BACKUP_FILE"

# Verify backup was created
if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
    SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Backup created: $BACKUP_FILE ($SIZE)"
else
    echo "Error: Backup file was not created or is empty"
    exit 1
fi

# Rotate old backups - keep only the last N backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/hindsight_backup_*.sql.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$KEEP_BACKUPS" ]; then
    TO_DELETE=$((BACKUP_COUNT - KEEP_BACKUPS))
    echo "Rotating backups: removing $TO_DELETE old backup(s)..."
    ls -1t "$BACKUP_DIR"/hindsight_backup_*.sql.gz | tail -n "$TO_DELETE" | xargs rm -f
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Backup complete. Total backups: $(ls -1 "$BACKUP_DIR"/hindsight_backup_*.sql.gz 2>/dev/null | wc -l)"
