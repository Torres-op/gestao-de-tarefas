#!/bin/sh
set -e

echo "==> Aplicando migracoes..."
python manage.py migrate --noinput

if [ "${SEED_DEMO:-0}" = "1" ]; then
    echo "==> SEED_DEMO=1: carregando dados de demonstracao..."
    python manage.py seed_demo
fi

exec "$@"
