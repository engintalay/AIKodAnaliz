#!/bin/bash

# Backup klasörü
BACKUP_DIR="$HOME/projects/backup"

# Tarih format?
DATE=$(date +"%Y%m%d_%H%M%S")

# Klasör yoksa olu?tur
mkdir -p "$BACKUP_DIR"

# Database backup
tar -czf "$BACKUP_DIR/database_$DATE.tar.gz" database

# Upload backup
tar -czf "$BACKUP_DIR/uploads$DATE.tar.gz" uploads

echo "Backup tamamland?:"
echo "$BACKUP_DIR/database_$DATE.tar.gz"
echo "$BACKUP_DIR/uploads_$DATE.tar.gz"
