#!/bin/bash
# Hindsight Database Restore Script
# Usage: ./restore.sh [backup_file]
# If no file specified, uses the latest backup

set -e

BACKUP_DIR="${HINDSIGHT_BACKUP_DIR:-$HOME/.hindsight/backups}"
CONTAINER_NAME="${HINDSIGHT_DB_CONTAINER:-hindsight-db}"
DB_USER="${POSTGRES_USER:-hindsight}"
DB_NAME="${POSTGRES_DB:-hindsight}"

# Get backup file
if [ -n "$1" ]; then
    BACKUP_FILE="$1"
else
    BACKUP_FILE=$(ls -1t "$BACKUP_DIR"/hindsight_backup_*.sql.gz 2>/dev/null | head -1)
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: No backup file found"
    echo "Usage: $0 [backup_file]"
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/hindsight_backup_*.sql.gz 2>/dev/null || echo "  None"
    exit 1
fi

echo "Restoring from: $BACKUP_FILE"
read -p "This will overwrite all current data. Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 0
fi

echo "Restoring database..."
gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -q

echo "Restore complete!"
