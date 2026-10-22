"""Análise do período (GET /dashboard/analise).

Toda data aqui é FIXA, e o `agora` é passado explicitamente: a suíte não
pode depender do dia em que roda. O "hoje" de referência é uma quinta-feira,
15/10/2026, ao meio-dia em São Paulo.

Os casos de fuso são regressão de verdade: pagamento das 23:30 de 31/08 em
São Paulo já é 01/09 em UTC, e a sessão das 08:00 é 11:00 em UTC. Agrupar
pelo relógio do banco joga o dinheiro no mês errado e a turma na hora errada.
"""

from datetime import UTC, date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.booking import Booking, OrigemReserva
from app.models.charge import Charge, FormaPagamento, StatusCobranca, TipoCobranca
from app.models.configuracao import HorarioFuncionamento
from app.models.patient import Patient
from app.models.session import Session as Sessao
from app.models.user import Papel, User
from app.services import booking_service, dashboard_service, session_service
from app.services.schedule_service import FUSO
from tests.conftest import (
    auth,
    criar_configuracao,
    criar_paciente,
    criar_servico,
    criar_sessao,
    criar_usuario,
    login,
)

#: Quinta-feira, 15/10/2026, 12:00 em São Paulo.
AGORA = datetime(2026, 10, 15, 12, 0, tzinfo=FUSO)
HOJE = AGORA.date()


def _sp(ano: int, mes: int, dia: int, hora: int = 10, minuto: int = 0) -> datetime:
    """Instante em horário de São Paulo."""
    return datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO)


def _cobranca(
    db: Session,
    paciente: Patient,
    *,
    valor: int,
    pago_em: datetime | None,
    tipo: TipoCobranca = TipoCobranca.AVULSA,
    status: StatusCobranca = StatusCobranca.PAGO,
    forma: FormaPagamento | None = FormaPagamento.PIX,
) -> Charge:
    cobranca = Charge(
        patient_id=paciente.id,
        tipo=tipo,
        descricao=f"Cobrança de teste {tipo.value}",
        valor_centavos=valor,
        vencimento=(pago_em or AGORA).date(),
        status=status,
        pago_em=pago_em,
        forma_pagamento=forma,
    )
    db.add(cobranca)
    db.flush()
    return cobranca


def _reservar(
    db: Session,
    sessao: Sessao,
    criado_por: User,
    nome: str,
    *,
    origem: OrigemReserva = OrigemReserva.AVULSA,
    substitui: Booking | None = None,
    paciente: Patient | None = None,
) -> Booking:
    return booking_service.criar(
        db,
        session_id=sessao.id,
        patient_id=(paciente or criar_paciente(db, nome)).id,
        criado_por_id=criado_por.id,
        origem=origem,
        substitui_booking_id=substitui.id if substitui else None,
    )


def _analise(db: Session, meses: int = 3, agora: datetime = AGORA) -> dashboard_service.Analise:
    return dashboard_service.analise(db, meses, agora=agora)


# ── a) período ──────────────────────────────────────────────────────────────


class TestPeriodoDeAnalise:
    def test_um_mes_e_o_mes_inteiro_por_semana(self) -> None:
        p = dashboard_service.periodo_de_analise(1, date(2026, 10, 15))

        assert (p.inicio, p.fim) == (date(2026, 10, 1), date(2026, 10, 31))
        assert p.meses == 1
        assert p.granularidade == "semana"

    def test_tres_meses_por_mes(self) -> None:
        p = dashboard_service.periodo_de_analise(3, date(2026, 10, 15))

        assert (p.inicio, p.fim) == (date(2026, 8, 1), date(2026, 10, 31))
        assert p.granularidade == "mes"

    def test_virada_de_ano(self) -> None:
        p = dashboard_service.periodo_de_analise(3, date(2026, 2, 10))

        assert (p.inicio, p.fim) == (date(2025, 12, 1), date(2026, 2, 28))

    def test_doze_meses(self) -> None:
        p = dashboard_service.periodo_de_analise(12, date(2026, 10, 15))

        assert (p.inicio, p.fim) == (date(2025, 11, 1), date(2026, 10, 31))
        assert p.granularidade == "mes"

    def test_hoje_no_dia_31_nao_estoura(self) -> None:
        """date(2026, 2, 31) levantaria ValueError — aritmética é por índice."""
        p = dashboard_service.periodo_de_analise(2, date(2026, 3, 31))

        assert (p.inicio, p.fim) == (date(2026, 2, 1), date(2026, 3, 31))

    def test_fevereiro_bissexto(self) -> None:
        p = dashboard_service.periodo_de_analise(1, date(2028, 2, 10))

        assert p.fim == date(2028, 2, 29)

    @pytest.mark.parametrize("meses", [0, 13, -1])
    def test_fora_de_1_a_12_e_erro(self, meses: int) -> None:
        with pytest.raises(ValueError):
            dashboard_service.periodo_de_analise(meses, date(2026, 10, 15))


# ── b) formas de pagamento ──────────────────────────────────────────────────


class TestFormasDePagamento:
    def test_so_pago_no_periodo_conta_e_ordena(self, db: Session) -> None:
        p = criar_paciente(db, "Pagante")
        _cobranca(db, p, valor=10_000, pago_em=_sp(2026, 9, 10), forma=FormaPagamento.PIX)
        _cobranca(db, p, valor=5_000, pago_em=_sp(2026, 10, 1), forma=FormaPagamento.PIX)
        _cobranca(db, p, valor=30_000, pago_em=_sp(2026, 8, 20), forma=FormaPagamento.DINHEIRO)
        _cobranca(db, p, valor=20_000, pago_em=_sp(2026, 9, 5), forma=FormaPagamento.CREDITO)
        _cobranca(db, p, valor=10_000, pago_em=_sp(2026, 10, 2), forma=FormaPagamento.CREDITO)
        _cobranca(db, p, valor=7_000, pago_em=_sp(2026, 10, 3), forma=None)
        # Nada disto é receita do período:
        _cobranca(db, p, valor=99_900, pago_em=None, status=StatusCobranca.PENDENTE)
        _cobranca(
            db,
            p,
            valor=88_800,
            pago_em=None,
            status=StatusCobranca.CANCELADO,
            forma=FormaPagamento.DINHEIRO,
        )
        _cobranca(db, p, valor=77_700, pago_em=_sp(2026, 7, 20), forma=FormaPagamento.DINHEIRO)

        a = _analise(db)

        assert [(f.forma, f.pagamentos, f.valor_centavos) for f in a.formas_pagamento] == [
            (FormaPagamento.CREDITO, 2, 30_000),
            (FormaPagamento.PIX, 2, 15_000),
            (FormaPagamento.DINHEIRO, 1, 30_000),
            (None, 1, 7_000),
        ]
        assert a.receita.recebido_centavos == 82_000
        assert a.receita.pagamentos == 6
        assert sum(f.valor_centavos for f in a.formas_pagamento) == a.receita.recebido_centavos

    def test_sem_pagamento_nao_ha_forma(self, db: Session) -> None:
        p = criar_paciente(db, "Devedor")
        _cobranca(db, p, valor=10_000, pago_em=None, status=StatusCobranca.PENDENTE)

        a = _analise(db)

        assert a.formas_pagamento == []
        assert a.receita.recebido_centavos == 0


# ── c) regressão de fuso ────────────────────────────────────────────────────


class TestFuso:
    def test_pagamento_das_23h30_de_31_08_e_de_agosto(self, db: Session) -> None:
        p = criar_paciente(db, "Pagou Tarde")
        pago_em = _sp(2026, 8, 31, 23, 30)
        assert pago_em.astimezone(UTC).date() == date(2026, 9, 1), "premissa do teste"
        _cobranca(db, p, valor=12_345, pago_em=pago_em)

        serie = _analise(db).receita.serie

        assert serie[0].inicio == date(2026, 8, 1)
        assert serie[0].recebido_centavos == 12_345
        assert serie[1].recebido_centavos == 0

    def test_pagamento_das_23h30_de_31_07_fica_fora_do_periodo(self, db: Session) -> None:
        """Em UTC já é 01/08 — mas em São Paulo foi julho."""
        p = criar_paciente(db, "Pagou em Julho")
        _cobranca(db, p, valor=5_000, pago_em=_sp(2026, 7, 31, 23, 30))

        a = _analise(db)

        assert a.receita.recebido_centavos == 0
        assert a.formas_pagamento == []

    def test_sessao_das_8h_e_hora_8_no_dia_certo(self, db: Session, instrutor: User) -> None:
        servico = criar_servico(db, nome="Pilates Fuso")
        # Segunda 14/09 08:00 em SP = 11:00 UTC.
        criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 14), hora=8)
        # Sábado 19/09 21:00 em SP = domingo 00:00 UTC.
        criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 19), hora=21)

        h = _analise(db).horarios

        assert [(c.dia_semana, c.hora) for c in h.celulas] == [(1, 8), (6, 21)]


# ── d) série de receita ─────────────────────────────────────────────────────


class TestSerieDeReceita:
    def test_serie_mensal_com_tipos(self, db: Session) -> None:
        p = criar_paciente(db, "Mensalista")
        _cobranca(db, p, valor=30_000, pago_em=_sp(2026, 8, 5), tipo=TipoCobranca.MENSALIDADE)
        _cobranca(db, p, valor=9_000, pago_em=_sp(2026, 8, 6), tipo=TipoCobranca.PACOTE)
        _cobranca(db, p, valor=1_000, pago_em=_sp(2026, 8, 7), tipo=TipoCobranca.AVULSA)
        _cobranca(db, p, valor=20_000, pago_em=_sp(2026, 9, 5), tipo=TipoCobranca.MENSALIDADE)
        _cobranca(db, p, valor=5_000, pago_em=_sp(2026, 10, 2), tipo=TipoCobranca.AVULSA)

        serie = _analise(db).receita.serie

        assert [(b.inicio, b.fim) for b in serie] == [
            (date(2026, 8, 1), date(2026, 8, 31)),
            (date(2026, 9, 1), date(2026, 9, 30)),
            (date(2026, 10, 1), date(2026, 10, 31)),
        ]
        assert [b.recebido_centavos for b in serie] == [40_000, 20_000, 5_000]
        assert serie[0].por_tipo == {
            TipoCobranca.MENSALIDADE: 30_000,
            TipoCobranca.PACOTE: 9_000,
            TipoCobranca.AVULSA: 1_000,
        }
        # As três chaves sempre presentes, mesmo zeradas.
        assert serie[1].por_tipo == {
            TipoCobranca.MENSALIDADE: 20_000,
            TipoCobranca.PACOTE: 0,
            TipoCobranca.AVULSA: 0,
        }
        assert [b.em_andamento for b in serie] == [False, False, True]

    def test_doze_meses_sem_balde_futuro(self, db: Session) -> None:
        serie = _analise(db, meses=12).receita.serie

        assert len(serie) == 12
        assert serie[0].inicio == date(2025, 11, 1)
        assert serie[-1].inicio == date(2026, 10, 1)
        assert all(b.inicio <= HOJE for b in serie)
        assert [b.em_andamento for b in serie].count(True) == 1

    def test_serie_semanal_comeca_na_segunda_e_nao_tem_futuro(self, db: Session) -> None:
        """Outubro/2026 começa numa quinta; hoje é quinta, 15."""
        serie = _analise(db, meses=1).receita.serie

        assert [(b.inicio, b.fim) for b in serie] == [
            (date(2026, 10, 1), date(2026, 10, 4)),  # recortada ao mês
            (date(2026, 10, 5), date(2026, 10, 11)),
            (date(2026, 10, 12), date(2026, 10, 18)),  # contém hoje
        ]
        assert all(b.inicio.weekday() == 0 for b in serie[1:])
        assert [b.em_andamento for b in serie] == [False, False, True]

    def test_serie_semanal_no_fim_do_mes_recorta_a_ultima(self, db: Session) -> None:
        p = criar_paciente(db, "Semanal")
        _cobranca(db, p, valor=1_000, pago_em=_sp(2026, 10, 4, 23, 30))  # domingo
        _cobranca(db, p, valor=2_000, pago_em=_sp(2026, 10, 5, 0, 10))  # segunda
        _cobranca(db, p, valor=4_000, pago_em=_sp(2026, 10, 31, 9))

        a = _analise(db, meses=1, agora=_sp(2026, 10, 31, 18))
        serie = a.receita.serie

        assert a.periodo.granularidade == "semana"
        assert [(b.inicio, b.fim) for b in serie] == [
            (date(2026, 10, 1), date(2026, 10, 4)),
            (date(2026, 10, 5), date(2026, 10, 11)),
            (date(2026, 10, 12), date(2026, 10, 18)),
            (date(2026, 10, 19), date(2026, 10, 25)),
            (date(2026, 10, 26), date(2026, 10, 31)),  # recortada ao mês
        ]
        assert [b.recebido_centavos for b in serie] == [1_000, 2_000, 0, 0, 4_000]
        assert [b.em_andamento for b in serie] == [False, False, False, False, True]


# ── e) serviços ─────────────────────────────────────────────────────────────


class TestServicosNoPeriodo:
    def test_ranking_e_quem_entra(self, db: Session, instrutor: User, recepcao: User) -> None:
        alfa = criar_servico(db, nome="Alfa Pilates")
        beta = criar_servico(db, nome="Beta Fisio")
        gama = criar_servico(db, nome="Gama Antigo")
        zeta = criar_servico(db, nome="Zeta Zerado")
        omega = criar_servico(db, nome="Omega Desativado")
        omega.ativo = False

        a1 = criar_sessao(db, instrutor, servico=alfa, dia=date(2026, 9, 14), hora=8)
        a2 = criar_sessao(db, instrutor, servico=alfa, dia=date(2026, 9, 15), hora=8)
        for i in range(2):
            _reservar(db, a1, recepcao, f"A1-{i}")
            _reservar(db, a2, recepcao, f"A2-{i}")
        cancelada = _reservar(db, a2, recepcao, "A2-cancelou")
        booking_service.cancelar(db, cancelada.id)

        b1 = criar_sessao(db, instrutor, servico=beta, dia=date(2026, 9, 16), hora=8)
        _reservar(db, b1, recepcao, "B1")
        # Turma cancelada: nem a sessão nem as reservas dela contam.
        b_morta = criar_sessao(db, instrutor, servico=beta, dia=date(2026, 9, 17), hora=8)
        _reservar(db, b_morta, recepcao, "BM-1")
        _reservar(db, b_morta, recepcao, "BM-2")
        session_service.cancelar(db, b_morta.id, motivo="Instrutora doente")

        # Inativo, mas teve sessão no período: entra.
        g1 = criar_sessao(db, instrutor, servico=gama, dia=date(2026, 9, 18), hora=8)
        _reservar(db, g1, recepcao, "G1")
        gama.ativo = False
        db.flush()

        servicos = _analise(db).servicos

        assert [s.nome for s in servicos] == [
            "Alfa Pilates",
            "Beta Fisio",
            "Gama Antigo",
            "Zeta Zerado",
        ], "Omega (inativo sem sessão) fica fora; empate por nome"
        por_nome = {s.nome: s for s in servicos}
        assert (por_nome["Alfa Pilates"].sessoes, por_nome["Alfa Pilates"].reservas) == (2, 4)
        assert por_nome["Alfa Pilates"].ocupacao_percentual == 50
        assert (por_nome["Beta Fisio"].sessoes, por_nome["Beta Fisio"].reservas) == (1, 1)
        assert por_nome["Beta Fisio"].ocupacao_percentual == 25
        assert por_nome["Zeta Zerado"].sessoes == 0
        assert por_nome["Zeta Zerado"].ocupacao_percentual == 0
        assert zeta.id == por_nome["Zeta Zerado"].service_id

    def test_sessao_fora_do_periodo_nao_conta(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        servico = criar_servico(db, nome="Fora")
        antes = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 7, 31), hora=8)
        _reservar(db, antes, recepcao, "Julho")

        (s,) = [s for s in _analise(db).servicos if s.nome == "Fora"]

        assert (s.sessoes, s.reservas) == (0, 0)

    def test_estatisticas_do_mes_continuam_so_com_ativos(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """O agregador inclui inativo com sessão; a tela de Atividades não."""
        servico = criar_servico(db, nome="Desativado no Mes")
        sessao = criar_sessao(db, instrutor, servico=servico, dia=date.today(), hora=8)
        _reservar(db, sessao, recepcao, "Mes")
        servico.ativo = False
        db.flush()

        nomes = {s.nome for s in dashboard_service.estatisticas_de_servicos(db)}

        assert "Desativado no Mes" not in nomes


# ── f) horários ─────────────────────────────────────────────────────────────


class TestHorarios:
    def test_soma_semanas_e_eixos_da_configuracao(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Horario")
        seg1 = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 14), hora=8)
        seg2 = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 21), hora=8)
        criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 16), hora=18)
        for i in range(3):
            _reservar(db, seg1, recepcao, f"S1-{i}")
        _reservar(db, seg2, recepcao, "S2-0")
        cancelou = _reservar(db, seg2, recepcao, "S2-cancelou")
        booking_service.cancelar(db, cancelou.id)
        morta = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 15), hora=10)
        session_service.cancelar(db, morta.id)

        h = _analise(db).horarios

        assert [
            (c.dia_semana, c.hora, c.sessoes, c.capacidade, c.reservas, c.ocupacao_percentual)
            for c in h.celulas
        ] == [
            (1, 8, 2, 8, 4, 50),
            (3, 18, 1, 4, 0, 0),
        ]
        assert h.dias == [1, 2, 3, 4, 5, 6], "segunda primeiro; domingo fechado e sem sessão"
        assert h.horas == [6, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 19, 20]
        assert 12 not in h.horas and 13 not in h.horas, "a pausa não vira coluna"
        assert h.horas_por_dia == {dia: h.horas for dia in [1, 2, 3, 4, 5, 6]}

    def test_sabado_ate_meio_dia_fecha_a_tarde_so_no_sabado(self, db: Session) -> None:
        """A janela é por dia: a união `horas` não diz que sábado 15:00 é atendível."""
        criar_configuracao(db)
        sabado = db.get(HorarioFuncionamento, 6)
        assert sabado is not None
        sabado.hora_fechamento = time(12, 0)
        sabado.pausa_inicio = None
        sabado.pausa_fim = None
        db.flush()

        h = _analise(db).horarios

        assert h.horas == [6, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 19, 20], "seg-sex seguem até 21"
        assert h.horas_por_dia[6] == [6, 7, 8, 9, 10, 11]
        assert not set(h.horas_por_dia[6]) & {14, 15, 16, 17, 18, 19, 20}, (
            "sábado à tarde é fechado, não horário ocioso"
        )
        assert h.horas_por_dia[1] == h.horas

    def test_dia_fechado_com_sessao_aparece_sem_horas_atendiveis(
        self, db: Session, instrutor: User
    ) -> None:
        """Domingo está fechado na configuração, mas teve turma (ou a config mudou depois)."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Domingo Excecao")
        criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 20), hora=10)  # domingo

        h = _analise(db).horarios

        assert h.dias == [1, 2, 3, 4, 5, 6, 0]
        assert h.horas_por_dia[0] == [], "a célula com sessão aparece; o resto do domingo é fechado"
        assert [(c.dia_semana, c.hora) for c in h.celulas] == [(0, 10)]
        assert set(h.horas_por_dia) == set(h.dias), "uma entrada para cada dia do eixo"

    def test_sem_configuracao_deriva_das_celulas(self, db: Session, instrutor: User) -> None:
        servico = criar_servico(db, nome="Sem Config")
        criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 19), hora=9)  # sábado
        criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 14), hora=15)  # segunda
        criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 20), hora=10)  # domingo

        h = _analise(db).horarios

        assert h.dias == [1, 6, 0], "domingo por último"
        assert h.horas == [9, 10, 15]
        assert [(c.dia_semana, c.hora) for c in h.celulas] == [(1, 15), (6, 9), (0, 10)]
        assert h.horas_por_dia == {1: [], 6: [], 0: []}, "sem configuração, nada é atendível"

    def test_sem_configuracao_e_sem_sessao_fica_vazio(self, db: Session) -> None:
        h = _analise(db).horarios

        assert (h.dias, h.horas, h.horas_por_dia, h.celulas) == ([], [], {}, [])


# ── g) presença ─────────────────────────────────────────────────────────────


class TestPresenca:
    def test_cada_categoria(self, db: Session, instrutor: User, recepcao: User) -> None:
        servico = criar_servico(db, nome="Presenca")
        s1 = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 10, 5), hora=8)
        s2 = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 10, 14), hora=8)
        s3 = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 10, 20), hora=8)
        # Hoje: uma antes do meio-dia (já começou), outra depois.
        hoje_cedo = criar_sessao(db, instrutor, servico=servico, dia=HOJE, hora=9)
        hoje_tarde = criar_sessao(db, instrutor, servico=servico, dia=HOJE, hora=14)

        for nome in ("P1", "P2"):
            booking_service.registrar_presenca(db, _reservar(db, s1, recepcao, nome).id)
        booking_service.registrar_falta(db, _reservar(db, s1, recepcao, "FJ").id, justificada=True)
        _reservar(db, s1, recepcao, "Esquecido")  # passado, agendada → sem_registro

        booking_service.registrar_presenca(db, _reservar(db, s2, recepcao, "P3").id)
        booking_service.registrar_falta(db, _reservar(db, s2, recepcao, "FNJ").id)
        booking_service.confirmar(db, _reservar(db, s2, recepcao, "Confirmou").id)
        booking_service.cancelar(db, _reservar(db, s2, recepcao, "Cancelou").id)

        _reservar(db, s3, recepcao, "Futuro A")
        booking_service.confirmar(db, _reservar(db, s3, recepcao, "Futuro B").id)

        _reservar(db, hoje_cedo, recepcao, "Hoje Cedo")
        _reservar(db, hoje_tarde, recepcao, "Hoje Tarde")

        # Turma cancelada sai de tudo, inclusive de "canceladas".
        morta = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 10, 6), hora=8)
        _reservar(db, morta, recepcao, "Turma Cancelada")
        session_service.cancelar(db, morta.id)

        p = _analise(db).presenca

        assert p.presentes == 3
        assert p.faltas_justificadas == 1
        assert p.faltas_nao_justificadas == 1
        assert p.sem_registro == 3, "Esquecido, Confirmou e Hoje Cedo"
        assert p.a_realizar == 3, "Futuro A, Futuro B e Hoje Tarde"
        assert p.canceladas == 1
        assert p.comparecimento_percentual == 60, "3 ÷ (3 + 2); sem_registro fora"

    def test_arredondamento(self, db: Session, instrutor: User, recepcao: User) -> None:
        servico = criar_servico(db, nome="Arredonda")
        s = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 10, 5), hora=8)
        booking_service.registrar_presenca(db, _reservar(db, s, recepcao, "A").id)
        booking_service.registrar_presenca(db, _reservar(db, s, recepcao, "B").id)
        booking_service.registrar_falta(db, _reservar(db, s, recepcao, "C").id)

        assert _analise(db).presenca.comparecimento_percentual == 67

    def test_denominador_zero_e_zero(self, db: Session, instrutor: User, recepcao: User) -> None:
        servico = criar_servico(db, nome="Ninguem Marcou")
        s = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 10, 5), hora=8)
        _reservar(db, s, recepcao, "Sem Registro")

        p = _analise(db).presenca

        assert p.sem_registro == 1
        assert p.comparecimento_percentual == 0


# ── h) origens ──────────────────────────────────────────────────────────────


class TestOrigens:
    def test_sempre_as_quatro_em_ordem(self, db: Session) -> None:
        origens = _analise(db).origens

        assert [(o.origem, o.reservas) for o in origens] == [
            (OrigemReserva.RECORRENTE, 0),
            (OrigemReserva.AVULSA, 0),
            (OrigemReserva.REPOSICAO, 0),
            (OrigemReserva.REMARCACAO, 0),
        ]

    def test_conta_por_origem(self, db: Session, instrutor: User, recepcao: User) -> None:
        servico = criar_servico(db, nome="Origens")
        s1 = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 14), hora=8)
        s2 = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 9, 15), hora=8)

        faltou = _reservar(db, s1, recepcao, "Faltou")
        booking_service.registrar_falta(db, faltou.id, justificada=True)
        cancelou = _reservar(db, s1, recepcao, "Cancelou")
        booking_service.cancelar(db, cancelou.id)
        _reservar(db, s1, recepcao, "Fixo", origem=OrigemReserva.RECORRENTE)
        mudou = _reservar(db, s1, recepcao, "Mudou")
        booking_service.remarcar(db, mudou.id, nova_session_id=s2.id, criado_por_id=recepcao.id)

        paciente_que_faltou = db.get(Patient, faltou.patient_id)
        assert paciente_que_faltou is not None
        _reservar(
            db,
            s2,
            recepcao,
            "Faltou",
            origem=OrigemReserva.REPOSICAO,
            substitui=faltou,
            paciente=paciente_que_faltou,
        )

        contagem = {o.origem: o.reservas for o in _analise(db).origens}

        assert contagem == {
            OrigemReserva.RECORRENTE: 1,
            OrigemReserva.AVULSA: 1,  # a falta conta; a cancelada e a remarcada não
            OrigemReserva.REPOSICAO: 1,
            OrigemReserva.REMARCACAO: 1,
        }


# ── ocupação ────────────────────────────────────────────────────────────────


class TestOcupacaoDoPeriodo:
    def test_reutiliza_a_taxa_do_painel(self, db: Session, instrutor: User, recepcao: User) -> None:
        servico = criar_servico(db, nome="Ocupa")
        s = criar_sessao(db, instrutor, servico=servico, dia=date(2026, 8, 3), hora=8)
        _reservar(db, s, recepcao, "Um")
        _reservar(db, s, recepcao, "Dois")
        outro_instrutor = criar_usuario(db, Papel.INSTRUTOR, email="outro@example.com")
        criar_sessao(db, outro_instrutor, servico=servico, dia=date(2026, 8, 3), hora=8)

        o = _analise(db).ocupacao

        assert (o.reservas_ativas, o.capacidade_ofertada, o.percentual) == (2, 8, 25)
        assert o == dashboard_service.taxa_de_ocupacao(db, date(2026, 8, 1), date(2026, 10, 31))


# ── i) API ──────────────────────────────────────────────────────────────────

_CHAVES = {
    "periodo",
    "receita",
    "formas_pagamento",
    "servicos",
    "ocupacao",
    "horarios",
    "presenca",
    "origens",
}


class TestApiDaAnalise:
    def test_admin_recebe_o_contrato(self, client: TestClient, db: Session, admin: User) -> None:
        criar_configuracao(db)
        t = login(client, admin.email)

        r = client.get("/api/v1/dashboard/analise", headers=auth(t))

        assert r.status_code == 200, r.text
        corpo = r.json()
        assert set(corpo) == _CHAVES
        assert corpo["periodo"]["meses"] == 3, "sem parâmetro usa 3 meses"
        assert corpo["periodo"]["granularidade"] == "mes"
        assert set(corpo["periodo"]) == {"inicio", "fim", "meses", "granularidade"}
        assert set(corpo["receita"]) == {"recebido_centavos", "pagamentos", "serie"}
        balde = corpo["receita"]["serie"][-1]
        assert set(balde) == {"inicio", "fim", "recebido_centavos", "por_tipo", "em_andamento"}
        assert set(balde["por_tipo"]) == {"mensalidade", "pacote", "avulsa"}
        assert balde["em_andamento"] is True
        assert set(corpo["ocupacao"]) == {
            "percentual",
            "reservas_ativas",
            "capacidade_ofertada",
            "formula",
        }
        assert set(corpo["horarios"]) == {"dias", "horas", "horas_por_dia", "celulas"}
        assert corpo["horarios"]["dias"] == [1, 2, 3, 4, 5, 6]
        # No JSON a chave do dia vira string.
        assert set(corpo["horarios"]["horas_por_dia"]) == {"1", "2", "3", "4", "5", "6"}
        assert 12 not in corpo["horarios"]["horas_por_dia"]["6"]
        assert set(corpo["presenca"]) == {
            "presentes",
            "faltas_justificadas",
            "faltas_nao_justificadas",
            "sem_registro",
            "a_realizar",
            "canceladas",
            "comparecimento_percentual",
        }
        assert [o["origem"] for o in corpo["origens"]] == [
            "recorrente",
            "avulsa",
            "reposicao",
            "remarcacao",
        ]

    def test_datas_e_formas_no_json(self, client: TestClient, db: Session, admin: User) -> None:
        p = criar_paciente(db, "Json")
        # Agora mesmo: a rota usa o relógio real, e o mês corrente sempre
        # está no período.
        _cobranca(db, p, valor=1_500, pago_em=datetime.now(FUSO), forma=None)
        t = login(client, admin.email)

        corpo = client.get("/api/v1/dashboard/analise", params={"meses": 1}, headers=auth(t)).json()

        assert corpo["periodo"]["granularidade"] == "semana"
        date.fromisoformat(corpo["periodo"]["inicio"])  # "YYYY-MM-DD"
        assert corpo["formas_pagamento"] == [
            {"forma": None, "pagamentos": 1, "valor_centavos": 1_500}
        ]

    def test_recepcao_nao_recebe_valores(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """Valores são só da proprietária — escondidos na API, não só na tela."""
        criar_configuracao(db)
        p = criar_paciente(db, "Sem Valores")
        _cobranca(db, p, valor=1_500, pago_em=datetime.now(FUSO), forma=None)
        t = login(client, recepcao.email)

        corpo = client.get("/api/v1/dashboard/analise", headers=auth(t)).json()

        assert set(corpo) == _CHAVES
        assert corpo["receita"] is None
        # A contagem fica: é a própria recepção que registra cada baixa.
        assert corpo["formas_pagamento"] == [
            {"forma": None, "pagamentos": 1, "valor_centavos": None}
        ]

    def test_admin_ve(self, client: TestClient, db: Session, admin: User) -> None:
        t = login(client, admin.email)

        assert client.get("/api/v1/dashboard/analise", headers=auth(t)).status_code == 200

    def test_instrutor_nao_ve(self, client: TestClient, db: Session, instrutor: User) -> None:
        t = login(client, instrutor.email)

        assert client.get("/api/v1/dashboard/analise", headers=auth(t)).status_code == 403

    @pytest.mark.parametrize("meses", [0, 13])
    def test_meses_fora_de_1_a_12_e_422(
        self, client: TestClient, db: Session, recepcao: User, meses: int
    ) -> None:
        t = login(client, recepcao.email)

        r = client.get("/api/v1/dashboard/analise", params={"meses": meses}, headers=auth(t))

        assert r.status_code == 422

    def test_sem_token_e_401(self, client: TestClient) -> None:
        assert client.get("/api/v1/dashboard/analise").status_code == 401
