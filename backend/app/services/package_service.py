"""Regras do pacote de sessões vendido: saldo, validade e venda.

A definição de saldo vive isolada aqui desde a Fase 2, porque a Fase 3
precisa dela para saber se um paciente pode agendar. A venda chegou na
Fase 5, junto com o Financeiro.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.models.charge import Charge
from app.models.package import Package, StatusPacote
from app.models.patient import Patient
from app.models.service import Service


def sessoes_consumidas(db: DbSession, package_id: int) -> int:
    """Quantas sessões do pacote já foram gastas.

    DEFINIÇÃO — confirmada pela cliente, ver docs/premissas.md (P5):

        Só reserva com status `presente` consome sessão.
        `agendada`, `confirmada`, `cancelada` e `falta` NÃO consomem.

    Esta contagem existe SÓ AQUI. Não a reescreva numa consulta nova: é o tipo
    de regra que alguém "melhora" sem perceber, e o paciente acaba pagando por
    sessão que não teve.
    """
    # `bookings` chega na Fase 3. Até lá não há o que contar, e devolver zero
    # mantém a função utilizável (o saldo de um pacote novo é o total).
    if "bookings" not in Package.metadata.tables:
        return 0

    bookings = Package.metadata.tables["bookings"]
    return (
        db.execute(
            select(func.count())
            .select_from(bookings)
            .where(
                bookings.c.package_id == package_id,
                bookings.c.status == "presente",
            )
        ).scalar_one()
        or 0
    )


def saldo(db: DbSession, pacote: Package) -> int:
    return pacote.sessoes_contratadas - sessoes_consumidas(db, pacote.id)


def dentro_da_validade(pacote: Package, hoje: date | None = None) -> bool:
    """Validade nula significa 'vale até acabar o saldo', não 'sem dado'."""
    if pacote.validade_ate is None:
        return True
    return pacote.validade_ate >= (hoje or date.today())


def utilizavel(db: DbSession, pacote: Package, hoje: date | None = None) -> bool:
    """Se o pacote ainda pode ser usado para agendar.

    Checa validade JUNTO com saldo, nunca só saldo. Como falta não consome
    sessão (decisão da cliente), quem falta muito mantém o saldo intacto
    indefinidamente — a validade é a única trava do pacote.
    """
    return (
        pacote.status is StatusPacote.ATIVO
        and saldo(db, pacote) > 0
        and dentro_da_validade(pacote, hoje)
    )


# ── VENDA DE PACOTE ──────────────────────────────────────────────────────────


def vender(
    db: DbSession,
    *,
    patient_id: int,
    service_id: int,
    sessoes_contratadas: int,
    valor_centavos: int,
    registrado_por_id: int,
    validade_ate: date | None = None,
    comprado_em: date | None = None,
) -> tuple[Package, Charge]:
    """Vende um pacote e emite a cobrança no mesmo ato.

    Todos os valores vêm do FORMULÁRIO, não do serviço: cada pacote é
    negociado caso a caso pela doutora. `services.sugestao_pacote_*` só
    pré-preenche a tela — depois de vendido, o pacote nunca relê nada do
    serviço. Ver docs/modelo-de-dados.md.

    A cobrança nasce aqui, na venda, e não é mensal.
    """
    from app.services import charge_service

    paciente = db.get(Patient, patient_id)
    if paciente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado")
    servico = db.get(Service, service_id)
    if servico is None or not servico.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serviço não encontrado")

    compra = comprado_em or date.today()
    pacote = Package(
        patient_id=patient_id,
        service_id=service_id,
        sessoes_contratadas=sessoes_contratadas,
        valor_centavos=valor_centavos,
        validade_ate=validade_ate,
        comprado_em=compra,
        registrado_por_id=registrado_por_id,
        status=StatusPacote.ATIVO,
    )
    db.add(pacote)
    db.flush()

    cobranca = charge_service.cobranca_do_pacote(
        db,
        pacote,
        descricao=(
            f"{servico.nome} · pacote de {sessoes_contratadas} sessões"
            + (f" · validade {validade_ate:%d/%m/%Y}" if validade_ate else "")
        ),
    )
    return pacote, cobranca


def sugestao_para(db: DbSession, service_id: int) -> dict[str, int | None]:
    """Valores para PRÉ-PREENCHER o formulário de venda.

    Nunca são fonte de verdade e nunca são obrigatórios — a tela deixa tudo
    editável.
    """
    servico = db.get(Service, service_id)
    if servico is None:
        return {"sessoes": None, "validade_dias": None, "valor_centavos": None}
    return {
        "sessoes": servico.sugestao_pacote_sessoes,
        "validade_dias": servico.sugestao_pacote_validade_dias,
        "valor_centavos": servico.sugestao_pacote_valor_centavos,
    }
