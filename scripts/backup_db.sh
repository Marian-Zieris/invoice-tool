#!/bin/sh
# Jednorázově vytvoří komprimovaný pg_dump a smaže zálohy starší než
# BACKUP_KEEP_DAYS. Volá se ve smyčce ze servisy "backup" v docker-compose.yml
# (viz tam) - mimo Docker jde spustit i ručně/z hostitelského cronu, stačí mít
# nastavené stejné proměnné prostředí jako appka (POSTGRES_USER/_DB/_PASSWORD)
# a dostupný "db" host (např. přes `docker compose exec` nebo tunel).
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD musí být nastavené}"

mkdir -p "$BACKUP_DIR"
timestamp=$(date -u +%Y%m%d_%H%M%S)
target="$BACKUP_DIR/invoices_${timestamp}.sql.gz"
tmp="${target}.tmp"

echo "[backup] $(date -u +%FT%TZ) - zálohuji $POSTGRES_DB -> $target"
pg_dump -h "${POSTGRES_HOST:-db}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$tmp"
mv "$tmp" "$target"
echo "[backup] hotovo, velikost: $(du -h "$target" | cut -f1)"

deleted=$(find "$BACKUP_DIR" -name 'invoices_*.sql.gz' -mtime "+${KEEP_DAYS}" -print -delete | wc -l)
if [ "$deleted" -gt 0 ]; then
  echo "[backup] smazáno $deleted záloh(y) starších než $KEEP_DAYS dní"
fi
