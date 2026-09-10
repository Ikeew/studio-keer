"""Regras de reserva. É aqui que a capacidade é respeitada.

A dor número um da cliente é overbooking. Toda decisão deste módulo se
subordina a isso — inclusive as que tornam o código mais chato.
"""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.models.booking import Booking, OrigemReserva, StatusReserva
from app.models.session import Session, StatusSessao

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
        # O índice único de posição estourou: alguém pegou a vaga entre a
        # leitura e a escrita. Vira 409 com texto claro, nunca 500.
        raise SemVagaError() from exc

    return reserva


def buscar(db: DbSession, booking_id: int) -> Booking:
    reserva = db.get(Booking, booking_id)
    if reserva is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva não encontrada")
    return reserva


def cancelar(db: DbSession, booking_id: int, *, motivo: str | None = None) -> Booking:
    """Cancela e LIBERA A VAGA.

    Não há prazo de antecedência, e cancelar nunca vira falta sozinho — a
    regra das 24h era premissa do time, descartada (docs/premissas.md, P4).
    Quem classifica falta é a recepção.

    O valor do aviso antecipado é operacional: a posição sai do índice parcial
    e volta ao pool na mesma transação, podendo receber uma reposição.
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


def registrar_presenca(db: DbSession, booking_id: int) -> Booking:
    reserva = buscar(db, booking_id)
    if reserva.status is StatusReserva.CANCELADA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reserva cancelada não recebe presença.",
        )
    reserva.status = StatusReserva.PRESENTE
    db.flush()
    return reserva


def registrar_falta(
    db: DbSession,
    booking_id: int,
    *,
    justificada: bool = False,
    motivo: str | None = None,
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
    reserva.status = StatusReserva.FALTA
    reserva.justificada = justificada
    reserva.motivo_justificativa = motivo
    db.flush()
    return reserva


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
