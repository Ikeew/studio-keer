from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.erros import registrar as registrar_erros
from app.core.logs import LogDeRequisicoes
from app.core.logs import configurar as configurar_logs

settings = get_settings()

# Log estruturado, sem dado pessoal — ver app/core/logs.py.
configurar_logs("INFO")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
)

app.add_middleware(LogDeRequisicoes)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nenhum 500 vaza detalhe interno para a tela.
registrar_erros(app)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
