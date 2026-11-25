#!/bin/sh
set -e

echo "==> Aplicando migracoes..."
python manage.py migrate --noinput

echo "==> Preparando a tabela de cache (quando DJANGO_DATABASE_CACHE=True)..."
python manage.py createcachetable

if [ "${SEED_DEMO:-0}" = "1" ]; then
    echo "==> SEED_DEMO=1: carregando dados de demonstracao..."
    python manage.py seed_demo
fi

exec "$@"
