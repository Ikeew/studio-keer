from fastapi import APIRouter

from app.api.v1 import (
    agenda,
    auth,
    dashboard,
    financeiro,
    health,
    matriculas,
    patients,
    services,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(patients.router)
api_router.include_router(services.router)
api_router.include_router(agenda.router)
api_router.include_router(matriculas.router)
api_router.include_router(financeiro.router)
api_router.include_router(dashboard.router)

# Fases seguintes registram seus routers aqui:
