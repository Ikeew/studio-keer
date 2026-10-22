"""Regras de reserva. É aqui que a capacidade é respeitada.

A dor número um da cliente é overbooking. Toda decisão deste módulo se
subordina a isso — inclusive as que tornam o código mais chato.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.models.booking import AlteracaoPresenca, Booking, OrigemReserva, StatusReserva
from app.models.session import Session, StatusSessao
from app.models.user import User

SEM_VAGA = "Este horário já está com a turma completa."


class SemVagaError(HTTPException):
    """409, não 500. A recepção precisa entender o que aconteceu."""

    def __init__(self, detail: str = SEM_VAGA) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _travar_sessao(db: DbSession, session_id: int) -> Session:
    """Carrega a sessão com FOR UPDATE.

    A trava serializa as recepcionistas que disputam a última vaga, para que a
    segunda ESPERE em vez de tomar erro. O índice único de posição continua
    sendo a garantia final — a trava só torna o caminho feliz mais frequente.
    """
    sessao = db.execute(
        select(Session).where(Session.id == session_id).with_for_update()
    ).scalar_one_or_none()

    if sessao is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")
    if sessao.status is StatusSessao.CANCELADA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta sessão foi cancelada e não aceita reservas.",
        )
    return sessao


def posicoes_ocupadas(db: DbSession, session_id: int) -> set[int]:
    """Posições em uso. Canceladas não entram — vaga cancelada é vaga livre."""
    linhas = db.execute(
        select(Booking.posicao).where(
            Booking.session_id == session_id,
            Booking.status != StatusReserva.CANCELADA,
        )
    ).scalars()
    return set(linhas)


def vagas_livres(db: DbSession, sessao: Session) -> int:
    return sessao.capacidade - len(posicoes_ocupadas(db, sessao.id))


def _proxima_posicao(db: DbSession, sessao: Session) -> int:
    """Menor posição livre da turma, ou erro se não houver.

    Reaproveita buraco deixado por cancelamento em vez de sempre incrementar:
    é o que faz a vaga liberada voltar ao pool de verdade.
    """
    ocupadas = posicoes_ocupadas(db, sessao.id)
    for posicao in range(1, sessao.capacidade + 1):
        if posicao not in ocupadas:
            return posicao
    raise SemVagaError()


def _garantir_paciente_livre(db: DbSession, session_id: int, patient_id: int) -> None:
    ja_esta = db.execute(
        select(Booking).where(
            Booking.session_id == session_id,
            Booking.patient_id == patient_id,
            Booking.status != StatusReserva.CANCELADA,
        )
    ).scalar_one_or_none()
    if ja_esta is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este paciente já está reservado neste horário.",
        )


def criar(
    db: DbSession,
    *,
    session_id: int,
    patient_id: int,
    criado_por_id: int,
    origem: OrigemReserva = OrigemReserva.AVULSA,
    package_id: int | None = None,
    enrollment_id: int | None = None,
    substitui_booking_id: int | None = None,
) -> Booking:
    """Cria uma reserva respeitando a capacidade.

    REPOSIÇÃO NÃO TEM EXCEÇÃO. Passa por este mesmo caminho, ocupa posição
    como qualquer outra e é recusada quando a turma está cheia. Não existe
    "encaixe" — é a regra que resolve a dor principal da cliente.
    """
    sessao = _travar_sessao(db, session_id)
    _garantir_paciente_livre(db, session_id, patient_id)

    reserva = Booking(
        session_id=session_id,
        patient_id=patient_id,
        package_id=package_id,
        enrollment_id=enrollment_id,
        posicao=_proxima_posicao(db, sessao),
        # Cópia do momento da marcação — sustenta o CHECK que impede posição
        # acima da capacidade mesmo se a aplicação errar.
        capacidade_sessao=sessao.capacidade,
        origem=origem,
        status=StatusReserva.AGENDADA,
        substitui_booking_id=substitui_booking_id,
        criado_por_id=criado_por_id,
    )
    db.add(reserva)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        # Vários índices únicos protegem esta tabela. Traduzir todos como
        # "turma completa" mandaria a recepção procurar vaga quando o
        # problema é outro — mensagem errada custa tempo no balcão.
        raise _erro_de_integridade(exc) from exc

    return reserva


#: Índice único -> mensagem que explica o que realmente aconteceu.
_MENSAGEM_POR_INDICE = {
    "ix_bookings_posicao_unica": SEM_VAGA,
    "ix_bookings_paciente_unico_na_sessao": ("Este paciente já está reservado neste horário."),
    "ix_bookings_substitui_unico": (
        "Esta falta já foi reposta. Cada falta dá direito a uma reposição."
    ),
    "ix_bookings_matricula_por_sessao": ("Esta matrícula já tem reserva nesta sessão."),
}


def _erro_de_integridade(exc: IntegrityError) -> HTTPException:
    texto = str(exc.orig) if exc.orig is not None else str(exc)
    for indice, mensagem in _MENSAGEM_POR_INDICE.items():
        if indice in texto:
            return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=mensagem)
    return SemVagaError()


def buscar(db: DbSession, booking_id: int) -> Booking:
    reserva = db.get(Booking, booking_id)
    if reserva is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva não encontrada")
    return reserva


def cancelar(
    db: DbSession, booking_id: int, *, motivo: str | None = None, com_aviso: bool = False
) -> Booking:
    """Cancela e LIBERA A VAGA.

    Não há prazo de antecedência, e cancelar nunca vira falta sozinho — a
    regra das 24h era premissa do time, descartada (docs/premissas.md, P4).
    Quem classifica falta é a recepção.

    O valor do aviso antecipado é operacional: a posição sai do índice parcial
    e volta ao pool na mesma transação, podendo receber uma reposição.

    `com_aviso` é o paciente que avisou que não vem: dá direito a repor
    (docs/premissas.md, P5). Sem ele, é só uma reserva desfeita.
    """
    reserva = buscar(db, booking_id)

    if reserva.status is StatusReserva.CANCELADA:
        return reserva
    if reserva.status in (StatusReserva.PRESENTE, StatusReserva.FALTA):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta reserva já teve a presença registrada e não pode ser cancelada.",
        )

    reserva.status = StatusReserva.CANCELADA
    reserva.cancelado_em = datetime.now(UTC)
    reserva.motivo_cancelamento = motivo
    reserva.cancelado_com_aviso = com_aviso
    db.flush()
    return reserva


def confirmar(db: DbSession, booking_id: int) -> Booking:
    """Paciente confirmou que vem. Eixo de presença, não de pagamento."""
    reserva = buscar(db, booking_id)
    if reserva.status is not StatusReserva.AGENDADA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só uma reserva agendada pode ser confirmada.",
        )
    reserva.status = StatusReserva.CONFIRMADA
    db.flush()
    return reserva


#: Status que encerram o eixo de presença. Corrigir é sair de um para o outro.
_REGISTRADOS = (StatusReserva.PRESENTE, StatusReserva.FALTA)


def _reposicao_ativa(db: DbSession, booking_id: int) -> Booking | None:
    return db.execute(
        select(Booking).where(
            Booking.substitui_booking_id == booking_id,
            Booking.origem == OrigemReserva.REPOSICAO,
            Booking.status != StatusReserva.CANCELADA,
        )
    ).scalar_one_or_none()


def _garantir_correcao_permitida(
    db: DbSession, reserva: Booking, *, novo_status: StatusReserva, justificada: bool
) -> None:
    """Falta já reposta não pode perder o direito que gerou.

    Corrigir "faltou" para "presente" (ou tirar a justificativa) com a
    reposição já marcada deixaria uma reposição sem falta que a justifique —
    uma aula a mais, de graça, ocupando vaga. A recepção cancela a reposição
    antes, de propósito: é uma decisão, não um efeito colateral.
    """
    if reserva.status is not StatusReserva.FALTA:
        return
    if novo_status is StatusReserva.FALTA and justificada:
        return
    if _reposicao_ativa(db, reserva.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Esta falta já foi reposta. Cancele a reposição antes de corrigir o registro."),
        )


def _mudar_presenca(
    db: DbSession,
    reserva: Booking,
    *,
    novo_status: StatusReserva,
    justificada: bool,
    motivo: str | None,
    alterado_por_id: int | None,
) -> Booking:
    """Aplica a mudança e grava o histórico, se algo de fato mudou.

    `alterado_por_id` é obrigatório na API. Só fica de fora em chamadas
    internas (seed, testes), que não são registro de ninguém.
    """
    mudou = reserva.status is not novo_status or reserva.justificada is not justificada
    anterior = reserva.status

    reserva.status = novo_status
    reserva.justificada = justificada
    reserva.motivo_justificativa = motivo
    if mudou and alterado_por_id is not None:
        db.add(
            AlteracaoPresenca(
                booking_id=reserva.id,
                status_anterior=anterior,
                status_novo=novo_status,
                justificada=justificada,
                alterado_por_id=alterado_por_id,
            )
        )
    db.flush()
    return reserva


def registrar_presenca(
    db: DbSession, booking_id: int, *, alterado_por_id: int | None = None
) -> Booking:
    """Marca presença. Também corrige uma falta registrada por engano."""
    reserva = buscar(db, booking_id)
    if reserva.status is StatusReserva.CANCELADA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reserva cancelada não recebe presença.",
        )
    _garantir_correcao_permitida(db, reserva, novo_status=StatusReserva.PRESENTE, justificada=False)
    return _mudar_presenca(
        db,
        reserva,
        novo_status=StatusReserva.PRESENTE,
        justificada=False,
        motivo=None,
        alterado_por_id=alterado_por_id,
    )


def registrar_falta(
    db: DbSession,
    booking_id: int,
    *,
    justificada: bool = False,
    motivo: str | None = None,
    alterado_por_id: int | None = None,
) -> Booking:
    """Marca falta. Quem julga se é justificada é a RECEPÇÃO.

    O sistema nunca infere: não há prazo, relógio nem heurística que decida
    isso. É o critério real da cliente (docs/premissas.md, P4 e P5).

    A falta CONTINUA ocupando a vaga daquele horário — a aula aconteceu com
    aquele lugar reservado. O que a falta gera é direito a repor em OUTRO
    horário, que ocupará outra vaga.
    """
    reserva = buscar(db, booking_id)
    if reserva.status is StatusReserva.CANCELADA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reserva cancelada não recebe falta — ela já liberou a vaga.",
        )
    _garantir_correcao_permitida(
        db, reserva, novo_status=StatusReserva.FALTA, justificada=justificada
    )
    return _mudar_presenca(
        db,
        reserva,
        novo_status=StatusReserva.FALTA,
        justificada=justificada,
        motivo=motivo,
        alterado_por_id=alterado_por_id,
    )


def limpar_presenca(db: DbSession, booking_id: int, *, alterado_por_id: int) -> Booking:
    """Desfaz o registro: marcou em quem não devia, volta a "sem registro".

    Volta ao status que a reserva tinha antes do primeiro registro
    (agendada ou confirmada), lido do histórico.
    """
    reserva = buscar(db, booking_id)
    if reserva.status not in _REGISTRADOS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta reserva não tem presença nem falta registrada.",
        )
    anterior = db.execute(
        select(AlteracaoPresenca.status_anterior)
        .where(
            AlteracaoPresenca.booking_id == reserva.id,
            AlteracaoPresenca.status_anterior.in_(
                (StatusReserva.AGENDADA, StatusReserva.CONFIRMADA)
            ),
        )
        .order_by(AlteracaoPresenca.alterado_em.desc(), AlteracaoPresenca.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    destino = anterior or StatusReserva.AGENDADA

    _garantir_correcao_permitida(db, reserva, novo_status=destino, justificada=False)
    return _mudar_presenca(
        db,
        reserva,
        novo_status=destino,
        justificada=False,
        motivo=None,
        alterado_por_id=alterado_por_id,
    )


@dataclass
class UltimoRegistro:
    por: str
    em: datetime


def ultimos_registros(db: DbSession, booking_ids: list[int]) -> dict[int, UltimoRegistro]:
    """Quem registrou a presença de cada reserva por último, numa consulta só."""
    if not booking_ids:
        return {}
    linhas = db.execute(
        select(AlteracaoPresenca.booking_id, User.nome, AlteracaoPresenca.alterado_em)
        .join(User, User.id == AlteracaoPresenca.alterado_por_id)
        .where(AlteracaoPresenca.booking_id.in_(booking_ids))
        .order_by(
            AlteracaoPresenca.booking_id,
            AlteracaoPresenca.alterado_em.desc(),
            AlteracaoPresenca.id.desc(),
        )
        .distinct(AlteracaoPresenca.booking_id)
    ).all()
    return {bid: UltimoRegistro(por=nome, em=em) for bid, nome, em in linhas}


def remarcar(
    db: DbSession,
    booking_id: int,
    *,
    nova_session_id: int,
    criado_por_id: int,
    origem: OrigemReserva = OrigemReserva.REMARCACAO,
) -> Booking:
    """Move o paciente para outro horário, mantendo o vínculo de origem.

    A reserva nova passa pela MESMA verificação de capacidade. Remarcar não é
    atalho para furar turma cheia.

    A original é cancelada, o que devolve a vaga dela ao pool — é o
    comportamento certo: quem sai de um horário libera lugar nele.
    """
    original = buscar(db, booking_id)

    if original.status is StatusReserva.CANCELADA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reserva cancelada não pode ser remarcada.",
        )
    if nova_session_id == original.session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova sessão precisa ser diferente da atual.",
        )

    # Cria a nova ANTES de cancelar a antiga: se não houver vaga no destino, o
    # paciente não pode ficar sem nenhuma das duas.
    nova = criar(
        db,
        session_id=nova_session_id,
        patient_id=original.patient_id,
        criado_por_id=criado_por_id,
        origem=origem,
        package_id=original.package_id,
        substitui_booking_id=original.id,
    )

    original.status = StatusReserva.CANCELADA
    original.cancelado_em = datetime.now(UTC)
    original.motivo_cancelamento = f"Remarcado para a sessão {nova_session_id}"
    db.flush()
    return nova


def contar_ocupacao(db: DbSession, session_ids: list[int]) -> dict[int, int]:
    """Ocupação de várias sessões numa consulta só, para a grade da semana."""
    if not session_ids:
        return {}
    linhas = db.execute(
        select(Booking.session_id, func.count())
        .where(
            Booking.session_id.in_(session_ids),
            Booking.status != StatusReserva.CANCELADA,
        )
        .group_by(Booking.session_id)
    ).all()
    return {sid: total for sid, total in linhas}
