from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session as DbSession

from app.core.deps import CurrentUser, require_papel
from app.db.session import get_db
from app.models.user import Papel
from app.schemas.agenda import (
    BookingCancel,
    BookingCreate,
    BookingFalta,
    BookingRead,
    BookingRemarcar,
    DiaDaGrade,
    GradeSemanal,
    ReservaNaGrade,
    SessaoNaGrade,
    SessionCreate,
)
from app.services import booking_service, schedule_service, session_service
from app.services.schedule_service import FUSO

router = APIRouter(tags=["agenda"])

Db = Annotated[DbSession, Depends(get_db)]

# Ler a agenda é dos três perfis — é a única tela do instrutor.
LEITURA = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO, Papel.INSTRUTOR))
# Escrever é da recepção e da proprietária. O instrutor é SOMENTE LEITURA
# nesta entrega (CLAUDE.md); quem registra presença e falta é a recepção.
ESCRITA = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))


def _para_grade(item: schedule_service.SessaoNaGrade) -> SessaoNaGrade:
    local = item.sessao.inicia_em.astimezone(FUSO)
    return SessaoNaGrade(
        id=item.sessao.id,
        service_id=item.sessao.service_id,
        servico_nome=item.servico.nome,
        servico_cor=item.servico.cor,
        professional_id=item.sessao.professional_id,
        instrutor_nome=item.instrutor.nome,
        inicia_em=item.sessao.inicia_em,
        termina_em=item.sessao.termina_em,
        hora=f"{local.hour:02d}:00",
        dia=local.date(),
        capacidade=item.sessao.capacidade,
        ocupadas=item.ocupadas,
        vagas=item.sessao.capacidade - item.ocupadas,
        lotada=item.ocupadas >= item.sessao.capacidade,
        status=item.sessao.status,
        reservas=[
            ReservaNaGrade(
                id=reserva.id,
                patient_id=paciente.id,
                paciente_nome=paciente.nome_completo,
                posicao=reserva.posicao,
                status=reserva.status,
                origem=reserva.origem,
                justificada=reserva.justificada,
            )
            for reserva, paciente in item.reservas
        ],
    )


@router.get("/agenda/semana", response_model=GradeSemanal, dependencies=[LEITURA])
def grade_semanal(
    db: Db,
    referencia: Annotated[date | None, Query(description="Qualquer dia da semana")] = None,
) -> GradeSemanal:
    """Grade da semana, seguindo o print.

    Os horários devolvidos já excluem a pausa e o que está fora da janela do
    dia: a API nunca oferece um horário que o studio não atende.
    """
    inicio = schedule_service.inicio_da_semana(referencia or date.today())
    janelas = schedule_service.janela_da_semana(db, inicio)
    fim = janelas[-1].dia

    return GradeSemanal(
        inicio=inicio,
        fim=fim,
        dias=[
            DiaDaGrade(
                data=j.dia,
                dia_semana=(j.dia.weekday() + 1) % 7,
                aberto=j.aberto,
                horas=[f"{h.hour:02d}:00" for h in j.horas],
                hora_abertura=j.hora_abertura,
                hora_fechamento=j.hora_fechamento,
                pausa_inicio=j.pausa_inicio,
                pausa_fim=j.pausa_fim,
            )
            for j in janelas
        ],
        sessoes=[_para_grade(s) for s in schedule_service.sessoes_da_semana(db, inicio, fim)],
    )


@router.get("/agenda/vagas", response_model=list[SessaoNaGrade], dependencies=[LEITURA])
def sessoes_com_vaga(
    db: Db,
    de: date,
    ate: date,
    service_id: int | None = None,
    excluir_patient_id: int | None = None,
) -> list[SessaoNaGrade]:
    """Turmas que ainda comportam mais um paciente.

    É o que a recepção consulta ANTES de oferecer uma reposição, para não
    prometer horário que não existe. Devolve lista vazia quando não há vaga —
    e a tela precisa dizer isso explicitamente, sem oferecer saída.

    Só considera sessões já materializadas. Ver a explicação da armadilha em
    `schedule_service.sessoes_com_vaga`.
    """
    itens = schedule_service.sessoes_com_vaga(
        db, de=de, ate=ate, service_id=service_id, excluir_patient_id=excluir_patient_id
    )
    return [_para_grade(i) for i in itens]


@router.post(
    "/sessions",
    response_model=SessaoNaGrade,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ESCRITA],
)
def criar_sessao(dados: SessionCreate, db: Db) -> SessaoNaGrade:
    sessao = session_service.criar(
        db,
        service_id=dados.service_id,
        professional_id=dados.professional_id,
        inicia_em=dados.inicia_em,
        capacidade=dados.capacidade,
        observacoes=dados.observacoes,
    )
    db.commit()
    local = sessao.inicia_em.astimezone(FUSO)
    itens = schedule_service.sessoes_da_semana(db, local.date(), local.date())
    encontrada = next(i for i in itens if i.sessao.id == sessao.id)
    return _para_grade(encontrada)


@router.delete("/sessions/{session_id}", dependencies=[ESCRITA])
def cancelar_sessao(session_id: int, dados: BookingCancel, db: Db) -> dict[str, str]:
    """Cancela a turma e todas as reservas dela."""
    session_service.cancelar(db, session_id, motivo=dados.motivo)
    db.commit()
    return {"detail": "Turma cancelada e reservas liberadas."}


@router.post(
    "/bookings",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ESCRITA],
)
def criar_reserva(dados: BookingCreate, db: Db, usuario: CurrentUser) -> BookingRead:
    """Reserva um paciente numa turma.

    Vale para reserva avulsa E reposição — reposição não tem exceção nem
    "encaixe". Devolve 409 quando a turma está cheia.
    """
    reserva = booking_service.criar(
        db,
        session_id=dados.session_id,
        patient_id=dados.patient_id,
        criado_por_id=usuario.id,
        origem=dados.origem,
        package_id=dados.package_id,
        substitui_booking_id=dados.substitui_booking_id,
    )
    db.commit()
    return BookingRead.model_validate(reserva)


@router.post("/bookings/{booking_id}/cancelar", response_model=BookingRead, dependencies=[ESCRITA])
def cancelar_reserva(booking_id: int, dados: BookingCancel, db: Db) -> BookingRead:
    """Cancela e libera a vaga para outra pessoa — inclusive para reposição."""
    reserva = booking_service.cancelar(db, booking_id, motivo=dados.motivo)
    db.commit()
    return BookingRead.model_validate(reserva)


@router.post("/bookings/{booking_id}/confirmar", response_model=BookingRead, dependencies=[ESCRITA])
def confirmar_reserva(booking_id: int, db: Db) -> BookingRead:
    reserva = booking_service.confirmar(db, booking_id)
    db.commit()
    return BookingRead.model_validate(reserva)


@router.post("/bookings/{booking_id}/presenca", response_model=BookingRead, dependencies=[ESCRITA])
def registrar_presenca(booking_id: int, db: Db) -> BookingRead:
    reserva = booking_service.registrar_presenca(db, booking_id)
    db.commit()
    return BookingRead.model_validate(reserva)


@router.post("/bookings/{booking_id}/falta", response_model=BookingRead, dependencies=[ESCRITA])
def registrar_falta(booking_id: int, dados: BookingFalta, db: Db) -> BookingRead:
    """Marca falta. A recepção decide se é justificada — o sistema não infere."""
    reserva = booking_service.registrar_falta(
        db, booking_id, justificada=dados.justificada, motivo=dados.motivo
    )
    db.commit()
    return BookingRead.model_validate(reserva)


@router.post("/bookings/{booking_id}/remarcar", response_model=BookingRead, dependencies=[ESCRITA])
def remarcar_reserva(
    booking_id: int, dados: BookingRemarcar, db: Db, usuario: CurrentUser
) -> BookingRead:
    """Move para outro horário, mantendo o vínculo com a reserva de origem.

    A reserva nova passa pela mesma checagem de capacidade.
    """
    nova = booking_service.remarcar(
        db,
        booking_id,
        nova_session_id=dados.nova_session_id,
        criado_por_id=usuario.id,
        origem=dados.origem,
    )
    db.commit()
    return BookingRead.model_validate(nova)
