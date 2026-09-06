#!/bin/sh
# Obnoví databázi ze zálohy vytvořené backup_db.sh. POZOR: přepíše aktuální
# obsah databáze POSTGRES_DB - appku (web) je potřeba předtím zastavit, jinak
# souběžné zápisy skončí v nekonzistentním stavu.
#
# Použití (z hostitele): docker compose run --rm backup /scripts/restore_db.sh /backups/invoices_20260101_000000.sql.gz
set -eu

FILE="${1:?Použití: restore_db.sh <cesta k .sql.gz záloze>}"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD musí být nastavené}"

echo "Obnovuji $POSTGRES_DB ze zálohy $FILE - přepíše aktuální stav databáze."
gunzip -c "$FILE" | psql -h "${POSTGRES_HOST:-db}" -U "$POSTGRES_USER" -d "$POSTGRES_DB"
echo "Hotovo."
