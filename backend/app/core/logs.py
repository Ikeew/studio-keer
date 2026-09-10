"""Log estruturado, sem dado pessoal.

REGRA: nada que identifique um paciente entra no log. Nome, CPF, telefone e
e-mail ficam de fora — o log costuma ir para serviço de terceiro e sobrevive
por meses, o que o torna um vazamento de LGPD esperando acontecer.

Identificamos por ID. Quem tem acesso ao banco resolve o ID; quem só tem o
log, não.
"""

import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

#: Campos que NUNCA podem aparecer num log.
CAMPOS_PESSOAIS = frozenset(
    {
        "nome",
        "nome_completo",
        "paciente_nome",
        "cpf",
        "cpf_formatado",
        "telefone",
        "emergencia_nome",
        "emergencia_telefone",
        "email",
        "senha",
        "password",
        "access_token",
        "authorization",
        "motivo_justificativa",
        "observacoes",
    }
)


class FormatadorJson(logging.Formatter):
    """Uma linha JSON por evento — legível por máquina, sem ficar ilegível."""

    def format(self, record: logging.LogRecord) -> str:
        evento: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "nivel": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "contexto", None)
        if isinstance(extra, dict):
            evento.update(sanitizar(extra))
        if record.exc_info:
            evento["excecao"] = self.formatException(record.exc_info)
        return json.dumps(evento, ensure_ascii=False, default=str)


def sanitizar(dados: dict[str, object]) -> dict[str, object]:
    """Remove campos pessoais antes de qualquer coisa ir para o log."""
    return {
        chave: ("[removido]" if chave.lower() in CAMPOS_PESSOAIS else valor)
        for chave, valor in dados.items()
    }


def configurar(nivel: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatadorJson())
    raiz = logging.getLogger()
    raiz.handlers = [handler]
    raiz.setLevel(nivel)
    # O access log do uvicorn repetiria cada requisição em texto puro, sem
    # passar por este formatador nem pela sanitização.
    logging.getLogger("uvicorn.access").disabled = True


logger = logging.getLogger("studio_keer")


class LogDeRequisicoes(BaseHTTPMiddleware):
    """Uma linha por requisição, com um id para correlacionar erro e chamada.

    Registra método, rota, status e duração. NÃO registra corpo nem query
    string — os dois carregam nome e telefone nas buscas.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid.uuid4().hex[:12]
        inicio = time.perf_counter()

        try:
            resposta = await call_next(request)
        except Exception:
            logger.exception(
                "erro nao tratado",
                extra={
                    "contexto": {
                        "request_id": request_id,
                        "metodo": request.method,
                        "rota": request.url.path,
                        "duracao_ms": round((time.perf_counter() - inicio) * 1000),
                    }
                },
            )
            raise

        duracao = round((time.perf_counter() - inicio) * 1000)
        logger.info(
            "requisicao",
            extra={
                "contexto": {
                    "request_id": request_id,
                    "metodo": request.method,
                    # Só o caminho: a query string carrega busca por nome.
                    "rota": request.url.path,
                    "status": resposta.status_code,
                    "duracao_ms": duracao,
                }
            },
        )
        resposta.headers["X-Request-Id"] = request_id
        return resposta
