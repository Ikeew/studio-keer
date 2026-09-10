"""Ciclo de cobrança e as datas que quebram em silêncio.

Bug de data raramente aparece no dia em que o código é escrito. Aparece em
abril, quando o dia 31 não existe; em fevereiro, quando o 29 não existe; e a
cada quatro anos, quando existe. Todos aqui.
"""

from datetime import date
from itertools import pairwise

import pytest

from app.models.enrollment import Enrollment
from app.services import ciclo_service


def matricula(dia_vencimento: int, inicio: date | None = None) -> Enrollment:
    """Matrícula solta, sem banco — o ciclo é cálculo puro."""
    return Enrollment(
        patient_id=1,
        service_id=1,
        professional_id=1,
        vigencia_inicio=inicio or date(2026, 1, dia_vencimento),
        valor_mensal_centavos=20_000,
        dia_vencimento=dia_vencimento,
    )


class TestDiaSeguro:
    @pytest.mark.parametrize(
        ("ano", "mes", "dia", "esperado"),
        [
            (2026, 4, 31, date(2026, 4, 30)),  # abril tem 30
            (2026, 6, 31, date(2026, 6, 30)),
            (2026, 9, 31, date(2026, 9, 30)),
            (2026, 11, 31, date(2026, 11, 30)),
            (2026, 2, 31, date(2026, 2, 28)),  # fevereiro comum
            (2026, 2, 30, date(2026, 2, 28)),
            (2026, 2, 29, date(2026, 2, 28)),
            (2028, 2, 29, date(2028, 2, 29)),  # bissexto: o 29 EXISTE
            (2028, 2, 30, date(2028, 2, 29)),
            (2026, 1, 31, date(2026, 1, 31)),  # dia válido não é alterado
        ],
    )
    def test_encaixa_no_ultimo_dia_existente(
        self, ano: int, mes: int, dia: int, esperado: date
    ) -> None:
        assert ciclo_service.dia_seguro(ano, mes, dia) == esperado

    def test_2100_nao_e_bissexto(self) -> None:
        """Divisível por 100 e não por 400. Pega implementação ingênua."""
        assert ciclo_service.dia_seguro(2100, 2, 29) == date(2100, 2, 28)


class TestSomarMeses:
    def test_dia_31_atravessando_meses_de_30(self) -> None:
        assert ciclo_service.somar_meses(date(2026, 3, 31), 1) == date(2026, 4, 30)

    def test_dia_31_atravessando_fevereiro(self) -> None:
        assert ciclo_service.somar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)

    def test_dia_29_em_ano_bissexto(self) -> None:
        assert ciclo_service.somar_meses(date(2028, 1, 29), 1) == date(2028, 2, 29)

    def test_vira_o_ano(self) -> None:
        assert ciclo_service.somar_meses(date(2026, 12, 15), 1) == date(2027, 1, 15)

    def test_volta_um_mes(self) -> None:
        assert ciclo_service.somar_meses(date(2026, 3, 31), -1) == date(2026, 2, 28)


class TestCompetenciaPorAniversario:
    """Leitura (b): a competência vai do dia de aniversário à véspera do
    próximo. Ver docs/premissas.md (P2)."""

    def test_ciclo_do_meio_do_mes(self) -> None:
        c = ciclo_service.competencia_de(matricula(15), date(2026, 3, 20))

        assert c.inicio == date(2026, 3, 15)
        assert c.fim == date(2026, 4, 14)
        assert c.vencimento == date(2026, 3, 15)

    def test_data_antes_do_aniversario_cai_no_ciclo_anterior(self) -> None:
        """Dia 10 de março, vencendo dia 15: o ciclo é o de fevereiro."""
        c = ciclo_service.competencia_de(matricula(15), date(2026, 3, 10))

        assert c.inicio == date(2026, 2, 15)
        assert c.fim == date(2026, 3, 14)

    def test_no_proprio_dia_do_aniversario(self) -> None:
        c = ciclo_service.competencia_de(matricula(15), date(2026, 3, 15))

        assert c.inicio == date(2026, 3, 15)

    def test_dia_31_em_mes_de_30(self) -> None:
        """Quem começou dia 31 vence dia 30 em abril."""
        c = ciclo_service.competencia_de(matricula(31), date(2026, 4, 30))

        assert c.vencimento == date(2026, 4, 30)
        assert c.fim == date(2026, 5, 30)

    def test_dia_31_em_fevereiro(self) -> None:
        c = ciclo_service.competencia_de(matricula(31), date(2026, 2, 28))

        assert c.inicio == date(2026, 2, 28)
        assert c.fim == date(2026, 3, 30)

    def test_dia_29_em_fevereiro_bissexto(self) -> None:
        c = ciclo_service.competencia_de(matricula(29), date(2028, 2, 29))

        assert c.inicio == date(2028, 2, 29)

    def test_ciclos_nao_deixam_buraco_nem_sobrepoem(self) -> None:
        """Invariante: o fim de um ciclo é a véspera do início do seguinte.

        Vale para todo dia de vencimento, ao longo de dois anos — que é onde
        os meses curtos e o bissexto aparecem.
        """
        for dia in range(1, 32):
            m = matricula(dia)
            ciclos = ciclo_service.competencias_ate(m, date(2028, 1, 1))
            for anterior, seguinte in pairwise(ciclos):
                assert anterior.fim.toordinal() + 1 == seguinte.inicio.toordinal(), (
                    f"buraco ou sobreposição no dia {dia}: {anterior.rotulo} -> {seguinte.rotulo}"
                )

    def test_cada_ciclo_tem_chave_unica(self) -> None:
        """A chave identifica o ciclo na unicidade da cobrança."""
        for dia in (1, 15, 28, 29, 30, 31):
            ciclos = ciclo_service.competencias_ate(matricula(dia), date(2028, 1, 1))
            chaves = [c.chave for c in ciclos]
            assert len(chaves) == len(set(chaves)), f"chave repetida no dia {dia}"


class TestCompetenciasAte:
    def test_gera_um_ciclo_por_mes(self) -> None:
        m = matricula(10, inicio=date(2026, 1, 10))

        ciclos = ciclo_service.competencias_ate(m, date(2026, 6, 30))

        assert len(ciclos) == 6
        assert ciclos[0].inicio == date(2026, 1, 10)
        assert ciclos[-1].inicio == date(2026, 6, 10)

    def test_respeita_o_fim_da_vigencia(self) -> None:
        m = matricula(10, inicio=date(2026, 1, 10))
        m.vigencia_fim = date(2026, 3, 31)

        ciclos = ciclo_service.competencias_ate(m, date(2026, 12, 31))

        assert len(ciclos) == 3

    def test_matricula_futura_nao_gera_ciclo(self) -> None:
        m = matricula(10, inicio=date(2027, 1, 10))

        assert ciclo_service.competencias_ate(m, date(2026, 12, 31)) == []

    def test_dia_31_ao_longo_de_um_ano(self) -> None:
        """Doze ciclos, cada um vencendo no último dia possível do mês."""
        m = matricula(31, inicio=date(2026, 1, 31))

        ciclos = ciclo_service.competencias_ate(m, date(2026, 12, 31))

        vencimentos = [c.vencimento.day for c in ciclos]
        assert vencimentos == [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
