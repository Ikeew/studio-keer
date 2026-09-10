from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.core.deps import CurrentUser, require_papel
from app.db.session import get_db
from app.models.user import Papel
from app.schemas.dashboard import (
    EstatisticaDeServicoRead,
    IndicadoresRead,
    ProximoAgendamentoRead,
    TaxaDeOcupacaoRead,
)
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"])

Db = Annotated[DbSession, Depends(get_db)]

#: Visão geral da operação: proprietária e recepção.
GESTAO = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))

FORMULA_OCUPACAO = (
    "reservas ativas ÷ capacidade ofertada no mês. "
    "Reserva ativa é agendada, confirmada, presente ou falta — cancelada não "
    "conta, porque a vaga voltou ao pool. Falta conta, porque o lugar ficou "
    "reservado e ninguém mais pôde usá-lo."
)


def _ocupacao_read(o: dashboard_service.TaxaDeOcupacao) -> TaxaDeOcupacaoRead:
    return TaxaDeOcupacaoRead(
        percentual=o.percentual,
        reservas_ativas=o.reservas_ativas,
        capacidade_ofertada=o.capacidade_ofertada,
        formula=FORMULA_OCUPACAO,
    )


def _proximo_read(p: dashboard_service.ProximoAgendamento) -> ProximoAgendamentoRead:
    return ProximoAgendamentoRead(
        booking_id=p.booking_id,
        hora=p.hora,
        paciente_nome=p.paciente_nome,
        servico_nome=p.servico_nome,
        instrutor_nome=p.instrutor_nome,
        status=p.status,
    )


@router.get("/dashboard", response_model=IndicadoresRead, dependencies=[GESTAO])
def indicadores(db: Db) -> IndicadoresRead:
    """Os quatro indicadores do print, com números reais."""
    i = dashboard_service.indicadores(db)
    return IndicadoresRead(
        agendamentos_hoje=i.agendamentos_hoje,
        pacientes_ativos=i.pacientes_ativos,
        sessoes_no_mes=i.sessoes_no_mes,
        ocupacao=_ocupacao_read(i.ocupacao),
        proximos=[_proximo_read(p) for p in i.proximos],
    )


@router.get(
    "/dashboard/minha-agenda",
    response_model=list[ProximoAgendamentoRead],
    # Rota do instrutor. Admin também acessa para conferir a visão dele.
    dependencies=[Depends(require_papel(Papel.INSTRUTOR, Papel.ADMIN))],
)
def minha_agenda(db: Db, usuario: CurrentUser) -> list[ProximoAgendamentoRead]:
    """Aulas de hoje do instrutor autenticado. Somente leitura.

    Filtra pelo usuário do token, não por um id na URL: um instrutor não
    pode ler a agenda de outro passando um id diferente.
    """
    aulas = dashboard_service.agenda_do_instrutor(db, usuario.id)
    return [_proximo_read(p) for p in aulas]


@router.get(
    "/dashboard/servicos",
    response_model=list[EstatisticaDeServicoRead],
    dependencies=[GESTAO],
)
def estatisticas_de_servicos(db: Db) -> list[EstatisticaDeServicoRead]:
    """Painel da tela de Atividades."""
    return [
        EstatisticaDeServicoRead(
            service_id=e.service_id,
            nome=e.nome,
            cor=e.cor,
            sessoes_no_mes=e.sessoes_no_mes,
            reservas_no_mes=e.reservas_no_mes,
            ocupacao_percentual=e.ocupacao_percentual,
        )
        for e in dashboard_service.estatisticas_de_servicos(db)
    ]
