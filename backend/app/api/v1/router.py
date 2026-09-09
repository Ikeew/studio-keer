from fastapi import APIRouter

from app.api.v1 import auth, health, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])

# Fases seguintes registram seus routers aqui:
#   Fase 2: patients, services
#   Fase 3: schedule, bookings
#   Fase 4: enrollments
#   Fase 5: charges
#   Fase 6: dashboard
