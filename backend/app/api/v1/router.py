from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])

# Fases seguintes registram seus routers aqui:
#   Fase 1: auth, users
#   Fase 2: patients, services
#   Fase 3: schedule, bookings
#   Fase 4: enrollments
#   Fase 5: charges
#   Fase 6: dashboard
