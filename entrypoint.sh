#!/bin/sh
set -e

# Kontejner startuje jako root výhradně proto, aby šlo opravit vlastnictví
# named volumes (uploads/exports/excel_templates) - Docker je při prvním
# připojení prázdného volume vytvoří jako root, pokud na té cestě v obrazu
# předtím nic nebylo. Idempotentní, bezpečné spouštět při každém startu.
mkdir -p /app/uploads /app/exports /app/excel_templates
chown -R appuser:appuser /app/uploads /app/exports /app/excel_templates

echo "Running Alembic migrations..."
setpriv --reuid=appuser --regid=appuser --init-groups alembic upgrade head

echo "Starting application..."
exec setpriv --reuid=appuser --regid=appuser --init-groups "$@"
