from fastapi import APIRouter

from app.api.v1 import agenda, auth, health, patients, services, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(patients.router)
api_router.include_router(services.router)
api_router.include_router(agenda.router)

# Fases seguintes registram seus routers aqui:
#   Fase 4: enrollments
#   Fase 5: charges
#   Fase 6: dashboard
