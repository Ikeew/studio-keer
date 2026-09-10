from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.cpf import normalizar_cpf
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate


def _por_cpf(db: Session, cpf: str, excluindo_id: int | None = None) -> Patient | None:
    stmt = select(Patient).where(Patient.cpf == cpf)
    if excluindo_id is not None:
        stmt = stmt.where(Patient.id != excluindo_id)
    return db.execute(stmt).scalar_one_or_none()


def _garantir_cpf_livre(db: Session, cpf: str | None, excluindo_id: int | None = None) -> None:
    """CPF duplicado é erro de negócio, não de banco.

    Deixar o índice único estourar devolveria 500 com mensagem do Postgres.
    Aqui vira 409 com texto que a recepção entende. A constraint continua no
    banco como rede de segurança contra concorrência.
    """
    if cpf is None:
        return
    existente = _por_cpf(db, cpf, excluindo_id)
    if existente is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um paciente cadastrado com este CPF: {existente.nome_completo}",
        )


def buscar(db: Session, patient_id: int) -> Patient:
    paciente = db.get(Patient, patient_id)
    if paciente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado")
    return paciente


def _stmt_listagem(termo: str | None, incluir_inativos: bool) -> Select[tuple[Patient]]:
    stmt = select(Patient)
    if not incluir_inativos:
        stmt = stmt.where(Patient.ativo.is_(True))

    if termo:
        limpo = termo.strip()
        # Busca por nome OU telefone. Se o termo parece um documento/telefone,
        # compara só os dígitos: a recepção digita "(11) 98765-4321" e o banco
        # guarda "11987654321".
        digitos = normalizar_cpf(limpo)
        condicoes = [Patient.nome_completo.ilike(f"%{limpo}%")]
        if digitos:
            condicoes.append(
                func.regexp_replace(Patient.telefone, r"\D", "", "g").like(f"%{digitos}%")
            )
            condicoes.append(Patient.cpf.like(f"%{digitos}%"))
        stmt = stmt.where(or_(*condicoes))

    return stmt


def listar(
    db: Session,
    *,
    termo: str | None = None,
    pagina: int = 1,
    tamanho: int = 20,
    incluir_inativos: bool = False,
) -> tuple[list[Patient], int]:
    """Lista paginada. Devolve (itens, total)."""
    stmt = _stmt_listagem(termo, incluir_inativos)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    itens = (
        db.execute(
            stmt.order_by(Patient.nome_completo).offset((pagina - 1) * tamanho).limit(tamanho)
        )
        .scalars()
        .all()
    )
    return list(itens), total


def criar(db: Session, dados: PatientCreate) -> Patient:
    _garantir_cpf_livre(db, dados.cpf)

    paciente = Patient(**dados.model_dump())
    # A data do consentimento é registrada pelo sistema, não enviada pelo
    # cliente: sem ela o consentimento não é comprovável perante a LGPD.
    if dados.consentimento_lgpd:
        paciente.consentimento_em = date.today()

    db.add(paciente)
    db.flush()
    return paciente


def atualizar(db: Session, patient_id: int, dados: PatientUpdate) -> Patient:
    paciente = buscar(db, patient_id)
    alteracoes = dados.model_dump(exclude_unset=True)

    if "cpf" in alteracoes:
        _garantir_cpf_livre(db, alteracoes["cpf"], excluindo_id=patient_id)

    # Consentimento retirado limpa a data; consentimento novo carimba hoje.
    if "consentimento_lgpd" in alteracoes:
        novo = alteracoes["consentimento_lgpd"]
        if novo and not paciente.consentimento_lgpd:
            paciente.consentimento_em = date.today()
        elif not novo:
            paciente.consentimento_em = None

    for campo, valor in alteracoes.items():
        setattr(paciente, campo, valor)

    db.flush()
    return paciente


def desativar(db: Session, patient_id: int) -> Patient:
    """Exclusão lógica.

    Apagar de verdade levaria junto o histórico de agendamentos e pagamentos,
    que precisa sobreviver ao desligamento do paciente.
    """
    paciente = buscar(db, patient_id)
    paciente.ativo = False
    db.flush()
    return paciente


def reativar(db: Session, patient_id: int) -> Patient:
    paciente = buscar(db, patient_id)
    paciente.ativo = True
    db.flush()
    return paciente
