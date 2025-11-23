#!/usr/bin/env bash
# Database backup script for IsTheTubeRunning
# Creates compressed PostgreSQL backup and uploads to Azure Blob Storage
#
# Prerequisites:
#   - DOTENV_KEY environment variable set (for decrypting .env.vault)
#   - Azure CLI installed (az command)
#   - VM managed identity with Storage Blob Data Contributor role
#   - uv installed (for running Python scripts)
#
# Usage:
#   ./backup-db.sh [--local-only]
#
# Options:
#   --local-only    Create backup but don't upload to Azure (for testing)

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="/tmp/isthetube-backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="isthetube-${TIMESTAMP}.sql.gz"
LOCAL_ONLY=false

# Parse arguments
if [[ "${1:-}" == "--local-only" ]]; then
    LOCAL_ONLY=true
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "=== IsTheTubeRunning Database Backup ==="
echo "Timestamp: $TIMESTAMP"
echo "Local only: $LOCAL_ONLY"
echo ""

# Extract database credentials from .env.vault using dotenv-vault
echo "Extracting database credentials from .env.vault..."
if [[ -z "${DOTENV_KEY:-}" ]]; then
    echo "ERROR: DOTENV_KEY environment variable not set"
    echo "Cannot decrypt .env.vault without DOTENV_KEY"
    exit 1
fi

# Navigate to backend directory to access Python utility
cd "$SCRIPT_DIR/../../backend" || exit 1

# Extract credentials using Python utility
source <(uv run python -m app.utils.extract_db_credentials export)

# Validate credentials were extracted
if [[ -z "$PGPASSWORD" ]] || [[ -z "$PGHOST" ]] || [[ -z "$PGDATABASE" ]]; then
    echo "ERROR: Failed to extract database credentials"
    echo "PGHOST=$PGHOST PGUSER=$PGUSER PGDATABASE=$PGDATABASE"
    exit 1
fi

echo "Database: $PGUSER@$PGHOST/$PGDATABASE"
echo ""

# Create backup
echo "Creating database backup..."
pg_dump -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" | gzip > "$BACKUP_DIR/$BACKUP_FILE"

# Check backup was created
if [[ ! -f "$BACKUP_DIR/$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file was not created"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
echo "✓ Backup created: $BACKUP_FILE (${BACKUP_SIZE})"
echo ""

# Upload to Azure Blob Storage (unless --local-only)
if [[ "$LOCAL_ONLY" == false ]]; then
    echo "Uploading to Azure Blob Storage..."

    # Get storage account from environment or use default
    STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-isthetubestorage}"
    STORAGE_CONTAINER="${AZURE_STORAGE_CONTAINER:-backups}"

    # Upload using managed identity authentication
    if az storage blob upload \
        --account-name "$STORAGE_ACCOUNT" \
        --container-name "$STORAGE_CONTAINER" \
        --name "$BACKUP_FILE" \
        --file "$BACKUP_DIR/$BACKUP_FILE" \
        --auth-mode login \
        --overwrite; then
        echo "✓ Uploaded to Azure: $STORAGE_ACCOUNT/$STORAGE_CONTAINER/$BACKUP_FILE"
    else
        echo "ERROR: Failed to upload to Azure Blob Storage"
        echo "Backup remains at: $BACKUP_DIR/$BACKUP_FILE"
        exit 1
    fi

    # Implement backup rotation (7 daily, 4 weekly)
    echo ""
    echo "Implementing backup rotation..."

    # Get list of all backups
    BACKUP_LIST=$(az storage blob list \
        --account-name "$STORAGE_ACCOUNT" \
        --container-name "$STORAGE_CONTAINER" \
        --prefix "isthetube-" \
        --query "[].name" \
        --output tsv \
        --auth-mode login)

    # Count backups
    BACKUP_COUNT=$(echo "$BACKUP_LIST" | wc -l)
    echo "Total backups: $BACKUP_COUNT"

    # TODO: Implement sophisticated rotation (Issue #241)
    # - Keep last 7 daily backups
    # - Keep 4 weekly backups (one per week)
    # - Delete older backups
    echo "NOTE: Sophisticated backup rotation will be implemented in Issue #241"

    # Cleanup local backup file
    rm "$BACKUP_DIR/$BACKUP_FILE"
    echo "✓ Cleaned up local backup file"
else
    echo "Skipping Azure upload (--local-only mode)"
    echo "Backup saved locally: $BACKUP_DIR/$BACKUP_FILE"
fi

echo ""
echo "=== Backup Complete ==="
