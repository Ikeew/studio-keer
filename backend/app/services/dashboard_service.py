"""Indicadores do dashboard.

Nada aqui é armazenado. Todo número é contado no momento da consulta, pelo
mesmo motivo que vale para saldo, vagas e "vencido": um valor gravado sai de
sincronia e mente até alguém recalcular.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.models.booking import Booking, OrigemReserva, StatusReserva
from app.models.charge import Charge, FormaPagamento, StatusCobranca, TipoCobranca
from app.models.configuracao import HorarioFuncionamento
from app.models.patient import Patient
from app.models.service import Service
from app.models.session import Session, StatusSessao
from app.models.user import User
from app.services.schedule_service import FUSO, horas_do_dia, inicio_da_semana

#: Reservas que ocupam vaga. Cancelada não ocupa — a vaga voltou ao pool.
_ATIVAS = (
    StatusReserva.AGENDADA,
    StatusReserva.CONFIRMADA,
    StatusReserva.PRESENTE,
    StatusReserva.FALTA,
)


def _intervalo(inicio: date, fim: date) -> tuple[datetime, datetime]:
    """Dia inteiro no fuso do studio, do primeiro instante ao último."""
    return (
        datetime.combine(inicio, time.min, tzinfo=FUSO),
        datetime.combine(fim + timedelta(days=1), time.min, tzinfo=FUSO),
    )


def _filtro_sessoes(inicio: date, fim: date) -> tuple[ColumnElement[bool], ...]:
    """Sessões que contam num período: começam nele e não foram canceladas.

    Sessão cancelada sai de TODO indicador — não ofereceu capacidade, não
    teve aula, e as reservas dela não aconteceram. Fica num lugar só para que
    nenhum indicador use um recorte diferente do outro.
    """
    de, ate = _intervalo(inicio, fim)
    return (
        Session.inicia_em >= de,
        Session.inicia_em < ate,
        Session.status != StatusSessao.CANCELADA,
    )


def _sessoes_no_periodo(inicio: date, fim: date) -> Select[tuple[int]]:
    return select(Session.id).where(*_filtro_sessoes(inicio, fim))


@dataclass(frozen=True)
class TaxaDeOcupacao:
    """Quanto da capacidade oferecida foi efetivamente ocupada.

    ── A FÓRMULA ────────────────────────────────────────────────────────────

        taxa = reservas_ativas / capacidade_ofertada

    onde, no período:

      reservas_ativas     contagem de `bookings` cujo status ocupa vaga —
                          agendada, confirmada, presente ou falta.
                          CANCELADA não conta: a vaga voltou ao pool e pode
                          ter sido ocupada por outra pessoa, que é contada
                          separadamente. Contar cancelada inflaria a taxa com
                          lugares que ficaram vazios.

                          FALTA conta: a aula aconteceu com aquele lugar
                          reservado e ninguém mais pôde usá-lo. Do ponto de
                          vista de capacidade, o studio estava ocupado. É por
                          isso que a taxa mede OCUPAÇÃO, não comparecimento.

      capacidade_ofertada soma da `capacidade` de todas as sessões não
                          canceladas do período. É a capacidade real de cada
                          turma, e não `capacidade_padrao` do serviço — uma
                          sessão pode ter override.

    Sem sessão no período a taxa é 0%, não indefinida: um studio sem aula
    marcada tem ocupação zero.

    ── O QUE ESTA TAXA NÃO É ────────────────────────────────────────────────

    Não é taxa de comparecimento (que excluiria faltas) nem de aproveitamento
    financeiro. É quanto dos lugares oferecidos foram vendidos.
    """

    reservas_ativas: int
    capacidade_ofertada: int

    @property
    def percentual(self) -> int:
        if self.capacidade_ofertada == 0:
            return 0
        return round(100 * self.reservas_ativas / self.capacidade_ofertada)


def taxa_de_ocupacao(db: DbSession, inicio: date, fim: date) -> TaxaDeOcupacao:
    sessoes = _sessoes_no_periodo(inicio, fim).subquery()

    capacidade = int(
        db.execute(
            select(func.coalesce(func.sum(Session.capacidade), 0)).where(
                Session.id.in_(select(sessoes.c.id))
            )
        ).scalar_one()
    )
    reservas = int(
        db.execute(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.session_id.in_(select(sessoes.c.id)),
                Booking.status.in_(_ATIVAS),
            )
        ).scalar_one()
    )
    return TaxaDeOcupacao(reservas_ativas=reservas, capacidade_ofertada=capacidade)


@dataclass
class ProximoAgendamento:
    booking_id: int
    hora: str
    paciente_nome: str
    servico_nome: str
    instrutor_nome: str
    status: StatusReserva


@dataclass
class Indicadores:
    agendamentos_hoje: int
    pacientes_ativos: int
    sessoes_no_mes: int
    ocupacao: TaxaDeOcupacao
    proximos: list[ProximoAgendamento]


def _proximos_de(
    db: DbSession, dia: date, *, professional_id: int | None = None, limite: int = 8
) -> list[ProximoAgendamento]:
    de, ate = _intervalo(dia, dia)
    stmt = (
        select(Booking, Session, Patient, Service, User)
        .join(Session, Session.id == Booking.session_id)
        .join(Patient, Patient.id == Booking.patient_id)
        .join(Service, Service.id == Session.service_id)
        .join(User, User.id == Session.professional_id)
        .where(
            Session.inicia_em >= de,
            Session.inicia_em < ate,
            Session.status != StatusSessao.CANCELADA,
            Booking.status != StatusReserva.CANCELADA,
        )
        .order_by(Session.inicia_em, Booking.posicao)
        .limit(limite)
    )
    if professional_id is not None:
        stmt = stmt.where(Session.professional_id == professional_id)

    return [
        ProximoAgendamento(
            booking_id=reserva.id,
            hora=f"{sessao.inicia_em.astimezone(FUSO):%H:%M}",
            paciente_nome=paciente.nome_completo,
            servico_nome=servico.nome,
            instrutor_nome=instrutor.nome,
            status=reserva.status,
        )
        for reserva, sessao, paciente, servico, instrutor in db.execute(stmt).all()
    ]


def indicadores(db: DbSession) -> Indicadores:
    hoje = date.today()
    primeiro_do_mes = hoje.replace(day=1)
    proximo_mes = (primeiro_do_mes + timedelta(days=32)).replace(day=1)
    ultimo_do_mes = proximo_mes - timedelta(days=1)

    de_hoje, ate_hoje = _intervalo(hoje, hoje)
    agendamentos_hoje = int(
        db.execute(
            select(func.count())
            .select_from(Booking)
            .join(Session, Session.id == Booking.session_id)
            .where(
                Session.inicia_em >= de_hoje,
                Session.inicia_em < ate_hoje,
                Session.status != StatusSessao.CANCELADA,
                Booking.status != StatusReserva.CANCELADA,
            )
        ).scalar_one()
    )

    pacientes_ativos = int(
        db.execute(
            select(func.count()).select_from(Patient).where(Patient.ativo.is_(True))
        ).scalar_one()
    )

    sessoes_no_mes = int(
        db.execute(
            select(func.count()).select_from(
                _sessoes_no_periodo(primeiro_do_mes, ultimo_do_mes).subquery()
            )
        ).scalar_one()
    )

    return Indicadores(
        agendamentos_hoje=agendamentos_hoje,
        pacientes_ativos=pacientes_ativos,
        sessoes_no_mes=sessoes_no_mes,
        ocupacao=taxa_de_ocupacao(db, primeiro_do_mes, ultimo_do_mes),
        proximos=_proximos_de(db, hoje),
    )


def agenda_do_instrutor(db: DbSession, professional_id: int) -> list[ProximoAgendamento]:
    """Aulas de hoje do instrutor. Somente leitura — é a tela dele."""
    return _proximos_de(db, date.today(), professional_id=professional_id, limite=50)


def _percentual(parte: int, todo: int) -> int:
    """Percentual inteiro; 0 quando o denominador é 0 (nada a medir, não erro)."""
    return round(100 * parte / todo) if todo else 0


@dataclass(frozen=True)
class ServicoNoPeriodo:
    """Movimento de um serviço num intervalo de datas.

    ── O QUE CADA NÚMERO CONTA ──────────────────────────────────────────────

      sessoes      sessões do serviço que começam no intervalo e não foram
                   canceladas. Sessão cancelada não teve aula nem ofereceu
                   lugar — contá-la inflaria o volume do serviço.

      capacidade   soma da `capacidade` dessas sessões. É a capacidade da
                   SESSÃO, não o `capacidade_padrao` do serviço: uma turma
                   pode ter override.

      reservas     reservas ATIVAS nessas sessões — agendada, confirmada,
                   presente ou falta. A mesma regra da `TaxaDeOcupacao`, pelo
                   mesmo motivo: a falta ocupou o lugar, a cancelada devolveu.

      ocupacao_percentual  round(100 * reservas ÷ capacidade); 0 sem sessão.

    ── QUEM ENTRA NA LISTA ──────────────────────────────────────────────────

    Todo serviço ATIVO, mesmo sem sessão — aparecer zerado é informação ("não
    vendemos nada disso no período"). E todo serviço INATIVO que teve sessão
    no intervalo: desativar um serviço hoje não apaga o que ele movimentou no
    trimestre. Inativo sem sessão fica fora, porque não diz nada.
    """

    service_id: int
    nome: str
    cor: str
    ativo: bool
    sessoes: int
    capacidade: int
    reservas: int

    @property
    def ocupacao_percentual(self) -> int:
        return _percentual(self.reservas, self.capacidade)


def servicos_no_intervalo(db: DbSession, inicio: date, fim: date) -> list[ServicoNoPeriodo]:
    """Movimento por serviço em `[inicio, fim]`, ordenado por nome.

    Três consultas AGRUPADAS por serviço, qualquer que seja o número de
    serviços — nada de uma consulta por serviço (N+1). É o agregador único
    da tela de Atividades e da análise do período.
    """
    no_intervalo = _filtro_sessoes(inicio, fim)

    sessoes: dict[int, tuple[int, int]] = {
        service_id: (int(quantidade), int(capacidade))
        for service_id, quantidade, capacidade in db.execute(
            select(
                Session.service_id,
                func.count(),
                func.coalesce(func.sum(Session.capacidade), 0),
            )
            .where(*no_intervalo)
            .group_by(Session.service_id)
        ).all()
    }
    reservas: dict[int, int] = {
        service_id: int(quantidade)
        for service_id, quantidade in db.execute(
            select(Session.service_id, func.count())
            .select_from(Booking)
            .join(Session, Session.id == Booking.session_id)
            .where(*no_intervalo, Booking.status.in_(_ATIVAS))
            .group_by(Session.service_id)
        ).all()
    }
    servicos = db.execute(
        select(Service)
        .where(or_(Service.ativo.is_(True), Service.id.in_(list(sessoes))))
        .order_by(Service.nome)
    ).scalars()

    return [
        ServicoNoPeriodo(
            service_id=servico.id,
            nome=servico.nome,
            cor=servico.cor,
            ativo=servico.ativo,
            sessoes=sessoes.get(servico.id, (0, 0))[0],
            capacidade=sessoes.get(servico.id, (0, 0))[1],
            reservas=reservas.get(servico.id, 0),
        )
        for servico in servicos
    ]


@dataclass
class EstatisticaDeServico:
    service_id: int
    nome: str
    cor: str
    #: Sessões realizadas ou marcadas no mês.
    sessoes_no_mes: int
    #: Reservas que ocuparam vaga no mês.
    reservas_no_mes: int
    ocupacao_percentual: int


def estatisticas_de_servicos(db: DbSession) -> list[EstatisticaDeServico]:
    """Painel da tela de Atividades, como no print: serviços ativos, mês corrente."""
    hoje = date.today()
    primeiro = hoje.replace(day=1)
    ultimo = (primeiro + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    return [
        EstatisticaDeServico(
            service_id=s.service_id,
            nome=s.nome,
            cor=s.cor,
            sessoes_no_mes=s.sessoes,
            reservas_no_mes=s.reservas,
            ocupacao_percentual=s.ocupacao_percentual,
        )
        for s in servicos_no_intervalo(db, primeiro, ultimo)
        # A tela de Atividades mostra o catálogo vigente; o inativo que teve
        # sessão no mês só entra na análise do período.
        if s.ativo
    ]


# ════════════════════════════════════════════════════════════════════════════
# ANÁLISE DO PERÍODO
#
# Os mesmos princípios do resto do módulo: nada armazenado, tudo contado na
# hora, e cada indicador com a definição escrita ao lado — o que conta, o que
# não conta e por quê. São os números que a banca vai perguntar.
# ════════════════════════════════════════════════════════════════════════════

Granularidade = Literal["semana", "mes"]

MESES_MINIMO = 1
MESES_MAXIMO = 12


@dataclass(frozen=True)
class Periodo:
    """Recorte da análise: os últimos `meses` meses do CALENDÁRIO, inclusive o atual.

      inicio         dia 1 do mês que fica (meses - 1) meses antes do atual.
      fim            último dia do mês atual — inclui os dias que ainda não
                     chegaram, para que agenda futura do mês (a_realizar,
                     ocupação já vendida) apareça junto do que já aconteceu.
      granularidade  "semana" quando o recorte é de um mês só (um balde por
                     mês daria uma barra única); "mes" nos demais.

    "Hoje" é a data em America/Sao_Paulo, nunca a do servidor: em container o
    servidor está em UTC, e às 22:00 de 31/08 em São Paulo ele já acha que é
    setembro.

    É mês do calendário, e não o ciclo de cobrança por aniversário
    (`ciclo_service`): a pergunta aqui é "quanto entrou em agosto", não "qual
    competência venceu".
    """

    inicio: date
    fim: date
    meses: int
    granularidade: Granularidade


def _indice_do_mes(d: date) -> int:
    """Mês como número corrido (ano * 12 + mês - 1): somar e subtrair meses
    vira aritmética de inteiro, sem `date(ano, mes, 31)` que estoura em abril."""
    return d.year * 12 + d.month - 1


def _primeiro_dia(indice: int) -> date:
    return date(indice // 12, indice % 12 + 1, 1)


def _ultimo_dia(indice: int) -> date:
    """Último dia do mês = véspera do primeiro dia do mês seguinte."""
    return _primeiro_dia(indice + 1) - timedelta(days=1)


def periodo_de_analise(meses: int, hoje: date) -> Periodo:
    """Função pura: mesmo `meses` e mesmo `hoje`, mesmo período."""
    if not MESES_MINIMO <= meses <= MESES_MAXIMO:
        raise ValueError(
            f"meses deve estar entre {MESES_MINIMO} e {MESES_MAXIMO}; recebido {meses}"
        )
    atual = _indice_do_mes(hoje)
    return Periodo(
        inicio=_primeiro_dia(atual - (meses - 1)),
        fim=_ultimo_dia(atual),
        meses=meses,
        granularidade="semana" if meses == 1 else "mes",
    )


def _baldes(periodo: Periodo, hoje: date) -> list[tuple[date, date]]:
    """Intervalos da série de receita, em ordem cronológica.

    "mes": um balde por mês do período.
    "semana": semanas de segunda a domingo (a semana da grade), recortadas ao
    mês — a primeira e a última podem ter menos de sete dias.

    Baldes que começam depois de hoje ficam fora: não existe receita do
    futuro, e uma barra zerada ali seria lida como "não entrou nada".
    """
    limites: list[tuple[date, date]] = []
    if periodo.granularidade == "mes":
        primeiro = _indice_do_mes(periodo.inicio)
        limites = [
            (_primeiro_dia(i), _ultimo_dia(i)) for i in range(primeiro, primeiro + periodo.meses)
        ]
    else:
        segunda = inicio_da_semana(periodo.inicio)
        while segunda <= periodo.fim:
            limites.append(
                (max(segunda, periodo.inicio), min(segunda + timedelta(days=6), periodo.fim))
            )
            segunda += timedelta(days=7)
    return [(inicio, fim) for inicio, fim in limites if inicio <= hoje]


@dataclass(frozen=True)
class _Pagamento:
    dia: date
    tipo: TipoCobranca
    forma: FormaPagamento | None
    valor_centavos: int


def _pagamentos_do_periodo(db: DbSession, periodo: Periodo) -> list[_Pagamento]:
    """Cobranças PAGAS cujo `pago_em` cai no período (dia inteiro no fuso).

    O dia do pagamento é `pago_em` convertido para São Paulo. Agrupar pela
    data em UTC poria o Pix das 23:30 de 31/08 em setembro.
    """
    de, ate = _intervalo(periodo.inicio, periodo.fim)
    pagamentos: list[_Pagamento] = []
    for pago_em, tipo, forma, valor in db.execute(
        select(Charge.pago_em, Charge.tipo, Charge.forma_pagamento, Charge.valor_centavos).where(
            Charge.status == StatusCobranca.PAGO,
            Charge.pago_em >= de,
            Charge.pago_em < ate,
        )
    ).all():
        if pago_em is None:  # impossível pelo CHECK pago_tem_data; satisfaz o tipo
            continue
        pagamentos.append(
            _Pagamento(
                dia=pago_em.astimezone(FUSO).date(),
                tipo=tipo,
                forma=forma,
                valor_centavos=valor,
            )
        )
    return pagamentos


@dataclass(frozen=True)
class BaldeDeReceita:
    """Quanto entrou em `[inicio, fim]`, aberto por tipo de cobrança.

    `por_tipo` tem SEMPRE as três chaves (mensalidade, pacote, avulsa), zero
    quando não houver — a tela empilha as três sem precisar adivinhar.
    `em_andamento` marca o balde que contém hoje: ele ainda vai crescer, e
    compará-lo com um mês fechado sem esse aviso sugere queda que não houve.
    """

    inicio: date
    fim: date
    recebido_centavos: int
    por_tipo: dict[TipoCobranca, int]
    em_andamento: bool


@dataclass(frozen=True)
class Receita:
    """Dinheiro que ENTROU no período — regime de caixa, não de competência.

      recebido_centavos  soma de `valor_centavos` das cobranças com status
                         PAGO e `pago_em` no período.
      pagamentos         quantas cobranças são essas.

    NÃO conta: pendente (ainda não entrou — é a fila do financeiro, não
    receita) nem cancelada (não vai entrar). Também não importa o vencimento
    nem a competência: a mensalidade de setembro paga em outubro é receita de
    outubro, porque é quando o dinheiro chegou.

    `pago_em` é gravado no instante em que a recepção registra o pagamento,
    então não existe pagamento no futuro e a soma da série é o total.
    """

    recebido_centavos: int
    pagamentos: int
    serie: list[BaldeDeReceita]


def _receita(pagamentos: list[_Pagamento], periodo: Periodo, hoje: date) -> Receita:
    serie: list[BaldeDeReceita] = []
    for inicio, fim in _baldes(periodo, hoje):
        por_tipo = dict.fromkeys(TipoCobranca, 0)
        for p in pagamentos:
            if inicio <= p.dia <= fim:
                por_tipo[p.tipo] += p.valor_centavos
        serie.append(
            BaldeDeReceita(
                inicio=inicio,
                fim=fim,
                recebido_centavos=sum(por_tipo.values()),
                por_tipo=por_tipo,
                em_andamento=inicio <= hoje <= fim,
            )
        )
    return Receita(
        recebido_centavos=sum(p.valor_centavos for p in pagamentos),
        pagamentos=len(pagamentos),
        serie=serie,
    )


@dataclass(frozen=True)
class FormaDePagamento:
    """Como o dinheiro do período entrou.

    Mesmo universo da `Receita` (cobranças PAGAS com `pago_em` no período),
    agrupado por `forma_pagamento`. `forma = None` é "Não informada" e aparece
    como item próprio: escondê-la faria as formas somarem menos que a receita.
    Só entram formas com pelo menos um pagamento; ordem por quantidade de
    pagamentos e, no empate, por valor.
    """

    forma: FormaPagamento | None
    pagamentos: int
    valor_centavos: int


def _formas(pagamentos: list[_Pagamento]) -> list[FormaDePagamento]:
    quantidade: dict[FormaPagamento | None, int] = defaultdict(int)
    valor: dict[FormaPagamento | None, int] = defaultdict(int)
    for p in pagamentos:
        quantidade[p.forma] += 1
        valor[p.forma] += p.valor_centavos

    formas = [
        FormaDePagamento(forma=f, pagamentos=quantidade[f], valor_centavos=valor[f])
        for f in quantidade
    ]
    # Desempate final pelo nome (e "não informada" por último) só para a
    # ordem ser determinística entre duas chamadas.
    formas.sort(key=lambda f: (-f.pagamentos, -f.valor_centavos, f.forma is None, f.forma or ""))
    return formas


@dataclass(frozen=True)
class CelulaDeHorario:
    """Uma combinação (dia da semana, hora cheia) no período — o mapa de calor.

      sessoes      sessões não canceladas que começam naquele dia/hora, no
                   fuso do studio. A sessão das 08:00 em São Paulo é hora 8,
                   não 11 (que é a hora em UTC).
      capacidade   soma da capacidade dessas sessões.
      reservas     reservas ATIVAS nelas (mesma regra da ocupação).
      ocupacao_percentual  round(100 * reservas ÷ capacidade).

    `dia_semana` segue a convenção do banco: 0 = domingo … 6 = sábado.
    A mesma segunda 08:00 em semanas diferentes soma na mesma célula — é o
    que responde "qual horário enche e qual sobra".
    """

    dia_semana: int
    hora: int
    sessoes: int
    capacidade: int
    reservas: int

    @property
    def ocupacao_percentual(self) -> int:
        return _percentual(self.reservas, self.capacidade)


@dataclass(frozen=True)
class Horarios:
    """Eixos e células do mapa de calor.

      dias    dias abertos em `horarios_funcionamento` mais os dias que tiveram
              sessão, segunda primeiro e domingo por último (a ordem da grade).
      horas   horas atendíveis dos dias abertos (`horas_do_dia`, já SEM a
              pausa) mais as horas que tiveram sessão. A pausa não vira coluna
              vazia: o studio não atende ali, então não há o que medir.
      horas_por_dia
              para CADA dia de `dias`, as horas atendíveis dele segundo a
              configuração ATUAL, ordenadas; [] se o dia está fechado ou não
              tem linha de configuração.
      celulas só as combinações que tiveram sessão.

    Combinação sem célula é uma de duas coisas, e o mapa precisa distinguir:
    "sem turma" (hora dentro de `horas_por_dia[dia]`: o studio atende ali e
    ninguém comprou) ou "fechado" (fora dela: não há o que vender, então não
    é ociosidade). As duas diferem de "turma vazia" (célula com 0%). O eixo
    `horas` é a união de todos os dias e não basta para isso: o horário de
    cada dia é configuração, e a cliente pode fechar o sábado às 12:00 com um
    UPDATE — sábado à tarde não pode aparecer como horário ocioso só porque a
    segunda atende até as 21:00.

    Os eixos vêm da configuração e não só das células para que um horário
    aberto que ninguém comprou apareça como buraco no mapa — é justamente a
    informação útil. Sem configuração no banco, os eixos saem só das células
    (e todo `horas_por_dia` é []); a análise não depende dela para existir.
    """

    dias: list[int]
    horas: list[int]
    horas_por_dia: dict[int, list[int]]
    celulas: list[CelulaDeHorario]


def _ordem_do_dia(dia_semana: int) -> int:
    """Segunda (1) primeiro, domingo (0) por último."""
    return (dia_semana + 6) % 7


def _horarios(db: DbSession, periodo: Periodo) -> Horarios:
    # Uma consulta: cada sessão com a contagem das reservas ativas dela. O
    # LEFT JOIN mantém a sessão vazia (capacidade ofertada, zero reservas).
    linhas = db.execute(
        select(Session.inicia_em, Session.capacidade, func.count(Booking.id))
        .outerjoin(
            Booking,
            and_(Booking.session_id == Session.id, Booking.status.in_(_ATIVAS)),
        )
        .where(*_filtro_sessoes(periodo.inicio, periodo.fim))
        .group_by(Session.id)
    ).all()

    sessoes: dict[tuple[int, int], int] = defaultdict(int)
    capacidade: dict[tuple[int, int], int] = defaultdict(int)
    reservas: dict[tuple[int, int], int] = defaultdict(int)
    for inicia_em, cap, ativas in linhas:
        local = inicia_em.astimezone(FUSO)
        chave = ((local.weekday() + 1) % 7, local.hour)
        sessoes[chave] += 1
        capacidade[chave] += int(cap)
        reservas[chave] += int(ativas)

    celulas = [
        CelulaDeHorario(
            dia_semana=dia,
            hora=hora,
            sessoes=sessoes[(dia, hora)],
            capacidade=capacidade[(dia, hora)],
            reservas=reservas[(dia, hora)],
        )
        for dia, hora in sorted(sessoes, key=lambda c: (_ordem_do_dia(c[0]), c[1]))
    ]

    # `horas_do_dia` já devolve () para dia fechado; dia sem linha de
    # configuração cai no .get abaixo. Os dois viram [] — "fechado".
    configuracao = list(db.execute(select(HorarioFuncionamento)).scalars())
    atendiveis = {c.dia_semana: sorted(t.hour for t in horas_do_dia(c)) for c in configuracao}
    dias = {c.dia_semana for c in configuracao if c.aberto} | {d for d, _ in sessoes}
    horas = {h for horas_dia in atendiveis.values() for h in horas_dia} | {
        hora for _, hora in sessoes
    }

    eixo_dias = sorted(dias, key=_ordem_do_dia)
    return Horarios(
        dias=eixo_dias,
        horas=sorted(horas),
        horas_por_dia={dia: atendiveis.get(dia, []) for dia in eixo_dias},
        celulas=celulas,
    )


@dataclass(frozen=True)
class Presenca:
    """O que aconteceu com as reservas das sessões do período.

    Universo: TODAS as reservas (inclusive canceladas) das sessões não
    canceladas que começam no período. Cada reserva cai em exatamente uma
    categoria:

      presentes                status presente.
      faltas_justificadas      status falta, com `justificada` — julgamento
                               da recepção, nunca inferido pelo sistema (P4).
      faltas_nao_justificadas  status falta, sem justificativa.
      sem_registro             agendada ou confirmada numa sessão que JÁ
                               COMEÇOU: a aula passou e ninguém marcou nem
                               presença nem falta.
      a_realizar               agendada ou confirmada numa sessão que ainda
                               não começou. Não é pendência, é agenda.
      canceladas               status cancelada. A vaga voltou ao pool.

    ── COMPARECIMENTO ───────────────────────────────────────────────────────

        comparecimento = presentes ÷ (presentes + faltas)

    com faltas = justificadas + não justificadas; 0% se o denominador é 0.

    POR QUE FALTA CONTA NA OCUPAÇÃO MAS NÃO NO COMPARECIMENTO: são perguntas
    diferentes. Ocupação pergunta "quanto do lugar oferecido foi vendido" — o
    lugar de quem faltou ficou reservado e ninguém mais pôde usá-lo, então
    está ocupado. Comparecimento pergunta "de quem tinha aula, quantos
    vieram" — e quem faltou não veio. A mesma falta conta como ocupada num e
    como ausência no outro, sem contradição.

    POR QUE `sem_registro` EXISTE E FICA FORA DO DENOMINADOR: quem marca
    presença é a recepção, e se ela não está no balcão nas primeiras horas
    ninguém registra nada (docs/premissas.md, P8 — risco operacional). Contar
    essas reservas como presença inventaria comparecimento; contá-las como
    falta inventaria ausência. Deixá-las fora, e mostrá-las à parte, faz o
    percentual falar só do que foi registrado e torna visível o tamanho do
    buraco — em vez de o comparecimento mentir em silêncio.

    Canceladas e a_realizar também ficam fora: a aula não aconteceu para
    aquela reserva, ou ainda não aconteceu.
    """

    presentes: int
    faltas_justificadas: int
    faltas_nao_justificadas: int
    sem_registro: int
    a_realizar: int
    canceladas: int

    @property
    def comparecimento_percentual(self) -> int:
        faltas = self.faltas_justificadas + self.faltas_nao_justificadas
        return _percentual(self.presentes, self.presentes + faltas)


_SEM_REGISTRO_AINDA = (StatusReserva.AGENDADA, StatusReserva.CONFIRMADA)


def _presenca(db: DbSession, periodo: Periodo, agora: datetime) -> Presenca:
    # Uma consulta, uma linha: cada categoria é um COUNT ... FILTER.
    aguardando = Booking.status.in_(_SEM_REGISTRO_AINDA)
    linha = db.execute(
        select(
            func.count().filter(Booking.status == StatusReserva.PRESENTE),
            func.count().filter(
                Booking.status == StatusReserva.FALTA, Booking.justificada.is_(True)
            ),
            func.count().filter(
                Booking.status == StatusReserva.FALTA, Booking.justificada.is_(False)
            ),
            func.count().filter(aguardando, Session.inicia_em < agora),
            func.count().filter(aguardando, Session.inicia_em >= agora),
            func.count().filter(Booking.status == StatusReserva.CANCELADA),
        )
        .select_from(Booking)
        .join(Session, Session.id == Booking.session_id)
        .where(*_filtro_sessoes(periodo.inicio, periodo.fim))
    ).one()
    presentes, justificadas, nao_justificadas, sem_registro, a_realizar, canceladas = linha
    return Presenca(
        presentes=int(presentes),
        faltas_justificadas=int(justificadas),
        faltas_nao_justificadas=int(nao_justificadas),
        sem_registro=int(sem_registro),
        a_realizar=int(a_realizar),
        canceladas=int(canceladas),
    )


@dataclass(frozen=True)
class OrigemNoPeriodo:
    """De onde vieram as reservas que ocupam lugar no período.

    Universo: reservas NÃO canceladas das sessões não canceladas do período,
    contadas por `origem` (recorrente, avulsa, reposição, remarcação). Falta
    conta — ocupou o lugar. Cancelada não conta — devolveu.

    É o indicador que testa a hipótese P10 (reposição como causa do
    overbooking): quanto da agenda é reposição, agora que ela ocupa vaga como
    qualquer outra reserva. Sempre as quatro origens, na ordem do enum, com
    zero quando não houver.
    """

    origem: OrigemReserva
    reservas: int


def _origens(db: DbSession, periodo: Periodo) -> list[OrigemNoPeriodo]:
    contagem: dict[OrigemReserva, int] = {
        origem: int(quantidade)
        for origem, quantidade in db.execute(
            select(Booking.origem, func.count())
            .select_from(Booking)
            .join(Session, Session.id == Booking.session_id)
            .where(
                *_filtro_sessoes(periodo.inicio, periodo.fim),
                Booking.status != StatusReserva.CANCELADA,
            )
            .group_by(Booking.origem)
        ).all()
    }
    return [OrigemNoPeriodo(origem=o, reservas=contagem.get(o, 0)) for o in OrigemReserva]


@dataclass(frozen=True)
class Analise:
    """Os indicadores do período, todos sobre o mesmo recorte.

      receita          dinheiro que entrou (regime de caixa) e a série no tempo.
      formas_pagamento como ele entrou.
      servicos         movimento por serviço, do mais reservado ao menos.
      ocupacao         a mesma `TaxaDeOcupacao` do painel, sobre o período.
      horarios         mapa de calor dia por hora.
      presenca         o que aconteceu com as reservas, e o comparecimento.
      origens          de onde vieram as reservas.

    Sessões consideradas em todos os indicadores de agenda: começam no
    período (dia inteiro no fuso do studio) e não foram canceladas.
    """

    periodo: Periodo
    receita: Receita
    formas_pagamento: list[FormaDePagamento]
    servicos: list[ServicoNoPeriodo]
    ocupacao: TaxaDeOcupacao
    horarios: Horarios
    presenca: Presenca
    origens: list[OrigemNoPeriodo]


def analise(db: DbSession, meses: int, *, agora: datetime | None = None) -> Analise:
    """Análise dos últimos `meses` meses. `agora` fixo torna tudo testável.

    Datetime sem fuso é horário do STUDIO, como no resto do sistema — nunca
    do servidor.
    """
    if agora is None:
        agora = datetime.now(FUSO)
    elif agora.tzinfo is None:
        agora = agora.replace(tzinfo=FUSO)
    hoje = agora.astimezone(FUSO).date()
    periodo = periodo_de_analise(meses, hoje)

    pagamentos = _pagamentos_do_periodo(db, periodo)
    servicos = sorted(
        servicos_no_intervalo(db, periodo.inicio, periodo.fim),
        key=lambda s: (-s.reservas, s.nome),
    )

    return Analise(
        periodo=periodo,
        receita=_receita(pagamentos, periodo, hoje),
        formas_pagamento=_formas(pagamentos),
        servicos=servicos,
        ocupacao=taxa_de_ocupacao(db, periodo.inicio, periodo.fim),
        horarios=_horarios(db, periodo),
        presenca=_presenca(db, periodo, agora),
        origens=_origens(db, periodo),
    )
