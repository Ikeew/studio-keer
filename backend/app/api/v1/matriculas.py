from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.deps import CurrentUser, require_papel
from app.db.session import get_db
from app.models.enrollment import Enrollment
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import Papel, User
from app.schemas.matricula import (
    BlackoutCreate,
    BlackoutRead,
    EnrollmentCreate,
    EnrollmentRead,
    FaltaPendenteRead,
    HorarioFixo,
    MotivoOpcional,
    ResultadoGeracaoRead,
    SaudeDaGradeRead,
    SessaoAfetada,
)
from app.services import booking_service, enrollment_service, reposicao_service

router = APIRouter(tags=["matrículas"])

Db = Annotated[DbSession, Depends(get_db)]

ESCRITA = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))
# Reposições pendentes é leitura operacional da recepção e da proprietária.
LEITURA = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))


def _para_leitura(db: DbSession, m: Enrollment) -> EnrollmentRead:
    paciente = db.get(Patient, m.patient_id)
    servico = db.get(Service, m.service_id)
    instrutor = db.get(User, m.professional_id)
    return EnrollmentRead(
        id=m.id,
        patient_id=m.patient_id,
        paciente_nome=paciente.nome_completo if paciente else "",
        service_id=m.service_id,
        servico_nome=servico.nome if servico else "",
        professional_id=m.professional_id,
        instrutor_nome=instrutor.nome if instrutor else "",
        status=m.status,
        vigencia_inicio=m.vigencia_inicio,
        vigencia_fim=m.vigencia_fim,
        valor_mensal_centavos=m.valor_mensal_centavos,
        dia_vencimento=m.dia_vencimento,
        horarios=[
            HorarioFixo(dia_semana=h.dia_semana, hora_inicio=h.hora_inicio)
            for h in sorted(m.horarios, key=lambda h: (h.dia_semana, h.hora_inicio))
        ],
    )


@router.get("/enrollments", response_model=list[EnrollmentRead], dependencies=[LEITURA])
def listar(db: Db, patient_id: int | None = None) -> list[EnrollmentRead]:
    stmt = select(Enrollment).order_by(Enrollment.id)
    if patient_id is not None:
        stmt = stmt.where(Enrollment.patient_id == patient_id)
    return [_para_leitura(db, m) for m in db.execute(stmt).scalars().unique().all()]


@router.post(
    "/enrollments",
    response_model=EnrollmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ESCRITA],
)
def criar(dados: EnrollmentCreate, db: Db) -> EnrollmentRead:
    """Cria a matrícula.

    Recusa com 409 se algum dos horários já tiver a turma completa de alunos
    fixos — é o ponto onde nasce o overbooking vendido no balcão.
    """
    matricula = enrollment_service.criar(
        db,
        patient_id=dados.patient_id,
        service_id=dados.service_id,
        professional_id=dados.professional_id,
        vigencia_inicio=dados.vigencia_inicio,
        vigencia_fim=dados.vigencia_fim,
        valor_mensal_centavos=dados.valor_mensal_centavos,
        horarios=[(h.dia_semana, h.hora_inicio) for h in dados.horarios],
    )
    db.commit()
    return _para_leitura(db, matricula)


@router.post(
    "/enrollments/{enrollment_id}/suspender",
    response_model=EnrollmentRead,
    dependencies=[ESCRITA],
)
def suspender(enrollment_id: int, dados: MotivoOpcional, db: Db) -> EnrollmentRead:
    """Suspende e libera as vagas futuras.

    Presença e falta já registradas ficam intactas — são fato consumado.
    """
    enrollment_service.suspender(db, enrollment_id, motivo=dados.motivo)
    db.commit()
    return _para_leitura(db, enrollment_service.buscar(db, enrollment_id))


@router.post(
    "/enrollments/{enrollment_id}/encerrar",
    response_model=EnrollmentRead,
    dependencies=[ESCRITA],
)
def encerrar(enrollment_id: int, dados: MotivoOpcional, db: Db) -> EnrollmentRead:
    enrollment_service.encerrar(db, enrollment_id, motivo=dados.motivo)
    db.commit()
    return _para_leitura(db, enrollment_service.buscar(db, enrollment_id))


@router.post(
    "/enrollments/{enrollment_id}/reativar",
    response_model=ResultadoGeracaoRead,
    dependencies=[ESCRITA],
)
def reativar(enrollment_id: int, db: Db, usuario: CurrentUser) -> ResultadoGeracaoRead:
    """Reativa e regenera a grade.

    A capacidade é reverificada: o lugar pode ter sido vendido enquanto a
    matrícula esteve suspensa.
    """
    resultado = enrollment_service.reativar(db, enrollment_id, criado_por_id=usuario.id)
    db.commit()
    return ResultadoGeracaoRead(**resultado.__dict__)


@router.post(
    "/enrollments/gerar-grade",
    response_model=ResultadoGeracaoRead,
    dependencies=[ESCRITA],
)
def gerar_grade(
    db: Db,
    usuario: CurrentUser,
    enrollment_id: Annotated[int | None, Query()] = None,
) -> ResultadoGeracaoRead:
    """Materializa as sessões e reservas recorrentes até o horizonte.

    Idempotente: rodar de novo não duplica nada, e execução interrompida no
    meio pode ser repetida sem limpeza.
    """
    resultado = enrollment_service.gerar_grade(
        db, criado_por_id=usuario.id, enrollment_id=enrollment_id
    )
    db.commit()
    return ResultadoGeracaoRead(**resultado.__dict__)


@router.get(
    "/agenda/saude-da-grade",
    response_model=SaudeDaGradeRead,
    # O instrutor também lê: se a grade dele esvaziar, ele precisa saber por
    # quê antes de achar que perdeu turmas.
    dependencies=[Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO, Papel.INSTRUTOR))],
)
def saude_da_grade(db: Db) -> SaudeDaGradeRead:
    """Diagnóstico de quanto ainda resta de grade materializada."""
    s = enrollment_service.saude_da_grade(db)
    return SaudeDaGradeRead(
        materializado_ate=s.materializado_ate,
        dias_restantes=s.dias_restantes,
        semanas_restantes=s.semanas_restantes,
        vencida=s.vencida,
        precisa_atualizar=s.precisa_atualizar,
        matriculas_ativas=s.matriculas_ativas,
        semanas_minimas=enrollment_service.SEMANAS_MINIMAS,
    )


@router.post(
    "/blackouts",
    response_model=BlackoutRead,
    status_code=status.HTTP_201_CREATED,
    # Feriado e recesso são decisão da proprietária.
    dependencies=[Depends(require_papel(Papel.ADMIN))],
)
def criar_blackout(dados: BlackoutCreate, db: Db) -> BlackoutRead:
    """Cria o bloqueio e AVISA o que ele conflita — nunca apaga em silêncio.

    Mesmo princípio da redução de capacidade: o sistema não decide sozinho
    cancelar aula que já tem gente marcada.
    """
    blackout, conflito = enrollment_service.criar_blackout(
        db,
        data_inicio=dados.data_inicio,
        data_fim=dados.data_fim,
        motivo=dados.motivo,
    )
    ocupacao = booking_service.contar_ocupacao(db, [s.id for s in conflito.sessoes])
    db.commit()
    return BlackoutRead(
        id=blackout.id,
        data_inicio=blackout.data_inicio,
        data_fim=blackout.data_fim,
        motivo=blackout.motivo,
        sessoes_em_conflito=[
            SessaoAfetada(id=s.id, inicia_em=s.inicia_em, ocupadas=ocupacao.get(s.id, 0))
            for s in conflito.sessoes
        ],
        reservas_em_conflito=conflito.reservas_ativas,
    )


@router.get(
    "/reposicoes-pendentes",
    response_model=list[FaltaPendenteRead],
    dependencies=[LEITURA],
)
def reposicoes_pendentes(db: Db, incluir_vencidas: bool = False) -> list[FaltaPendenteRead]:
    """Faltas que dão direito a repor e ainda não foram repostas.

    Hoje isso vive na cabeça da proprietária. Devolve, para cada falta, quem
    é, de quando, até quando dá para repor, e a janela em que a recepção deve
    procurar vaga.
    """
    pendentes = reposicao_service.listar_pendentes(db, incluir_vencidas=incluir_vencidas)
    saida: list[FaltaPendenteRead] = []
    for p in pendentes:
        de, ate = reposicao_service.periodo_para_oferecer(db, p)
        saida.append(
            FaltaPendenteRead(
                booking_id=p.booking_id,
                patient_id=p.patient_id,
                paciente_nome=p.paciente_nome,
                paciente_telefone=p.paciente_telefone,
                servico_nome=p.servico_nome,
                service_id=p.service_id,
                faltou_em=p.faltou_em,
                justificada=p.justificada,
                motivo=p.motivo,
                repor_ate=p.repor_ate,
                dias_restantes=p.dias_restantes,
                procurar_de=de,
                procurar_ate=ate,
            )
        )
    return saida
