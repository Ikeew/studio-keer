"""Matrículas e geração da grade recorrente.

Dois pontos críticos vivem aqui:

1. A capacidade é verificada AO CRIAR O HORÁRIO DA MATRÍCULA — o segundo dos
   três pontos de verificação, e onde nasce o overbooking vendido no balcão.
2. O gerador é IDEMPOTENTE e materializa com antecedência, honrando o
   contrato deixado na Fase 3 (reposição só enxerga sessão materializada).
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.models.booking import Booking, OrigemReserva, StatusReserva
from app.models.enrollment import (
    Blackout,
    Enrollment,
    EnrollmentHorario,
    StatusMatricula,
)
from app.models.service import Service
from app.models.session import Session, StatusSessao
from app.models.user import Papel, User
from app.services import booking_service, schedule_service
from app.services.schedule_service import FUSO

# ── HORIZONTE DE MATERIALIZAÇÃO ──────────────────────────────────────────────
#
# 8 semanas. A escolha é um equilíbrio entre dois erros opostos:
#
# CURTO DEMAIS quebra a reposição. Na Fase 3 ficou definido que a
# disponibilidade só enxerga sessão já materializada — horizonte de 2 semanas
# faria a recepção não achar vaga que existe, e ela voltaria a encaixar de
# cabeça, que é exatamente o problema que o sistema veio resolver.
#
# LONGO DEMAIS vira lixo. Matrícula muda: aluno troca de horário, suspende,
# encerra. Cada semana materializada além do necessário é uma semana de
# reservas para remanejar quando isso acontece.
#
# 8 semanas cobrem com folga a janela de reposição (mês do calendário, no
# máximo ~5 semanas) e ainda deixam margem para a recepção oferecer reposição
# no mês seguinte quando o mês corrente estiver lotado.
HORIZONTE_SEMANAS = 8


#: Abaixo disto a grade é considerada curta e a interface avisa. Três semanas
#: dão folga para alguém reparar no aviso, clicar no botão e ainda sobrar
#: horizonte — o modo de falha real não é a grade acabar, é ninguém notar que
#: ela está acabando.
SEMANAS_MINIMAS = 3


def _dia_semana_db(d: date) -> int:
    return (d.weekday() + 1) % 7


@dataclass
class SaudeDaGrade:
    """Até quando a grade está materializada.

    Existe porque o modo de falha da geração manual é SILENCIOSO: a grade
    esvazia, a busca por vaga para de achar horário, e a recepção volta a
    encaixar de cabeça — exatamente a dor que o sistema veio resolver. Um
    aviso na tela custa pouco e ataca isso direto.
    """

    materializado_ate: date | None
    dias_restantes: int
    semanas_restantes: int
    #: Sem nenhuma sessão futura: a grade acabou.
    vencida: bool
    #: Abaixo do mínimo: ainda funciona, mas precisa ser atualizada.
    precisa_atualizar: bool
    matriculas_ativas: int


def saude_da_grade(db: DbSession) -> SaudeDaGrade:
    hoje = date.today()
    agora = datetime.combine(hoje, time.min, tzinfo=FUSO)

    ate = db.execute(
        select(func.max(Session.inicia_em)).where(
            Session.inicia_em >= agora,
            Session.status != StatusSessao.CANCELADA,
        )
    ).scalar_one_or_none()

    ativas = db.execute(
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.status == StatusMatricula.ATIVA)
    ).scalar_one()

    if ate is None:
        # Sem matrícula ativa não há grade a manter, e avisar seria ruído.
        return SaudeDaGrade(
            materializado_ate=None,
            dias_restantes=0,
            semanas_restantes=0,
            vencida=ativas > 0,
            precisa_atualizar=ativas > 0,
            matriculas_ativas=ativas,
        )

    limite = ate.astimezone(FUSO).date()
    dias = (limite - hoje).days
    semanas = dias // 7
    return SaudeDaGrade(
        materializado_ate=limite,
        dias_restantes=dias,
        semanas_restantes=semanas,
        vencida=False,
        precisa_atualizar=ativas > 0 and semanas < SEMANAS_MINIMAS,
        matriculas_ativas=ativas,
    )


def frequencia_semanal(matricula: Enrollment) -> int:
    """Derivada da contagem de horários — nunca um campo."""
    return len(matricula.horarios)


def em_blackout(db: DbSession, dia: date) -> Blackout | None:
    return db.execute(
        select(Blackout).where(Blackout.data_inicio <= dia, Blackout.data_fim >= dia)
    ).scalar_one_or_none()


def _matriculas_ativas_no_slot(
    db: DbSession,
    *,
    service_id: int,
    dia_semana: int,
    hora: time,
    excluir_enrollment_id: int | None = None,
) -> list[Enrollment]:
    stmt = (
        select(Enrollment)
        .join(EnrollmentHorario, EnrollmentHorario.enrollment_id == Enrollment.id)
        .where(
            Enrollment.service_id == service_id,
            Enrollment.status == StatusMatricula.ATIVA,
            EnrollmentHorario.dia_semana == dia_semana,
            EnrollmentHorario.hora_inicio == hora,
        )
    )
    if excluir_enrollment_id is not None:
        stmt = stmt.where(Enrollment.id != excluir_enrollment_id)
    return list(db.execute(stmt).scalars().unique().all())


def verificar_capacidade_do_slot(
    db: DbSession,
    *,
    service_id: int,
    dia_semana: int,
    hora: time,
    excluir_enrollment_id: int | None = None,
) -> None:
    """PONTO 2 DA CAPACIDADE: a venda do horário fixo.

    Se cinco pessoas têm horário fixo às segundas 08:00 e a capacidade é 4,
    TODA ocorrência nasce lotada e nenhuma reposição está envolvida — o
    overbooking foi vendido no balcão, meses antes.

    A mensagem diz que o problema é o HORÁRIO estar completo, e não a reserva
    de hoje: quem lê precisa entender que não adianta tentar de novo amanhã.
    """
    servico = db.get(Service, service_id)
    if servico is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serviço não encontrado")

    ocupantes = _matriculas_ativas_no_slot(
        db,
        service_id=service_id,
        dia_semana=dia_semana,
        hora=hora,
        excluir_enrollment_id=excluir_enrollment_id,
    )
    if len(ocupantes) >= servico.capacidade_padrao:
        nomes = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"O horário de {nomes[dia_semana]} às {hora:%H:%M} já tem "
                f"{len(ocupantes)} alunos fixos em {servico.nome}, que é a "
                f"capacidade da turma. Não é a reserva de hoje que está cheia: "
                f"é o horário. Escolha outro horário ou libere uma matrícula."
            ),
        )


def buscar(db: DbSession, enrollment_id: int) -> Enrollment:
    matricula = db.get(Enrollment, enrollment_id)
    if matricula is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Matrícula não encontrada"
        )
    return matricula


def criar(
    db: DbSession,
    *,
    patient_id: int,
    service_id: int,
    professional_id: int,
    vigencia_inicio: date,
    valor_mensal_centavos: int,
    horarios: list[tuple[int, time]],
    vigencia_fim: date | None = None,
) -> Enrollment:
    """Cria a matrícula, verificando a capacidade de CADA horário."""
    if not horarios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A matrícula precisa de pelo menos um horário fixo.",
        )

    instrutor = db.get(User, professional_id)
    if instrutor is None or instrutor.papel not in (Papel.INSTRUTOR, Papel.ADMIN):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Instrutor inválido")

    for dia_semana, hora in horarios:
        # O studio precisa atender naquele horário — senão a matrícula geraria
        # sessões que a grade nunca mostraria.
        exemplo = _proxima_data_do_dia(vigencia_inicio, dia_semana)
        momento = datetime.combine(exemplo, hora, tzinfo=FUSO)
        if not schedule_service.horario_e_atendivel(db, momento):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"O studio não atende {hora:%H:%M} nesse dia da semana. "
                    "Verifique a janela de funcionamento e a pausa."
                ),
            )
        verificar_capacidade_do_slot(db, service_id=service_id, dia_semana=dia_semana, hora=hora)

    matricula = Enrollment(
        patient_id=patient_id,
        service_id=service_id,
        professional_id=professional_id,
        vigencia_inicio=vigencia_inicio,
        vigencia_fim=vigencia_fim,
        valor_mensal_centavos=valor_mensal_centavos,
        dia_vencimento=vigencia_inicio.day,
        horarios=[EnrollmentHorario(dia_semana=d, hora_inicio=h) for d, h in horarios],
    )
    db.add(matricula)
    db.flush()
    return matricula


def _proxima_data_do_dia(a_partir_de: date, dia_semana: int) -> date:
    """Primeira data >= `a_partir_de` que cai naquele dia da semana."""
    delta = (dia_semana - _dia_semana_db(a_partir_de)) % 7
    return a_partir_de + timedelta(days=delta)


@dataclass
class ResultadoGeracao:
    sessoes_criadas: int = 0
    sessoes_reaproveitadas: int = 0
    reservas_criadas: int = 0
    reservas_ja_existentes: int = 0
    dias_em_blackout: int = 0
    sem_vaga: list[str] = field(default_factory=list)


def gerar_grade(
    db: DbSession,
    *,
    criado_por_id: int,
    ate: date | None = None,
    enrollment_id: int | None = None,
) -> ResultadoGeracao:
    """Materializa sessões e reservas recorrentes até o horizonte.

    ── IDEMPOTÊNCIA ─────────────────────────────────────────────────────────

    Rodar duas vezes não duplica nada, e uma execução interrompida no meio
    pode ser repetida sem limpeza:

    - Sessão: procura uma equivalente (serviço + instrutor + instante) antes
      de criar; se existir, reaproveita.
    - Reserva: o índice único parcial
      `(enrollment_id, session_id) WHERE enrollment_id IS NOT NULL AND
      status <> 'cancelada'` garante no banco que uma matrícula tem no máximo
      uma reserva por sessão. A checagem em Python evita o erro no caminho
      feliz; o índice cobre a corrida.

    ── CONTRATO COM A FASE 3 ────────────────────────────────────────────────

    A disponibilidade para reposição só enxerga sessão materializada. Este
    gerador é quem materializa, com HORIZONTE_SEMANAS de antecedência, e
    RESPEITA reservas já existentes em vez de assumir a sessão vazia.
    """
    resultado = ResultadoGeracao()
    hoje = date.today()
    limite = ate or (hoje + timedelta(weeks=HORIZONTE_SEMANAS))

    stmt = select(Enrollment).where(Enrollment.status == StatusMatricula.ATIVA)
    if enrollment_id is not None:
        stmt = stmt.where(Enrollment.id == enrollment_id)
    matriculas = list(db.execute(stmt).scalars().unique().all())

    servicos = {s.id: s for s in db.execute(select(Service)).scalars().all()}
    blackouts = list(db.execute(select(Blackout)).scalars().all())

    def bloqueado(d: date) -> bool:
        return any(b.data_inicio <= d <= b.data_fim for b in blackouts)

    for matricula in matriculas:
        servico = servicos[matricula.service_id]
        inicio = max(hoje, matricula.vigencia_inicio)
        fim = min(limite, matricula.vigencia_fim or limite)

        for horario in matricula.horarios:
            dia = _proxima_data_do_dia(inicio, horario.dia_semana)
            while dia <= fim:
                if bloqueado(dia):
                    resultado.dias_em_blackout += 1
                    dia += timedelta(days=7)
                    continue

                momento = datetime.combine(dia, horario.hora_inicio, tzinfo=FUSO)
                if not schedule_service.horario_e_atendivel(db, momento):
                    dia += timedelta(days=7)
                    continue

                sessao = _sessao_equivalente(db, matricula, momento)
                if sessao is None:
                    sessao = Session(
                        service_id=matricula.service_id,
                        professional_id=matricula.professional_id,
                        inicia_em=momento,
                        termina_em=momento + timedelta(minutes=servico.duracao_min),
                        capacidade=servico.capacidade_padrao,
                    )
                    db.add(sessao)
                    db.flush()
                    resultado.sessoes_criadas += 1
                else:
                    resultado.sessoes_reaproveitadas += 1

                if _ja_tem_reserva(db, matricula.id, sessao.id):
                    resultado.reservas_ja_existentes += 1
                else:
                    try:
                        booking_service.criar(
                            db,
                            session_id=sessao.id,
                            patient_id=matricula.patient_id,
                            criado_por_id=criado_por_id,
                            origem=OrigemReserva.RECORRENTE,
                            enrollment_id=matricula.id,
                        )
                        resultado.reservas_criadas += 1
                    except HTTPException as exc:
                        if exc.status_code != status.HTTP_409_CONFLICT:
                            raise
                        # Turma cheia por reposições ou avulsas encaixadas
                        # antes. O gerador NÃO fura a capacidade — reporta.
                        resultado.sem_vaga.append(
                            f"{dia:%d/%m} {horario.hora_inicio:%H:%M} — matrícula {matricula.id}"
                        )
                    except IntegrityError:
                        db.rollback()
                        resultado.reservas_ja_existentes += 1

                dia += timedelta(days=7)

    db.flush()
    return resultado


def _sessao_equivalente(db: DbSession, matricula: Enrollment, momento: datetime) -> Session | None:
    return db.execute(
        select(Session).where(
            Session.service_id == matricula.service_id,
            Session.professional_id == matricula.professional_id,
            Session.inicia_em == momento,
            Session.status != StatusSessao.CANCELADA,
        )
    ).scalar_one_or_none()


def _ja_tem_reserva(db: DbSession, enrollment_id: int, session_id: int) -> bool:
    return (
        db.execute(
            select(Booking.id).where(
                Booking.enrollment_id == enrollment_id,
                Booking.session_id == session_id,
                Booking.status != StatusReserva.CANCELADA,
            )
        ).first()
        is not None
    )


# ── ENCERRAMENTO E SUSPENSÃO ─────────────────────────────────────────────────
#
# DECISÃO: ao encerrar ou suspender, as reservas FUTURAS geradas por aquela
# matrícula são canceladas; as PASSADAS e as que já têm presença registrada
# ficam intactas.
#
# Por quê:
#   - Reserva futura sem matrícula ativa é lugar ocupado por quem não vem
#     mais. Deixá-la lá bloqueia vaga que a recepção poderia usar para
#     reposição — o oposto do que o sistema existe para fazer.
#   - Presença registrada é FATO CONSUMADO. A aula aconteceu; apagar isso
#     reescreveria o histórico do paciente e a base do faturamento. Vale
#     também para falta: a falta gera direito a reposição, e sumir com ela
#     apagaria esse direito.
#
# Suspender e encerrar fazem a mesma coisa com as reservas. A diferença é que
# a suspensa pode ser reativada, e reativar regenera a grade adiante.


def _reservas_futuras_da_matricula(db: DbSession, enrollment_id: int) -> list[Booking]:
    agora = datetime.now(tz=FUSO)
    return list(
        db.execute(
            select(Booking)
            .join(Session, Session.id == Booking.session_id)
            .where(
                Booking.enrollment_id == enrollment_id,
                Session.inicia_em > agora,
                # Presença e falta são fato consumado: nunca tocadas.
                Booking.status.in_([StatusReserva.AGENDADA, StatusReserva.CONFIRMADA]),
            )
        )
        .scalars()
        .all()
    )


def _liberar_reservas_futuras(db: DbSession, matricula: Enrollment, motivo: str) -> int:
    agora = datetime.now(tz=FUSO)
    liberadas = _reservas_futuras_da_matricula(db, matricula.id)
    for reserva in liberadas:
        reserva.status = StatusReserva.CANCELADA
        reserva.cancelado_em = agora
        reserva.motivo_cancelamento = motivo
    db.flush()
    return len(liberadas)


def suspender(db: DbSession, enrollment_id: int, *, motivo: str | None = None) -> int:
    """Suspende a matrícula e libera as vagas futuras. Devolve quantas."""
    matricula = buscar(db, enrollment_id)
    matricula.status = StatusMatricula.SUSPENSA
    return _liberar_reservas_futuras(db, matricula, motivo or "Matrícula suspensa")


def encerrar(
    db: DbSession,
    enrollment_id: int,
    *,
    em: date | None = None,
    motivo: str | None = None,
) -> int:
    matricula = buscar(db, enrollment_id)
    matricula.status = StatusMatricula.ENCERRADA
    matricula.vigencia_fim = em or date.today()
    return _liberar_reservas_futuras(db, matricula, motivo or "Matrícula encerrada")


def reativar(db: DbSession, enrollment_id: int, *, criado_por_id: int) -> ResultadoGeracao:
    """Reativa e regenera a grade adiante.

    A capacidade de cada horário é reverificada: enquanto a matrícula esteve
    suspensa, o lugar pode ter sido vendido a outra pessoa.
    """
    matricula = buscar(db, enrollment_id)
    if matricula.status is StatusMatricula.ATIVA:
        return ResultadoGeracao()

    for horario in matricula.horarios:
        verificar_capacidade_do_slot(
            db,
            service_id=matricula.service_id,
            dia_semana=horario.dia_semana,
            hora=horario.hora_inicio,
            excluir_enrollment_id=matricula.id,
        )

    matricula.status = StatusMatricula.ATIVA
    matricula.vigencia_fim = None
    db.flush()
    return gerar_grade(db, criado_por_id=criado_por_id, enrollment_id=matricula.id)


# ── BLACKOUTS ────────────────────────────────────────────────────────────────


@dataclass
class ConflitoDeBlackout:
    """Sessões que já existem dentro de um período de blackout novo."""

    sessoes: list[Session]
    reservas_ativas: int


def sessoes_afetadas_por_blackout(
    db: DbSession, data_inicio: date, data_fim: date
) -> ConflitoDeBlackout:
    """Lista o que um blackout novo atingiria — para AVISAR, não apagar.

    Mesmo princípio da redução de capacidade: o sistema não decide sozinho
    cancelar aula que já tem gente marcada. Quem cancela é a recepção, ciente
    de que precisa avisar os pacientes.
    """
    comeco = datetime.combine(data_inicio, time.min, tzinfo=FUSO)
    termino = datetime.combine(data_fim + timedelta(days=1), time.min, tzinfo=FUSO)

    sessoes = list(
        db.execute(
            select(Session)
            .where(
                Session.inicia_em >= comeco,
                Session.inicia_em < termino,
                Session.status != StatusSessao.CANCELADA,
            )
            .order_by(Session.inicia_em)
        )
        .scalars()
        .all()
    )
    ocupacao = booking_service.contar_ocupacao(db, [s.id for s in sessoes])
    return ConflitoDeBlackout(sessoes=sessoes, reservas_ativas=sum(ocupacao.values()))


def criar_blackout(
    db: DbSession, *, data_inicio: date, data_fim: date, motivo: str
) -> tuple[Blackout, ConflitoDeBlackout]:
    """Cria o blackout e devolve o que ele conflita, sem apagar nada."""
    conflito = sessoes_afetadas_por_blackout(db, data_inicio, data_fim)
    blackout = Blackout(data_inicio=data_inicio, data_fim=data_fim, motivo=motivo)
    db.add(blackout)
    db.flush()
    return blackout, conflito
