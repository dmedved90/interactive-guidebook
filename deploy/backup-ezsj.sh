#!/usr/bin/env bash
# Nightly backup of the EZSJ instance (Predator): consistent SQLite copy (sqlite3 backup API,
# safe while the app writes) and the .env, into ~/backups/guidebook. Keeps the newest $KEEP of each.
# ~/backups on Predator is pulled to the appserver and Synology every night.
#
#   cron: 40 2 * * * $HOME/interactive-guidebook/deploy/backup-ezsj.sh >> $HOME/backups/guidebook/backup.log 2>&1
#
# Restore: docker compose -f compose.ezsj.yaml stop web
#          docker cp sqlite-<stamp>.db guidebook-ezsj:/data/db.sqlite3   (then start web)
set -euo pipefail

CONTAINER=guidebook-ezsj
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIR="${BACKUP_DIR:-$HOME/backups/guidebook}"
KEEP="${KEEP:-30}"
STAMP="$(date +%Y-%m-%d_%H%M)"

umask 077
mkdir -p "$DIR"
dest="$DIR/sqlite-$STAMP.db"

docker exec "$CONTAINER" python -c '
import os, sqlite3, sys
t = "/tmp/backup.db"
d = sqlite3.connect(t)
sqlite3.connect("/data/db.sqlite3").backup(d)
d.close()
sys.stdout.buffer.write(open(t, "rb").read())
os.remove(t)
' > "$dest.part"

if [ "$(head -c 15 "$dest.part")" != "SQLite format 3" ]; then
    rm -f "$dest.part"
    echo "$(date '+%F %T') ERROR: copy has no SQLite header" >&2
    exit 1
fi
mv "$dest.part" "$dest"
cp "$APP_DIR/.env" "$DIR/env-$STAMP"

for pattern in 'sqlite-*.db' 'env-*'; do
    ls -1t "$DIR"/$pattern 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f
done

echo "$(date '+%F %T') OK $(basename "$dest") ($(du -h "$dest" | cut -f1))"
