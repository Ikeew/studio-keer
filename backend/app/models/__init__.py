"""Models do SQLAlchemy.

Todo model precisa ser importado aqui: o Alembic descobre as tabelas por
`Base.metadata`, que só é populado quando a classe é importada. Model que
falta nesta lista some silenciosamente do autogenerate.
"""

from app.models.booking import Booking, OrigemReserva, StatusReserva
from app.models.configuracao import Configuracao, HorarioFuncionamento, JanelaReposicao
from app.models.enrollment import (
    Blackout,
    Enrollment,
    EnrollmentHorario,
    StatusMatricula,
)
from app.models.package import Package, StatusPacote
from app.models.patient import EstadoCivil, Patient, Sexo
from app.models.service import ModeloCobranca, Service
from app.models.session import Session, StatusSessao
from app.models.user import Papel, User

__all__ = [
    "Blackout",
    "Booking",
    "Configuracao",
    "Enrollment",
    "EnrollmentHorario",
    "EstadoCivil",
    "HorarioFuncionamento",
    "JanelaReposicao",
    "ModeloCobranca",
    "OrigemReserva",
    "Package",
    "Papel",
    "Patient",
    "Service",
    "Session",
    "Sexo",
    "StatusMatricula",
    "StatusPacote",
    "StatusReserva",
    "StatusSessao",
    "User",
]
