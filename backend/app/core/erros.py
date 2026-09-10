"""Tratamento de erro uniforme.

Duas garantias:

1. NENHUM 500 vaza detalhe interno para a tela. Traceback e mensagem do
   Postgres viram uma resposta genérica com um id de correlação; o detalhe
   fica no log do servidor.

2. Toda falha previsível diz O QUE FAZER, e não só o que aconteceu. É o
   espírito da correção de "Esta falta já foi reposta": mensagem errada manda
   a pessoa resolver o problema errado.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.logs import logger


def _resposta(codigo: int, detalhe: str, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=codigo,
        content={"detail": detalhe},
        headers={"X-Request-Id": request.headers.get("X-Request-Id", "")},
    )


def registrar(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
        """422 com o campo e o motivo, em vez do despejo do Pydantic.

        A tela mostra `detail` direto para o usuário; o formato padrão do
        FastAPI é uma lista aninhada que não se lê.
        """
        problemas = []
        campos = []
        for erro in exc.errors():
            campo = ".".join(str(p) for p in erro["loc"] if p != "body")
            mensagem = str(erro["msg"]).removeprefix("Value error, ")
            problemas.append(f"{campo}: {mensagem}" if campo else mensagem)
            # Só campo e mensagem. O `ctx` do Pydantic carrega a exceção
            # original, que não é serializável em JSON — incluí-la fazia o
            # próprio handler de erro estourar.
            campos.append({"campo": campo, "mensagem": mensagem})

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Confira os campos: " + "; ".join(problemas),
                "campos": campos,
            },
        )

    @app.exception_handler(IntegrityError)
    async def integridade(request: Request, exc: IntegrityError) -> JSONResponse:
        """Constraint violada que escapou da checagem do serviço.

        Vira 409 — é conflito de dado, não erro do servidor. O detalhe do
        Postgres fica no log, nunca na tela.
        """
        logger.warning(
            "violacao de integridade",
            extra={"contexto": {"rota": request.url.path, "erro": str(exc.orig)}},
        )
        return _resposta(
            status.HTTP_409_CONFLICT,
            "Esta operação conflita com um registro existente. "
            "Recarregue a tela e tente de novo — outra pessoa pode ter alterado "
            "este dado ao mesmo tempo.",
            request,
        )

    @app.exception_handler(SQLAlchemyError)
    async def banco(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("erro de banco", extra={"contexto": {"rota": request.url.path}})
        return _resposta(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "O sistema não conseguiu falar com o banco de dados. "
            "Tente de novo em alguns instantes; se persistir, avise o suporte.",
            request,
        )

    @app.exception_handler(Exception)
    async def inesperado(request: Request, exc: Exception) -> JSONResponse:
        """Rede de segurança. Nada de traceback na resposta."""
        logger.exception("erro nao tratado", extra={"contexto": {"rota": request.url.path}})
        return _resposta(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Ocorreu um erro inesperado. A equipe foi notificada pelo log. "
            "Se puder, informe o que estava fazendo quando aconteceu.",
            request,
        )
