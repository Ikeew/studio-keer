"""Indicadores do dashboard.

Nada aqui é armazenado. Todo número é contado no momento da consulta, pelo
mesmo motivo que vale para saldo, vagas e "vencido": um valor gravado sai de
sincronia e mente até alguém recalcular.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session as DbSession

from app.models.booking import Booking, StatusReserva
from app.models.patient import Patient
from app.models.service import Service
from app.models.session import Session, StatusSessao
from app.models.user import User
from app.services.schedule_service import FUSO

#: Reservas que ocupam vaga. Cancelada não ocupa — a vaga voltou ao pool.
_ATIVAS = (
    StatusReserva.AGENDADA,
    StatusReserva.CONFIRMADA,
    StatusReserva.PRESENTE,
    StatusReserva.FALTA,
)


def _intervalo(inicio: date, fim: date) -> tuple[datetime, datetime]:
    """Dia inteiro no fuso do studio, do primeiro instante ao último."""
    return (
        datetime.combine(inicio, time.min, tzinfo=FUSO),
        datetime.combine(fim + timedelta(days=1), time.min, tzinfo=FUSO),
    )


def _sessoes_no_periodo(inicio: date, fim: date) -> Select[tuple[int]]:
    de, ate = _intervalo(inicio, fim)
    return select(Session.id).where(
        Session.inicia_em >= de,
        Session.inicia_em < ate,
        Session.status != StatusSessao.CANCELADA,
    )


@dataclass(frozen=True)
class TaxaDeOcupacao:
    """Quanto da capacidade oferecida foi efetivamente ocupada.

    ── A FÓRMULA ────────────────────────────────────────────────────────────

        taxa = reservas_ativas / capacidade_ofertada

    onde, no período:

      reservas_ativas     contagem de `bookings` cujo status ocupa vaga —
                          agendada, confirmada, presente ou falta.
                          CANCELADA não conta: a vaga voltou ao pool e pode
                          ter sido ocupada por outra pessoa, que é contada
                          separadamente. Contar cancelada inflaria a taxa com
                          lugares que ficaram vazios.

                          FALTA conta: a aula aconteceu com aquele lugar
                          reservado e ninguém mais pôde usá-lo. Do ponto de
                          vista de capacidade, o studio estava ocupado. É por
                          isso que a taxa mede OCUPAÇÃO, não comparecimento.

      capacidade_ofertada soma da `capacidade` de todas as sessões não
                          canceladas do período. É a capacidade real de cada
                          turma, e não `capacidade_padrao` do serviço — uma
                          sessão pode ter override.

    Sem sessão no período a taxa é 0%, não indefinida: um studio sem aula
    marcada tem ocupação zero.

    ── O QUE ESTA TAXA NÃO É ────────────────────────────────────────────────

    Não é taxa de comparecimento (que excluiria faltas) nem de aproveitamento
    financeiro. É quanto dos lugares oferecidos foram vendidos.
    """

    reservas_ativas: int
    capacidade_ofertada: int

    @property
    def percentual(self) -> int:
        if self.capacidade_ofertada == 0:
            return 0
        return round(100 * self.reservas_ativas / self.capacidade_ofertada)


def taxa_de_ocupacao(db: DbSession, inicio: date, fim: date) -> TaxaDeOcupacao:
    sessoes = _sessoes_no_periodo(inicio, fim).subquery()

    capacidade = int(
        db.execute(
            select(func.coalesce(func.sum(Session.capacidade), 0)).where(
                Session.id.in_(select(sessoes.c.id))
            )
        ).scalar_one()
    )
    reservas = int(
        db.execute(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.session_id.in_(select(sessoes.c.id)),
                Booking.status.in_(_ATIVAS),
            )
        ).scalar_one()
    )
    return TaxaDeOcupacao(reservas_ativas=reservas, capacidade_ofertada=capacidade)


@dataclass
class ProximoAgendamento:
    booking_id: int
    hora: str
    paciente_nome: str
    servico_nome: str
    instrutor_nome: str
    status: StatusReserva


@dataclass
class Indicadores:
    agendamentos_hoje: int
    pacientes_ativos: int
    sessoes_no_mes: int
    ocupacao: TaxaDeOcupacao
    proximos: list[ProximoAgendamento]


def _proximos_de(
    db: DbSession, dia: date, *, professional_id: int | None = None, limite: int = 8
) -> list[ProximoAgendamento]:
    de, ate = _intervalo(dia, dia)
    stmt = (
        select(Booking, Session, Patient, Service, User)
        .join(Session, Session.id == Booking.session_id)
        .join(Patient, Patient.id == Booking.patient_id)
        .join(Service, Service.id == Session.service_id)
        .join(User, User.id == Session.professional_id)
        .where(
            Session.inicia_em >= de,
            Session.inicia_em < ate,
            Session.status != StatusSessao.CANCELADA,
            Booking.status != StatusReserva.CANCELADA,
        )
        .order_by(Session.inicia_em, Booking.posicao)
        .limit(limite)
    )
    if professional_id is not None:
        stmt = stmt.where(Session.professional_id == professional_id)

    return [
        ProximoAgendamento(
            booking_id=reserva.id,
            hora=f"{sessao.inicia_em.astimezone(FUSO):%H:%M}",
            paciente_nome=paciente.nome_completo,
            servico_nome=servico.nome,
            instrutor_nome=instrutor.nome,
            status=reserva.status,
        )
        for reserva, sessao, paciente, servico, instrutor in db.execute(stmt).all()
    ]


def indicadores(db: DbSession) -> Indicadores:
    hoje = date.today()
    primeiro_do_mes = hoje.replace(day=1)
    proximo_mes = (primeiro_do_mes + timedelta(days=32)).replace(day=1)
    ultimo_do_mes = proximo_mes - timedelta(days=1)

    de_hoje, ate_hoje = _intervalo(hoje, hoje)
    agendamentos_hoje = int(
        db.execute(
            select(func.count())
            .select_from(Booking)
            .join(Session, Session.id == Booking.session_id)
            .where(
                Session.inicia_em >= de_hoje,
                Session.inicia_em < ate_hoje,
                Session.status != StatusSessao.CANCELADA,
                Booking.status != StatusReserva.CANCELADA,
            )
        ).scalar_one()
    )

    pacientes_ativos = int(
        db.execute(
            select(func.count()).select_from(Patient).where(Patient.ativo.is_(True))
        ).scalar_one()
    )

    sessoes_no_mes = int(
        db.execute(
            select(func.count()).select_from(
                _sessoes_no_periodo(primeiro_do_mes, ultimo_do_mes).subquery()
            )
        ).scalar_one()
    )

    return Indicadores(
        agendamentos_hoje=agendamentos_hoje,
        pacientes_ativos=pacientes_ativos,
        sessoes_no_mes=sessoes_no_mes,
        ocupacao=taxa_de_ocupacao(db, primeiro_do_mes, ultimo_do_mes),
        proximos=_proximos_de(db, hoje),
    )


def agenda_do_instrutor(db: DbSession, professional_id: int) -> list[ProximoAgendamento]:
    """Aulas de hoje do instrutor. Somente leitura — é a tela dele."""
    return _proximos_de(db, date.today(), professional_id=professional_id, limite=50)


@dataclass
class EstatisticaDeServico:
    service_id: int
    nome: str
    cor: str
    #: Sessões realizadas ou marcadas no mês.
    sessoes_no_mes: int
    #: Reservas que ocuparam vaga no mês.
    reservas_no_mes: int
    ocupacao_percentual: int


def estatisticas_de_servicos(db: DbSession) -> list[EstatisticaDeServico]:
    """Painel da tela de Atividades, como no print."""
    hoje = date.today()
    primeiro = hoje.replace(day=1)
    ultimo = (primeiro + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    de, ate = _intervalo(primeiro, ultimo)

    saida: list[EstatisticaDeServico] = []
    for servico in db.execute(
        select(Service).where(Service.ativo.is_(True)).order_by(Service.nome)
    ).scalars():
        sessoes = list(
            db.execute(
                select(Session.id, Session.capacidade).where(
                    Session.service_id == servico.id,
                    Session.inicia_em >= de,
                    Session.inicia_em < ate,
                    Session.status != StatusSessao.CANCELADA,
                )
            ).all()
        )
        ids = [s for s, _ in sessoes]
        capacidade = sum(c for _, c in sessoes)
        reservas = (
            int(
                db.execute(
                    select(func.count())
                    .select_from(Booking)
                    .where(
                        Booking.session_id.in_(ids),
                        Booking.status.in_(_ATIVAS),
                    )
                ).scalar_one()
            )
            if ids
            else 0
        )
        saida.append(
            EstatisticaDeServico(
                service_id=servico.id,
                nome=servico.nome,
                cor=servico.cor,
                sessoes_no_mes=len(ids),
                reservas_no_mes=reservas,
                ocupacao_percentual=round(100 * reservas / capacidade) if capacidade else 0,
            )
        )
    return saida
