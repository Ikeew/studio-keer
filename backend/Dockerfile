FROM python:3.12-slim

# uv vem da imagem oficial: mais rápido e reproduzível que baixar por script.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# O venv fica FORA de /app de propósito. O docker-compose monta ./backend em
# /app para dar hot reload, e um venv em /app/.venv seria escondido por esse
# bind mount — o container perderia uvicorn e alembic ao subir.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Instala dependências antes de copiar o código: enquanto o pyproject não
# mudar, esta camada vem do cache mesmo a cada alteração na aplicação.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

# start.sh aplica as migrations antes de subir e respeita a $PORT que o
# provedor injeta. Em desenvolvimento o docker-compose sobrescreve o comando
# para ganhar hot reload.
CMD ["./start.sh"]
