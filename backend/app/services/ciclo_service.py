"""Ciclo de cobrança — o ÚNICO lugar que sabe como um mês de mensalidade
começa e termina.

── A DECISÃO, E POR QUE ELA ESTÁ ISOLADA AQUI ───────────────────────────────

A cliente confirmou o VENCIMENTO: cada paciente vence no dia em que começou,
mês cheio, sem proporcional. Não confirmou a COMPETÊNCIA — o período que a
cobrança cobre. Duas leituras, para quem começou em 15/03:

    (a) Calendário   competência 01/03 a 31/03, vencimento dia 15
    (b) Aniversário  competência 15/03 a 14/04, vencimento dia 15

Adotamos **(b)**, e está registrado como premissa a confirmar
(docs/premissas.md, P2). É a leitura consistente com o que ela já respondeu:
se fosse calendário, quem entrasse dia 28 pagaria o mês inteiro por três dias
de aula — justamente o proporcional que ela disse não fazer.

Todo o resto do sistema chama estas funções em vez de calcular datas por
conta própria. Trocar para (a) é reescrever `competencia_de` e
`vencimento_de`; nada mais no código sabe que ciclo existe.

Este módulo NÃO decide a janela de reposição. São conceitos distintos que só
se parecem por usarem a palavra "mês" — ver `reposicao_service`.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date

from app.models.enrollment import Enrollment


def ultimo_dia_do_mes(ano: int, mes: int) -> int:
    return monthrange(ano, mes)[1]


def dia_seguro(ano: int, mes: int, dia: int) -> date:
    """Data existente mais próxima do dia pedido, dentro do mês.

    Quem começou dia 31 vence dia 30 em abril e 28 em fevereiro — ou 29 em
    ano bissexto. Sem isto, `date(2026, 4, 31)` levanta ValueError e a
    geração de cobranças quebra em abril, junho, setembro e novembro; e em
    fevereiro para quem começou dia 29, 30 ou 31.

    É bug silencioso: passa em todos os testes escritos em março.
    """
    return date(ano, mes, min(dia, ultimo_dia_do_mes(ano, mes)))


def somar_meses(referencia: date, meses: int) -> date:
    """Avança meses preservando o dia quando ele existe no mês de destino."""
    total = referencia.month - 1 + meses
    ano = referencia.year + total // 12
    mes = total % 12 + 1
    return dia_seguro(ano, mes, referencia.day)


@dataclass(frozen=True)
class Competencia:
    """Um ciclo de cobrança concreto de uma matrícula."""

    #: Primeiro dia coberto.
    inicio: date
    #: Último dia coberto (inclusive).
    fim: date
    #: Data de vencimento da cobrança deste ciclo.
    vencimento: date

    @property
    def rotulo(self) -> str:
        return f"{self.inicio:%d/%m/%Y} a {self.fim:%d/%m/%Y}"

    @property
    def chave(self) -> date:
        """Identidade do ciclo, usada na unicidade da cobrança.

        É a data de início: com ciclo por aniversário, dois ciclos da mesma
        matrícula nunca começam no mesmo dia.
        """
        return self.inicio


def _mes_seguinte(ano: int, mes: int) -> tuple[int, int]:
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def _competencia_do_mes(dia_vencimento: int, ano: int, mes: int) -> Competencia:
    """Ciclo que começa no aniversário dentro de (ano, mes).

    O avanço é feito sobre o MÊS NOMINAL, nunca somando à data já ajustada.
    Somar um mês a 28/02 (que era um "dia 31" encolhido) devolveria 28/03, e
    o dia 31 nunca mais voltaria — o ciclo travaria em fevereiro. Foi
    exatamente o que aconteceu, e o teste de doze meses pegou.
    """
    inicio = dia_seguro(ano, mes, dia_vencimento)
    prox_ano, prox_mes = _mes_seguinte(ano, mes)
    proximo_inicio = dia_seguro(prox_ano, prox_mes, dia_vencimento)
    fim = date.fromordinal(proximo_inicio.toordinal() - 1)
    # Vencimento no primeiro dia do ciclo: o paciente paga o mês adiantado,
    # que é o que "vence no dia em que começou" significa na prática.
    return Competencia(inicio=inicio, fim=fim, vencimento=inicio)


def competencia_de(matricula: Enrollment, em: date) -> Competencia:
    """O ciclo da matrícula que contém a data `em`.

    LEITURA (b) — aniversário. Trocar para calendário é mexer só aqui.
    """
    dia = matricula.dia_vencimento
    ciclo = _competencia_do_mes(dia, em.year, em.month)
    if ciclo.inicio > em:
        anterior = somar_meses(date(em.year, em.month, 1), -1)
        ciclo = _competencia_do_mes(dia, anterior.year, anterior.month)
    return ciclo


def competencias_ate(matricula: Enrollment, ate: date) -> list[Competencia]:
    """Todos os ciclos da matrícula, do início da vigência até `ate`.

    Usado pela geração de cobranças, que precisa cobrir também os ciclos
    passados que ainda não foram faturados.
    """
    limite_final = min(ate, matricula.vigencia_fim or ate)
    if matricula.vigencia_inicio > limite_final:
        return []

    dia = matricula.dia_vencimento
    primeiro = competencia_de(matricula, matricula.vigencia_inicio)
    ano, mes = primeiro.inicio.year, primeiro.inicio.month

    ciclos: list[Competencia] = []
    while True:
        ciclo = _competencia_do_mes(dia, ano, mes)
        if ciclo.inicio > limite_final:
            break
        ciclos.append(ciclo)
        ano, mes = _mes_seguinte(ano, mes)
    return ciclos
