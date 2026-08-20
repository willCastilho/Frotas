#!/usr/bin/env bash
# Backup do banco MySQL do Gestao de Frotas.
# Le as credenciais do .env (ou do ambiente) e gera um dump com data no nome.
#
# Uso:
#   ./scripts/backup.sh [diretorio_destino]
#
# Exemplo de agendamento (cron diario as 2h):
#   0 2 * * * /caminho/gestao-frotas/scripts/backup.sh /var/backups/frotas

set -euo pipefail

# Carrega variaveis do .env se existir
if [ -f "$(dirname "$0")/../.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$(dirname "$0")/../.env"
    set +a
fi

DB_NAME="${DB_NAME:-gestao_frotas}"
DB_USER="${DB_USER:-root}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DESTINO="${1:-./backups}"

mkdir -p "$DESTINO"
ARQUIVO="$DESTINO/${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql.gz"

echo "Gerando backup em $ARQUIVO ..."
mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" ${DB_PASSWORD:+-p"$DB_PASSWORD"} \
    --single-transaction --routines --triggers "$DB_NAME" | gzip > "$ARQUIVO"

echo "Backup concluido: $ARQUIVO"
