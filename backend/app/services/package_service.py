"""Regras do pacote de sessões vendido.

A tela de venda pertence ao Financeiro (Fase 5). O que existe aqui é a
definição de saldo, isolada num lugar só desde já, porque a Fase 3 vai
precisar dela para saber se um paciente pode agendar.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.package import Package, StatusPacote


def sessoes_consumidas(db: Session, package_id: int) -> int:
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


def saldo(db: Session, pacote: Package) -> int:
    return pacote.sessoes_contratadas - sessoes_consumidas(db, pacote.id)


def dentro_da_validade(pacote: Package, hoje: date | None = None) -> bool:
    """Validade nula significa 'vale até acabar o saldo', não 'sem dado'."""
    if pacote.validade_ate is None:
        return True
    return pacote.validade_ate >= (hoje or date.today())


def utilizavel(db: Session, pacote: Package, hoje: date | None = None) -> bool:
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
