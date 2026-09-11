from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.deps import CurrentUser, require_papel
from app.db.session import get_db
from app.models.charge import Charge
from app.models.package import Package
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import Papel
from app.schemas.financeiro import (
    CancelarCobranca,
    ChargeRead,
    MarcarPago,
    PackageRead,
    PaginaDeCobrancas,
    ResultadoFaturamentoRead,
    SugestaoDePacote,
    TotaisRead,
    VendaDePacote,
)
from app.services import charge_service, package_service

router = APIRouter(tags=["financeiro"])

Db = Annotated[DbSession, Depends(get_db)]

# O instrutor não vê valores: a agenda é a tela dele.
OPERADORES = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))
# Perdoar dívida é decisão da proprietária, não da recepção.
SO_ADMIN = Depends(require_papel(Papel.ADMIN))


def _para_leitura(cobranca: Charge, paciente: Patient) -> ChargeRead:
    return ChargeRead(
        id=cobranca.id,
        patient_id=paciente.id,
        paciente_nome=paciente.nome_completo,
        tipo=cobranca.tipo,
        descricao=cobranca.descricao,
        competencia_inicio=cobranca.competencia_inicio,
        competencia_fim=cobranca.competencia_fim,
        valor_centavos=cobranca.valor_centavos,
        vencimento=cobranca.vencimento,
        status=cobranca.status,
        pago_em=cobranca.pago_em,
        forma_pagamento=cobranca.forma_pagamento,
    )


def _recarregar(db: DbSession, cobranca: Charge) -> ChargeRead:
    paciente = db.get(Patient, cobranca.patient_id)
    assert paciente is not None
    return _para_leitura(cobranca, paciente)


@router.get("/charges", response_model=PaginaDeCobrancas, dependencies=[OPERADORES])
def listar(
    db: Db,
    filtro: Annotated[
        str | None, Query(description="pendentes | pagos | vencidos | cancelados")
    ] = None,
    # Mesmos limites da listagem de pacientes, pelos mesmos motivos — ver o
    # comentário em api/v1/patients.py.
    busca: Annotated[str | None, Query(max_length=100)] = None,
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 30,
) -> PaginaDeCobrancas:
    linhas, total = charge_service.listar(
        db, filtro=filtro, busca=busca, pagina=pagina, tamanho=tamanho
    )
    return PaginaDeCobrancas(
        itens=[_para_leitura(c, p) for c, p in linhas],
        total=total,
        pagina=pagina,
        tamanho=tamanho,
    )


@router.get("/charges/totais", response_model=TotaisRead, dependencies=[OPERADORES])
def totais(db: Db) -> TotaisRead:
    t = charge_service.totais(db)
    return TotaisRead(
        recebido_centavos=t.recebido_centavos,
        pendente_centavos=t.pendente_centavos,
        vencido_centavos=t.vencido_centavos,
    )


@router.get("/charges/{charge_id}", response_model=ChargeRead, dependencies=[OPERADORES])
def obter(charge_id: int, db: Db) -> ChargeRead:
    """Consistência: toda entidade tem GET por id.

    Sem esta rota, pedir uma cobrança pelo id devolvia 405 — um erro que não
    diz nada a quem está integrando ou depurando.
    """
    return _recarregar(db, charge_service.buscar(db, charge_id))


@router.post(
    "/charges/gerar-mensalidades",
    response_model=ResultadoFaturamentoRead,
    dependencies=[OPERADORES],
)
def gerar_mensalidades(db: Db, ate: date | None = None) -> ResultadoFaturamentoRead:
    """Emite as mensalidades devidas até a data.

    Idempotente: rodar duas vezes não cobra o paciente duas vezes.
    """
    r = charge_service.gerar_mensalidades(db, ate=ate)
    db.commit()
    return ResultadoFaturamentoRead(
        criadas=r.criadas, ja_existentes=r.ja_existentes, matriculas=r.matriculas
    )


@router.post("/charges/{charge_id}/pagar", response_model=ChargeRead, dependencies=[OPERADORES])
def marcar_pago(charge_id: int, dados: MarcarPago, db: Db, usuario: CurrentUser) -> ChargeRead:
    cobranca = charge_service.marcar_pago(
        db, charge_id, registrado_por_id=usuario.id, forma=dados.forma_pagamento
    )
    db.commit()
    return _recarregar(db, cobranca)


@router.post("/charges/{charge_id}/desfazer", response_model=ChargeRead, dependencies=[OPERADORES])
def desfazer_pagamento(charge_id: int, db: Db, usuario: CurrentUser) -> ChargeRead:
    """Volta a cobrança para pendente.

    A recepção erra ao dar baixa e precisa corrigir sem chamar a
    proprietária. Desfazer não é cancelar: a cobrança continua devida.
    """
    cobranca = charge_service.desfazer_pagamento(db, charge_id, registrado_por_id=usuario.id)
    db.commit()
    return _recarregar(db, cobranca)


@router.delete("/charges/{charge_id}", response_model=ChargeRead, dependencies=[SO_ADMIN])
def cancelar(charge_id: int, dados: CancelarCobranca, db: Db) -> ChargeRead:
    """Cancela a cobrança — ela deixa de ser devida. Só a proprietária."""
    cobranca = charge_service.cancelar(db, charge_id, motivo=dados.motivo)
    db.commit()
    return _recarregar(db, cobranca)


# ── PACOTES ──────────────────────────────────────────────────────────────────


def _pacote_para_leitura(db: DbSession, pacote: Package) -> PackageRead:
    paciente = db.get(Patient, pacote.patient_id)
    servico = db.get(Service, pacote.service_id)
    return PackageRead(
        id=pacote.id,
        patient_id=pacote.patient_id,
        paciente_nome=paciente.nome_completo if paciente else "",
        service_id=pacote.service_id,
        servico_nome=servico.nome if servico else "",
        sessoes_contratadas=pacote.sessoes_contratadas,
        valor_centavos=pacote.valor_centavos,
        validade_ate=pacote.validade_ate,
        comprado_em=pacote.comprado_em,
        status=pacote.status.value,
        sessoes_usadas=package_service.sessoes_consumidas(db, pacote.id),
        saldo=package_service.saldo(db, pacote),
        utilizavel=package_service.utilizavel(db, pacote),
    )


@router.get("/packages", response_model=list[PackageRead], dependencies=[OPERADORES])
def listar_pacotes(db: Db, patient_id: int | None = None) -> list[PackageRead]:
    stmt = select(Package).order_by(Package.comprado_em.desc())
    if patient_id is not None:
        stmt = stmt.where(Package.patient_id == patient_id)
    return [_pacote_para_leitura(db, p) for p in db.execute(stmt).scalars().all()]


@router.get(
    "/packages/sugestao/{service_id}",
    response_model=SugestaoDePacote,
    dependencies=[OPERADORES],
)
def sugestao(service_id: int, db: Db) -> SugestaoDePacote:
    """Valores para pré-preencher a venda. Todos editáveis na tela."""
    s = package_service.sugestao_para(db, service_id)
    return SugestaoDePacote(
        sessoes=s["sessoes"],
        validade_dias=s["validade_dias"],
        valor_centavos=s["valor_centavos"],
    )


@router.post(
    "/packages",
    response_model=PackageRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[OPERADORES],
)
def vender_pacote(dados: VendaDePacote, db: Db, usuario: CurrentUser) -> PackageRead:
    """Vende um pacote e emite a cobrança no mesmo ato.

    Todos os valores vêm do formulário — a sugestão do serviço só
    pré-preencheu a tela. Depois de vendido, o pacote nunca relê o serviço.
    """
    pacote, _ = package_service.vender(
        db,
        patient_id=dados.patient_id,
        service_id=dados.service_id,
        sessoes_contratadas=dados.sessoes_contratadas,
        valor_centavos=dados.valor_centavos,
        validade_ate=dados.validade_ate,
        registrado_por_id=usuario.id,
    )
    db.commit()
    return _pacote_para_leitura(db, pacote)


@router.get("/packages/validade-sugerida", dependencies=[OPERADORES])
def validade_sugerida(dias: int) -> dict[str, str]:
    """Converte "N dias" numa data, para a tela não fazer conta de calendário."""
    return {"validade_ate": (date.today() + timedelta(days=dias)).isoformat()}
