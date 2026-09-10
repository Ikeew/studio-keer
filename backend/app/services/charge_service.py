"""Cobranças: geração, baixa de pagamento e totais.

Presença e pagamento são eixos independentes. Nada aqui olha para o status de
uma reserva, e nada em `booking_service` olha para o status de uma cobrança.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.models.charge import (
    Charge,
    FormaPagamento,
    StatusCobranca,
    TipoCobranca,
)
from app.models.enrollment import Enrollment, StatusMatricula
from app.models.package import Package
from app.models.patient import Patient
from app.services import ciclo_service


def vencida_sql() -> object:
    """Condição SQL de "vencido".

    `vencido` NUNCA é coluna: é `pendente AND vencimento < hoje`. Um status
    gravado exigiria um job à meia-noite e mentiria até ele rodar.
    """
    return and_(Charge.status == StatusCobranca.PENDENTE, Charge.vencimento < date.today())


def esta_vencida(cobranca: Charge, hoje: date | None = None) -> bool:
    return cobranca.status is StatusCobranca.PENDENTE and cobranca.vencimento < (
        hoje or date.today()
    )


@dataclass
class ResultadoFaturamento:
    criadas: int = 0
    ja_existentes: int = 0
    matriculas: int = 0
    detalhes: list[str] = field(default_factory=list)


def gerar_mensalidades(
    db: DbSession,
    *,
    ate: date | None = None,
    enrollment_id: int | None = None,
) -> ResultadoFaturamento:
    """Gera as mensalidades devidas até `ate`.

    IDEMPOTENTE, como o gerador da grade: a checagem em Python evita o erro
    no caminho feliz, e o índice único parcial
    `(enrollment_id, competencia_inicio) WHERE tipo='mensalidade'` garante no
    banco que o paciente nunca é cobrado duas vezes pelo mesmo ciclo —
    inclusive se a execução morrer no meio.

    O ciclo vem inteiro de `ciclo_service`. Nenhuma data é calculada aqui.
    """
    resultado = ResultadoFaturamento()
    limite = ate or date.today()

    stmt = select(Enrollment).where(
        Enrollment.status.in_([StatusMatricula.ATIVA, StatusMatricula.SUSPENSA])
    )
    if enrollment_id is not None:
        stmt = stmt.where(Enrollment.id == enrollment_id)

    for matricula in db.execute(stmt).scalars().unique().all():
        resultado.matriculas += 1
        for competencia in ciclo_service.competencias_ate(matricula, limite):
            existente = db.execute(
                select(Charge.id).where(
                    Charge.enrollment_id == matricula.id,
                    Charge.competencia_inicio == competencia.chave,
                    Charge.tipo == TipoCobranca.MENSALIDADE,
                    Charge.status != StatusCobranca.CANCELADO,
                )
            ).first()
            if existente is not None:
                resultado.ja_existentes += 1
                continue

            db.add(
                Charge(
                    patient_id=matricula.patient_id,
                    enrollment_id=matricula.id,
                    tipo=TipoCobranca.MENSALIDADE,
                    descricao=f"Mensalidade · {competencia.rotulo}",
                    competencia_inicio=competencia.inicio,
                    competencia_fim=competencia.fim,
                    # Snapshot da matrícula. Reajuste não altera cobrança
                    # já emitida.
                    valor_centavos=matricula.valor_mensal_centavos,
                    vencimento=competencia.vencimento,
                )
            )
            try:
                db.flush()
                resultado.criadas += 1
            except IntegrityError:
                db.rollback()
                resultado.ja_existentes += 1

    return resultado


def cobranca_do_pacote(db: DbSession, pacote: Package, *, descricao: str | None = None) -> Charge:
    """Cobrança que nasce no ato da venda do pacote. Não é mensal."""
    cobranca = Charge(
        patient_id=pacote.patient_id,
        package_id=pacote.id,
        tipo=TipoCobranca.PACOTE,
        descricao=descricao or f"Pacote de {pacote.sessoes_contratadas} sessões",
        valor_centavos=pacote.valor_centavos,
        vencimento=pacote.comprado_em,
        registrado_por_id=pacote.registrado_por_id,
    )
    db.add(cobranca)
    db.flush()
    return cobranca


def buscar(db: DbSession, charge_id: int) -> Charge:
    cobranca = db.get(Charge, charge_id)
    if cobranca is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cobrança não encontrada")
    return cobranca


def marcar_pago(
    db: DbSession,
    charge_id: int,
    *,
    registrado_por_id: int,
    forma: FormaPagamento = FormaPagamento.OUTRO,
) -> Charge:
    cobranca = buscar(db, charge_id)
    if cobranca.status is StatusCobranca.CANCELADO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cobrança cancelada não pode ser paga.",
        )
    cobranca.status = StatusCobranca.PAGO
    cobranca.pago_em = datetime.now(UTC)
    cobranca.forma_pagamento = forma
    cobranca.registrado_por_id = registrado_por_id
    db.flush()
    return cobranca


def desfazer_pagamento(db: DbSession, charge_id: int, *, registrado_por_id: int) -> Charge:
    """Volta a cobrança para pendente.

    A recepção erra ao dar baixa e precisa corrigir sem chamar a
    proprietária. Desfazer NÃO é cancelar: a cobrança continua devida.
    """
    cobranca = buscar(db, charge_id)
    if cobranca.status is not StatusCobranca.PAGO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só uma cobrança paga pode ser desfeita.",
        )
    cobranca.status = StatusCobranca.PENDENTE
    cobranca.pago_em = None
    cobranca.forma_pagamento = None
    cobranca.registrado_por_id = registrado_por_id
    db.flush()
    return cobranca


def cancelar(db: DbSession, charge_id: int, *, motivo: str | None = None) -> Charge:
    """Cancela a cobrança — ela deixa de ser devida.

    Restrito ao admin: perdoar dívida é decisão da proprietária, não da
    recepção. A rota é quem aplica o RBAC.
    """
    cobranca = buscar(db, charge_id)
    cobranca.status = StatusCobranca.CANCELADO
    cobranca.motivo_cancelamento = motivo
    db.flush()
    return cobranca


@dataclass
class Totais:
    """Os três cards do topo da tela, como no print."""

    recebido_centavos: int
    pendente_centavos: int
    vencido_centavos: int


def totais(db: DbSession) -> Totais:
    def soma(condicao: object) -> int:
        return int(
            db.execute(
                select(func.coalesce(func.sum(Charge.valor_centavos), 0)).where(condicao)  # type: ignore[arg-type]
            ).scalar_one()
        )

    return Totais(
        recebido_centavos=soma(Charge.status == StatusCobranca.PAGO),
        # Pendente inclui o vencido: é tudo que ainda não entrou no caixa.
        pendente_centavos=soma(Charge.status == StatusCobranca.PENDENTE),
        vencido_centavos=soma(vencida_sql()),
    )


def _stmt_listagem(filtro: str | None, busca: str | None) -> Select[tuple[Charge, Patient]]:
    stmt = (
        select(Charge, Patient)
        .join(Patient, Patient.id == Charge.patient_id)
        .order_by(Charge.vencimento.desc(), Charge.id.desc())
    )
    if filtro == "pendentes":
        stmt = stmt.where(Charge.status == StatusCobranca.PENDENTE)
    elif filtro == "pagos":
        stmt = stmt.where(Charge.status == StatusCobranca.PAGO)
    elif filtro == "vencidos":
        stmt = stmt.where(vencida_sql())  # type: ignore[arg-type]
    elif filtro == "cancelados":
        stmt = stmt.where(Charge.status == StatusCobranca.CANCELADO)

    if busca:
        termo = f"%{busca.strip()}%"
        stmt = stmt.where(or_(Patient.nome_completo.ilike(termo), Charge.descricao.ilike(termo)))
    return stmt


def listar(
    db: DbSession,
    *,
    filtro: str | None = None,
    busca: str | None = None,
    pagina: int = 1,
    tamanho: int = 30,
) -> tuple[list[tuple[Charge, Patient]], int]:
    stmt = _stmt_listagem(filtro, busca)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    linhas = db.execute(stmt.offset((pagina - 1) * tamanho).limit(tamanho)).all()
    return [(c, p) for c, p in linhas], total
