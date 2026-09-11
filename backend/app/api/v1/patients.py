from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_papel
from app.db.session import get_db
from app.models.user import Papel
from app.schemas.patient import (
    PaginaDePacientes,
    PatientCreate,
    PatientRead,
    PatientUpdate,
)
from app.services import patient_service

# Recepção e admin operam o cadastro. O instrutor não vê a ficha do paciente:
# ele só lê a agenda do dia. Ver CLAUDE.md.
OPERADORES = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))

router = APIRouter(prefix="/patients", tags=["pacientes"], dependencies=[OPERADORES])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=PaginaDePacientes)
def listar(
    db: DbSession,
    busca: Annotated[
        str | None,
        # A busca cai num índice trigram. Um termo de dez mil caracteres faz o
        # Postgres trabalhar de verdade para devolver nada — ninguém procura
        # paciente por um parágrafo. Cem cobre o nome mais longo com folga.
        Query(description="Nome, telefone ou CPF", max_length=100),
    ] = None,
    # O OFFSET cresce com o número da página: `pagina=999999999` manda o banco
    # percorrer e descartar linhas só para devolver vazio. Dez mil páginas são
    # mais do que a base da cliente vai ter, e limitam o pior caso.
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 20,
    incluir_inativos: bool = False,
) -> PaginaDePacientes:
    itens, total = patient_service.listar(
        db,
        termo=busca,
        pagina=pagina,
        tamanho=tamanho,
        incluir_inativos=incluir_inativos,
    )
    return PaginaDePacientes(
        itens=[PatientRead.model_validate(p) for p in itens],
        total=total,
        pagina=pagina,
        tamanho=tamanho,
    )


@router.get("/{patient_id}", response_model=PatientRead)
def obter(patient_id: int, db: DbSession) -> PatientRead:
    return PatientRead.model_validate(patient_service.buscar(db, patient_id))


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def criar(dados: PatientCreate, db: DbSession) -> PatientRead:
    paciente = patient_service.criar(db, dados)
    db.commit()
    return PatientRead.model_validate(paciente)


@router.patch("/{patient_id}", response_model=PatientRead)
def atualizar(patient_id: int, dados: PatientUpdate, db: DbSession) -> PatientRead:
    paciente = patient_service.atualizar(db, patient_id, dados)
    db.commit()
    return PatientRead.model_validate(paciente)


@router.delete("/{patient_id}", response_model=PatientRead)
def desativar(patient_id: int, db: DbSession) -> PatientRead:
    """Exclusão lógica — o histórico do paciente precisa sobreviver."""
    paciente = patient_service.desativar(db, patient_id)
    db.commit()
    return PatientRead.model_validate(paciente)


@router.post("/{patient_id}/reativar", response_model=PatientRead)
def reativar(patient_id: int, db: DbSession) -> PatientRead:
    paciente = patient_service.reativar(db, patient_id)
    db.commit()
    return PatientRead.model_validate(paciente)
