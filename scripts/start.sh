#!/usr/bin/env sh
# Script de inicializacao em producao (Railway/Docker).
# Roda migracoes, garante grupos/admin (sem bloquear o servidor) e sobe o gunicorn.

echo "==> [1/4] Rodando migracoes..."
python manage.py migrate --noinput || echo "!! migrate falhou (seguindo para subir o servidor mesmo assim)"

echo "==> [2/4] Garantindo grupos de acesso..."
python manage.py criar_grupos || echo "!! criar_grupos falhou (ignorado)"

echo "==> [3/4] Garantindo superusuario..."
python manage.py criar_admin || echo "!! criar_admin falhou (ignorado)"

echo "==> [4/4] Iniciando gunicorn na porta ${PORT:-8000}..."
exec gunicorn project.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --log-level info
