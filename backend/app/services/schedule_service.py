"""Montagem da grade semanal.

Regra que guia este módulo: A GRADE NÃO PODE OFERECER O QUE NÃO EXISTE.
Horário na pausa não aparece. Horário fora da janela do dia não aparece. Dia
fechado não aparece. Turma cheia é mostrada como cheia ANTES de a recepção
oferecer a vaga ao paciente.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import get_settings
from app.models.booking import Booking, StatusReserva
from app.models.configuracao import HorarioFuncionamento
from app.models.patient import Patient
from app.models.service import Service
from app.models.session import Session, StatusSessao
from app.models.user import User
from app.services import booking_service

settings = get_settings()
FUSO = ZoneInfo(settings.TIMEZONE)


@dataclass(frozen=True)
class JanelaDoDia:
    dia: date
    aberto: bool
    horas: tuple[time, ...]
    hora_abertura: time | None
    hora_fechamento: time | None
    pausa_inicio: time | None
    pausa_fim: time | None


def _dia_semana_db(d: date) -> int:
    """date.weekday() é 0=segunda; o banco usa 0=domingo."""
    return (d.weekday() + 1) % 7


def _horas_do_dia(cfg: HorarioFuncionamento) -> tuple[time, ...]:
    """Horas cheias atendíveis no dia, já SEM a pausa.

    A pausa é removida aqui, e não escondida na tela, para que a API nunca
    devolva um horário que o studio não atende — a grade e as consultas de
    disponibilidade compartilham esta função.
    """
    if not cfg.aberto:
        return ()

    horas: list[time] = []
    hora = cfg.hora_abertura.hour
    while hora < cfg.hora_fechamento.hour:
        atual = time(hour=hora)
        na_pausa = (
            cfg.pausa_inicio is not None
            and cfg.pausa_fim is not None
            and cfg.pausa_inicio <= atual < cfg.pausa_fim
        )
        if not na_pausa:
            horas.append(atual)
        hora += 1
    return tuple(horas)


def janela_da_semana(db: DbSession, inicio: date) -> list[JanelaDoDia]:
    """Sete dias a partir de `inicio`, com as horas atendíveis de cada um."""
    config = {c.dia_semana: c for c in db.execute(select(HorarioFuncionamento)).scalars().all()}
    if not config:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Horário de funcionamento não configurado. "
                "Rode: python -m app.cli seed-configuracao"
            ),
        )

    janelas: list[JanelaDoDia] = []
    for offset in range(7):
        dia = inicio + timedelta(days=offset)
        cfg = config.get(_dia_semana_db(dia))
        if cfg is None or not cfg.aberto:
            janelas.append(JanelaDoDia(dia, False, (), None, None, None, None))
            continue
        janelas.append(
            JanelaDoDia(
                dia=dia,
                aberto=True,
                horas=_horas_do_dia(cfg),
                hora_abertura=cfg.hora_abertura,
                hora_fechamento=cfg.hora_fechamento,
                pausa_inicio=cfg.pausa_inicio,
                pausa_fim=cfg.pausa_fim,
            )
        )
    return janelas


def horario_e_atendivel(db: DbSession, momento: datetime) -> bool:
    """Se o studio atende naquele instante. Usado ao criar sessão."""
    # Defesa em profundidade: se um chamador interno passar datetime ingênuo,
    # ele é do fuso do studio — nunca do fuso do servidor.
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=FUSO)
    local = momento.astimezone(FUSO)
    cfg = db.get(HorarioFuncionamento, _dia_semana_db(local.date()))
    if cfg is None or not cfg.aberto:
        return False
    return time(hour=local.hour) in _horas_do_dia(cfg)


def inicio_da_semana(referencia: date) -> date:
    """Segunda-feira da semana de `referencia`.

    A grade dos prints começa na segunda; o domingo (fechado) fecha a semana.
    """
    return referencia - timedelta(days=referencia.weekday())


@dataclass
class SessaoNaGrade:
    sessao: Session
    servico: Service
    instrutor: User
    ocupadas: int
    reservas: list[tuple[Booking, Patient]]


def sessoes_da_semana(db: DbSession, inicio: date, fim: date) -> list[SessaoNaGrade]:
    """Sessões materializadas do período, com ocupação e nomes já resolvidos.

    Só devolve o que EXISTE no banco. Um horário sem sessão não é "livre":
    é um horário sem turma — a diferença importa, ver `sessoes_com_vaga`.
    """
    comeco = datetime.combine(inicio, time.min, tzinfo=FUSO)
    termino = datetime.combine(fim + timedelta(days=1), time.min, tzinfo=FUSO)

    linhas = db.execute(
        select(Session, Service, User)
        .join(Service, Service.id == Session.service_id)
        .join(User, User.id == Session.professional_id)
        .where(
            Session.inicia_em >= comeco,
            Session.inicia_em < termino,
            Session.status != StatusSessao.CANCELADA,
        )
        .order_by(Session.inicia_em)
    ).all()

    sessoes = [s for s, _, _ in linhas]
    ocupacao = booking_service.contar_ocupacao(db, [s.id for s in sessoes])

    reservas_por_sessao: dict[int, list[tuple[Booking, Patient]]] = {}
    if sessoes:
        for reserva, paciente in db.execute(
            select(Booking, Patient)
            .join(Patient, Patient.id == Booking.patient_id)
            .where(
                Booking.session_id.in_([s.id for s in sessoes]),
                Booking.status != StatusReserva.CANCELADA,
            )
            .order_by(Booking.posicao)
        ).all():
            reservas_por_sessao.setdefault(reserva.session_id, []).append((reserva, paciente))

    return [
        SessaoNaGrade(
            sessao=sessao,
            servico=servico,
            instrutor=instrutor,
            ocupadas=ocupacao.get(sessao.id, 0),
            reservas=reservas_por_sessao.get(sessao.id, []),
        )
        for sessao, servico, instrutor in linhas
    ]


def sessoes_com_vaga(
    db: DbSession,
    *,
    de: date,
    ate: date,
    service_id: int | None = None,
    excluir_patient_id: int | None = None,
) -> list[SessaoNaGrade]:
    """Sessões que ainda comportam mais um paciente — a base da reposição.

    ── A ARMADILHA DA MATERIALIZAÇÃO ────────────────────────────────────────

    Esta consulta olha SOMENTE sessões já materializadas, com as reservas que
    elas já têm. Isso é deliberado.

    Se a disponibilidade fosse calculada a partir da grade teórica de horários
    ("segunda 08:00 existe, logo está livre"), um horário ainda não
    materializado pareceria vago, receberia a reposição, e depois seria
    preenchido pelo gerador de recorrência da Fase 4 — recriando o overbooking
    pelo caminho oposto ao que estamos evitando.

    CONTRATO COM A FASE 4: o gerador materializa com semanas de antecedência e
    respeita reservas já existentes. Enquanto uma sessão não existe, ela não é
    oferecida — "sem turma nesse horário" é resposta melhor que uma vaga que
    pode evaporar.
    """
    candidatas = sessoes_da_semana(db, de, ate)

    resultado = []
    for item in candidatas:
        if service_id is not None and item.sessao.service_id != service_id:
            continue
        if item.ocupadas >= item.sessao.capacidade:
            continue
        # Não oferecer um horário em que o paciente já está.
        if excluir_patient_id is not None and any(
            p.id == excluir_patient_id for _, p in item.reservas
        ):
            continue
        resultado.append(item)
    return resultado
