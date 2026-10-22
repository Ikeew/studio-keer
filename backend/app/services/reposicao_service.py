"""Reposições pendentes.

É o item de maior retorno do sistema: hoje isso vive na cabeça da Dra.
Belanir, que controla as reposições de memória. Nada aqui é armazenado — é
uma consulta sobre o que já existe, então não há o que sair de sincronia.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import aliased

from app.models.booking import Booking, OrigemReserva, StatusReserva
from app.models.configuracao import Configuracao, JanelaReposicao
from app.models.enrollment import Enrollment
from app.models.patient import Patient
from app.models.service import Service
from app.models.session import Session
from app.services.schedule_service import FUSO

#: O que gerou o direito: falta registrada, ou aviso de que não vinha.
TipoPendencia = Literal["falta", "aviso"]


@dataclass
class FaltaPendente:
    """Uma falta (ou aviso) que ainda dá direito a repor e não foi reposta."""

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
    tipo: TipoPendencia = "falta"


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


def hoje_no_studio() -> date:
    """O dia de HOJE no fuso do studio, não no do servidor.

    `date.today()` usa o fuso do processo, que em container é UTC: a partir
    das 21h em São Paulo já seria "amanhã", e o prazo do último dia do mês
    venceria três horas antes da hora.
    """
    return datetime.now(FUSO).date()


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
    """Faltas e avisos que ainda podem ser repostos e ainda não foram.

    Dá direito a repor (confirmado pela cliente, premissas.md P5):
      - FALTA, se a configuração não exige justificativa OU ela é justificada
      - CANCELADA COM AVISO: o paciente avisou que não vinha. Reposição
        cancelada fica de fora — quem volta a ficar pendente é a falta que
        ela repunha, e contar as duas daria direito em dobro.

    E, nos dois casos:
      - ninguém ainda repôs (NOT EXISTS)
      - ainda está dentro da janela de reposição
    """
    cfg = _config(db)
    hoje = hoje_no_studio()

    falta = Booking.status == StatusReserva.FALTA
    if cfg.reposicao_exige_justificativa:
        falta = and_(falta, Booking.justificada.is_(True))
    aviso = and_(
        Booking.status == StatusReserva.CANCELADA,
        Booking.cancelado_com_aviso.is_(True),
        Booking.origem != OrigemReserva.REPOSICAO,
    )

    reposicao = aliased(Booking)
    stmt = (
        select(Booking, Patient, Service, Session)
        .join(Session, Session.id == Booking.session_id)
        .join(Patient, Patient.id == Booking.patient_id)
        .join(Service, Service.id == Session.service_id)
        .where(
            or_(falta, aviso),
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

    pendentes: list[FaltaPendente] = []
    for reserva, paciente, servico, sessao in db.execute(stmt).all():
        matricula = (
            db.get(Enrollment, reserva.enrollment_id) if reserva.enrollment_id is not None else None
        )
        faltou_em = sessao.inicia_em.astimezone(FUSO)
        limite = prazo_para_repor(db, faltou_em.date(), matricula)

        if limite is not None and limite < hoje and not incluir_vencidas:
            continue

        avisou = reserva.status is StatusReserva.CANCELADA
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
                motivo=reserva.motivo_cancelamento if avisou else reserva.motivo_justificativa,
                repor_ate=limite,
                dias_restantes=(limite - hoje).days if limite is not None else None,
                tipo="aviso" if avisou else "falta",
            )
        )
    return pendentes


def periodo_para_oferecer(db: DbSession, pendente: FaltaPendente) -> tuple[date, date]:
    """Intervalo em que faz sentido procurar vaga para esta falta.

    Começa amanhã (não adianta oferecer horário que já passou) e termina no
    prazo — ou no horizonte de materialização, quando não há prazo.
    """
    from app.services.enrollment_service import HORIZONTE_SEMANAS

    hoje = hoje_no_studio()
    inicio = hoje + timedelta(days=1)
    fim = pendente.repor_ate or (hoje + timedelta(weeks=HORIZONTE_SEMANAS))
    return inicio, max(inicio, fim)
