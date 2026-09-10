#!/bin/sh
# Boot de produção.
#
# `set -e` é essencial: sem ele, uma migration que falha seria ignorada e a
# API subiria contra um banco em schema errado — pior que não subir.
set -e

echo "Aplicando migrations..."
alembic upgrade head

# Render e Railway injetam a porta em $PORT e mudam o valor entre deploys.
# Fixar 8000 faz o health check do provedor falhar e o serviço nunca ficar
# pronto, sem erro visível no log da aplicação.
PORTA="${PORT:-8000}"
echo "Subindo a API na porta $PORTA..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORTA"
