"""Reposições pendentes.

É o item de maior retorno do sistema: hoje isso vive na cabeça da Dra.
Belanir, que controla as reposições de memória. Nada aqui é armazenado — é
uma consulta sobre o que já existe, então não há o que sair de sincronia.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import aliased

from app.models.booking import Booking, StatusReserva
from app.models.configuracao import Configuracao, JanelaReposicao
from app.models.enrollment import Enrollment
from app.models.patient import Patient
from app.models.service import Service
from app.models.session import Session
from app.services.schedule_service import FUSO


@dataclass
class FaltaPendente:
    """Uma falta que ainda dá direito a repor e ainda não foi reposta."""

    booking_id: int
    patient_id: int
    paciente_nome: str
    paciente_telefone: str | None
    servico_nome: str
    service_id: int
    faltou_em: datetime
    justificada: bool
    motivo: str | None
    repor_ate: date | None
    dias_restantes: int | None


def _config(db: DbSession) -> Configuracao:
    cfg = db.get(Configuracao, 1)
    if cfg is None:
        # Sem configuração o sistema opera no padrão mais restritivo, em vez
        # de assumir que tudo é permitido.
        return Configuracao(
            id=1,
            reposicao_exige_justificativa=True,
            janela_reposicao=JanelaReposicao.MES_CALENDARIO,
            falta_consome_sessao_do_pacote=False,
        )
    return cfg


def _fim_do_mes(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])


def prazo_para_repor(db: DbSession, falta_em: date, matricula: Enrollment | None) -> date | None:
    """Até quando a falta pode ser reposta.

    A JANELA DE REPOSIÇÃO é operacional e INDEPENDENTE do ciclo de cobrança —
    os dois só se parecem por usarem a palavra "mês". Ver docs/premissas.md
    (P2). O padrão é mês do calendário, porque é o que uma pessoa quer dizer
    ao falar "dentro do mesmo mês".
    """
    janela = _config(db).janela_reposicao

    if janela is JanelaReposicao.SEM_PRAZO:
        return None

    if janela is JanelaReposicao.CICLO_DO_PACIENTE and matricula is not None:
        # Fim do ciclo do paciente: o dia anterior ao próximo vencimento dele.
        dia = min(matricula.dia_vencimento, monthrange(falta_em.year, falta_em.month)[1])
        vencimento = date(falta_em.year, falta_em.month, dia)
        if falta_em >= vencimento:
            proximo_mes = (falta_em.replace(day=1) + timedelta(days=32)).replace(day=1)
            dia = min(matricula.dia_vencimento, monthrange(proximo_mes.year, proximo_mes.month)[1])
            vencimento = date(proximo_mes.year, proximo_mes.month, dia)
        return vencimento - timedelta(days=1)

    return _fim_do_mes(falta_em)


def listar_pendentes(db: DbSession, *, incluir_vencidas: bool = False) -> list[FaltaPendente]:
    """Faltas que ainda podem ser repostas e ainda não foram.

    Uma falta é pendente quando:
      - status = 'falta'
      - E (a configuração não exige justificativa OU ela é justificada)
      - E ninguém ainda repôs esta falta (NOT EXISTS)
      - E ainda está dentro da janela de reposição
    """
    cfg = _config(db)
    hoje = date.today()

    reposicao = aliased(Booking)
    stmt = (
        select(Booking, Patient, Service, Session)
        .join(Session, Session.id == Booking.session_id)
        .join(Patient, Patient.id == Booking.patient_id)
        .join(Service, Service.id == Session.service_id)
        .where(
            Booking.status == StatusReserva.FALTA,
            # NOT EXISTS: ninguém repôs esta falta ainda.
            ~select(reposicao.id)
            .where(
                reposicao.substitui_booking_id == Booking.id,
                reposicao.status != StatusReserva.CANCELADA,
            )
            .exists(),
        )
        .order_by(Session.inicia_em.desc())
    )
    if cfg.reposicao_exige_justificativa:
        stmt = stmt.where(Booking.justificada.is_(True))

    pendentes: list[FaltaPendente] = []
    for reserva, paciente, servico, sessao in db.execute(stmt).all():
        matricula = (
            db.get(Enrollment, reserva.enrollment_id) if reserva.enrollment_id is not None else None
        )
        faltou_em = sessao.inicia_em.astimezone(FUSO)
        limite = prazo_para_repor(db, faltou_em.date(), matricula)

        if limite is not None and limite < hoje and not incluir_vencidas:
            continue

        pendentes.append(
            FaltaPendente(
                booking_id=reserva.id,
                patient_id=paciente.id,
                paciente_nome=paciente.nome_completo,
                paciente_telefone=paciente.telefone,
                servico_nome=servico.nome,
                service_id=servico.id,
                faltou_em=faltou_em,
                justificada=reserva.justificada,
                motivo=reserva.motivo_justificativa,
                repor_ate=limite,
                dias_restantes=(limite - hoje).days if limite is not None else None,
            )
        )
    return pendentes


def periodo_para_oferecer(db: DbSession, pendente: FaltaPendente) -> tuple[date, date]:
    """Intervalo em que faz sentido procurar vaga para esta falta.

    Começa amanhã (não adianta oferecer horário que já passou) e termina no
    prazo — ou no horizonte de materialização, quando não há prazo.
    """
    from app.services.enrollment_service import HORIZONTE_SEMANAS

    inicio = date.today() + timedelta(days=1)
    fim = pendente.repor_ate or (date.today() + timedelta(weeks=HORIZONTE_SEMANAS))
    return inicio, max(inicio, fim)
