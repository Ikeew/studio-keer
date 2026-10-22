from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.core.deps import CurrentUser, require_papel
from app.db.session import get_db
from app.models.user import Papel
from app.schemas.dashboard import (
    AnaliseRead,
    BaldeDeReceitaRead,
    CelulaDeHorarioRead,
    EstatisticaDeServicoRead,
    FormaDePagamentoRead,
    HorariosRead,
    IndicadoresRead,
    OrigemRead,
    PeriodoRead,
    PresencaRead,
    ProximoAgendamentoRead,
    ReceitaRead,
    ServicoNoPeriodoRead,
    TaxaDeOcupacaoRead,
)
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"])

Db = Annotated[DbSession, Depends(get_db)]

#: Visão geral da operação: proprietária e recepção.
GESTAO = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))

_REGRA_OCUPACAO = (
    "Reserva ativa é agendada, confirmada, presente ou falta — cancelada não "
    "conta, porque a vaga voltou ao pool. Falta conta, porque o lugar ficou "
    "reservado e ninguém mais pôde usá-lo."
)
FORMULA_OCUPACAO = "reservas ativas ÷ capacidade ofertada no mês. " + _REGRA_OCUPACAO
#: A mesma regra, sobre o período da análise em vez do mês corrente.
FORMULA_OCUPACAO_PERIODO = "reservas ativas ÷ capacidade ofertada no período. " + _REGRA_OCUPACAO


def _ocupacao_read(
    o: dashboard_service.TaxaDeOcupacao, *, formula: str = FORMULA_OCUPACAO
) -> TaxaDeOcupacaoRead:
    return TaxaDeOcupacaoRead(
        percentual=o.percentual,
        reservas_ativas=o.reservas_ativas,
        capacidade_ofertada=o.capacidade_ofertada,
        formula=formula,
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


def _analise_read(a: dashboard_service.Analise, *, com_valores: bool) -> AnaliseRead:
    """`com_valores=False` tira todo valor em dinheiro da resposta.

    Esconder na tela não basta: o dado continuaria a uma chamada de distância.
    A contagem de pagamentos por forma fica, porque é a própria recepção que
    registra cada baixa.
    """
    receita = ReceitaRead(
        recebido_centavos=a.receita.recebido_centavos,
        pagamentos=a.receita.pagamentos,
        serie=[
            BaldeDeReceitaRead(
                inicio=b.inicio,
                fim=b.fim,
                recebido_centavos=b.recebido_centavos,
                por_tipo=dict(b.por_tipo),
                em_andamento=b.em_andamento,
            )
            for b in a.receita.serie
        ],
    )
    return AnaliseRead(
        periodo=PeriodoRead(
            inicio=a.periodo.inicio,
            fim=a.periodo.fim,
            meses=a.periodo.meses,
            granularidade=a.periodo.granularidade,
        ),
        receita=receita if com_valores else None,
        formas_pagamento=[
            FormaDePagamentoRead(
                forma=f.forma,
                pagamentos=f.pagamentos,
                valor_centavos=f.valor_centavos if com_valores else None,
            )
            for f in a.formas_pagamento
        ],
        servicos=[
            ServicoNoPeriodoRead(
                service_id=s.service_id,
                nome=s.nome,
                cor=s.cor,
                sessoes=s.sessoes,
                reservas=s.reservas,
                ocupacao_percentual=s.ocupacao_percentual,
            )
            for s in a.servicos
        ],
        ocupacao=_ocupacao_read(a.ocupacao, formula=FORMULA_OCUPACAO_PERIODO),
        horarios=HorariosRead(
            dias=a.horarios.dias,
            horas=a.horarios.horas,
            horas_por_dia=a.horarios.horas_por_dia,
            celulas=[
                CelulaDeHorarioRead(
                    dia_semana=c.dia_semana,
                    hora=c.hora,
                    sessoes=c.sessoes,
                    reservas=c.reservas,
                    capacidade=c.capacidade,
                    ocupacao_percentual=c.ocupacao_percentual,
                )
                for c in a.horarios.celulas
            ],
        ),
        presenca=PresencaRead(
            presentes=a.presenca.presentes,
            faltas_justificadas=a.presenca.faltas_justificadas,
            faltas_nao_justificadas=a.presenca.faltas_nao_justificadas,
            sem_registro=a.presenca.sem_registro,
            a_realizar=a.presenca.a_realizar,
            canceladas=a.presenca.canceladas,
            comparecimento_percentual=a.presenca.comparecimento_percentual,
        ),
        origens=[OrigemRead(origem=o.origem, reservas=o.reservas) for o in a.origens],
    )


@router.get("/dashboard/analise", response_model=AnaliseRead, dependencies=[GESTAO])
def analise(
    db: Db,
    usuario: CurrentUser,
    meses: Annotated[
        int,
        Query(
            ge=dashboard_service.MESES_MINIMO,
            le=dashboard_service.MESES_MAXIMO,
            description="Quantos meses do calendário analisar, contando o atual.",
        ),
    ] = 3,
) -> AnaliseRead:
    """Análise do período: receita, formas de pagamento, serviços, ocupação,
    horários, presença e origem das reservas.

    Receita e valores em dinheiro só vão para o admin.

    As definições de cada indicador estão em `dashboard_service`.
    """
    return _analise_read(
        dashboard_service.analise(db, meses), com_valores=usuario.papel is Papel.ADMIN
    )
