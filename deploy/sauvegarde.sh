#!/usr/bin/env bash
# Sauvegarde quotidienne : base SQLite (copie cohérente) + documents générés.
# Conservation 30 jours dans /var/backups/gb-etats (pensez à une copie HORS serveur :
# la sauvegarde automatique OVH ou un rsync vers le bureau — voir le guide).
set -euo pipefail

APP=/opt/gb-etats
DEST=/var/backups/gb-etats
JOUR=$(date +%F)

mkdir -p "$DEST"
if [ -f "$APP/runtime/gb.db" ]; then
  sqlite3 "$APP/runtime/gb.db" ".backup '$DEST/gb-$JOUR.db'"
fi
tar -czf "$DEST/sorties-$JOUR.tar.gz" -C "$APP/runtime" sorties 2>/dev/null || true

# Rotation : 30 jours
find "$DEST" -type f -mtime +30 -delete
echo "$(date -Is) sauvegarde OK -> $DEST (gb-$JOUR.db)"
