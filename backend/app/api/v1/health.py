from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok", "unreachable"]


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    """Liveness + checagem de banco.

    Responde 200 mesmo com o banco fora: o campo `database` diz o que está
    quebrado. Um healthcheck que retorna 503 por causa do banco faz o
    orquestrador reiniciar a API em loop durante uma queda do Postgres,
    o que não conserta nada.
    """
    try:
        db.execute(text("SELECT 1"))
        database: Literal["ok", "unreachable"] = "ok"
    except Exception:
        database = "unreachable"

    return HealthResponse(status="ok", database=database)
