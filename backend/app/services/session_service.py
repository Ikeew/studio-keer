from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.models.booking import Booking, StatusReserva
from app.models.service import Service
from app.models.session import Session, StatusSessao
from app.models.user import Papel, User
from app.services import schedule_service


def buscar(db: DbSession, session_id: int) -> Session:
    sessao = db.get(Session, session_id)
    if sessao is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")
    return sessao


def criar(
    db: DbSession,
    *,
    service_id: int,
    professional_id: int,
    inicia_em: datetime,
    capacidade: int | None = None,
    observacoes: str | None = None,
) -> Session:
    """Cria uma turma num horário.

    Recusa horário que o studio não atende. Sem isso, a recepção poderia criar
    uma turma às 13:00 (dentro da pausa) e a grade teria de escondê-la — um
    dado que existe e não aparece é pior que um dado recusado.
    """
    servico = db.get(Service, service_id)
    if servico is None or not servico.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serviço não encontrado")

    instrutor = db.get(User, professional_id)
    if instrutor is None or not instrutor.ativo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instrutor não encontrado"
        )
    if instrutor.papel not in (Papel.INSTRUTOR, Papel.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Só instrutor ou proprietária pode ministrar uma turma.",
        )

    if not schedule_service.horario_e_atendivel(db, inicia_em):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O studio não atende neste horário. "
                "Verifique o dia da semana, a janela de funcionamento e a pausa."
            ),
        )

    sessao = Session(
        service_id=service_id,
        professional_id=professional_id,
        inicia_em=inicia_em,
        termina_em=inicia_em + timedelta(minutes=servico.duracao_min),
        # Cópia do serviço, com override opcional.
        capacidade=capacidade if capacidade is not None else servico.capacidade_padrao,
        observacoes=observacoes,
    )
    db.add(sessao)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este instrutor já tem uma turma começando neste horário.",
        ) from exc
    return sessao


def cancelar(db: DbSession, session_id: int, *, motivo: str | None = None) -> Session:
    """Cancela a turma inteira, e com ela todas as reservas.

    As reservas são canceladas explicitamente, e não deixadas órfãs: uma
    reserva ativa numa sessão cancelada apareceria no histórico do paciente
    como aula que ele deveria ter tido.
    """
    sessao = buscar(db, session_id)
    if sessao.status is StatusSessao.CANCELADA:
        return sessao

    reservas = (
        db.execute(
            select(Booking).where(
                Booking.session_id == session_id,
                Booking.status != StatusReserva.CANCELADA,
            )
        )
        .scalars()
        .all()
    )
    agora = datetime.now(tz=sessao.inicia_em.tzinfo)
    for reserva in reservas:
        reserva.status = StatusReserva.CANCELADA
        reserva.cancelado_em = agora
        reserva.motivo_cancelamento = motivo or "Turma cancelada"

    sessao.status = StatusSessao.CANCELADA
    sessao.observacoes = motivo or sessao.observacoes
    db.flush()
    return sessao


def sessoes_acima_da_capacidade(
    db: DbSession, service_id: int, nova_capacidade: int
) -> list[Session]:
    """Sessões futuras que ficariam acima de uma capacidade menor.

    Serve para AVISAR ao reduzir a capacidade de um serviço. O sistema não
    remove reserva nenhuma: escolher quem perde a vaga é decisão humana.
    """
    from app.services.booking_service import contar_ocupacao

    hoje = date.today()
    futuras = (
        db.execute(
            select(Session).where(
                Session.service_id == service_id,
                Session.status != StatusSessao.CANCELADA,
                Session.inicia_em
                >= datetime.combine(hoje, datetime.min.time()).astimezone(schedule_service.FUSO),
            )
        )
        .scalars()
        .all()
    )
    ocupacao = contar_ocupacao(db, [s.id for s in futuras])
    return [s for s in futuras if ocupacao.get(s.id, 0) > nova_capacidade]
