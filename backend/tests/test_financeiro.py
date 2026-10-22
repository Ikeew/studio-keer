"""Cobranças: geração idempotente, vencido derivado, venda de pacote, RBAC."""

from datetime import date, time, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.charge import Charge, FormaPagamento, StatusCobranca, TipoCobranca
from app.models.service import ModeloCobranca
from app.models.user import User
from app.services import charge_service, package_service
from tests.conftest import (
    auth,
    criar_configuracao,
    criar_matricula,
    criar_paciente,
    criar_servico,
    login,
)


def _matricula(db: Session, instrutor: User, nome: str, inicio: date, valor: int = 20_000):
    servico = criar_servico(db, nome=f"Pilates {nome}")
    m = criar_matricula(
        db,
        criar_paciente(db, nome),
        instrutor,
        servico,
        inicio=inicio,
        horarios=[(1, time(8, 0))],
    )
    m.valor_mensal_centavos = valor
    db.flush()
    return m


class TestGeracaoDeMensalidades:
    def test_gera_um_ciclo_por_mes(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Mensal", date(2026, 1, 10))

        r = charge_service.gerar_mensalidades(db, ate=date(2026, 6, 30))

        assert r.criadas == 6

    def test_e_idempotente(self, db: Session, instrutor: User) -> None:
        """Rodar duas vezes não cobra o paciente duas vezes."""
        criar_configuracao(db)
        _matricula(db, instrutor, "Idem", date(2026, 1, 10))
        charge_service.gerar_mensalidades(db, ate=date(2026, 6, 30))
        antes = db.execute(select(func.count()).select_from(Charge)).scalar_one()

        r = charge_service.gerar_mensalidades(db, ate=date(2026, 6, 30))

        depois = db.execute(select(func.count()).select_from(Charge)).scalar_one()
        assert antes == depois
        assert r.criadas == 0
        assert r.ja_existentes == 6

    def test_execucao_parcial_pode_ser_repetida(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Parcial", date(2026, 1, 10))
        charge_service.gerar_mensalidades(db, ate=date(2026, 3, 31))

        r = charge_service.gerar_mensalidades(db, ate=date(2026, 6, 30))

        assert r.ja_existentes == 3
        assert r.criadas == 3

    def test_cada_paciente_vence_no_seu_dia(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Dia 5", date(2026, 1, 5))
        _matricula(db, instrutor, "Dia 22", date(2026, 1, 22))

        charge_service.gerar_mensalidades(db, ate=date(2026, 2, 28))

        dias = sorted({c.vencimento.day for c in db.execute(select(Charge)).scalars()})
        assert dias == [5, 22]

    def test_valor_e_snapshot_da_matricula(self, db: Session, instrutor: User) -> None:
        """Reajuste não altera cobrança já emitida."""
        criar_configuracao(db)
        m = _matricula(db, instrutor, "Snapshot", date(2026, 1, 10), valor=20_000)
        charge_service.gerar_mensalidades(db, ate=date(2026, 1, 31))

        m.valor_mensal_centavos = 30_000
        db.flush()

        cobranca = db.execute(select(Charge)).scalars().first()
        assert cobranca is not None
        assert cobranca.valor_centavos == 20_000


class TestDatasQueQuebram:
    """Os casos que só aparecem meses depois."""

    @pytest.mark.parametrize("dia", [29, 30, 31])
    def test_inicio_no_fim_do_mes_gera_doze_meses(
        self, db: Session, instrutor: User, dia: int
    ) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, f"Dia {dia}", date(2026, 1, dia))

        r = charge_service.gerar_mensalidades(db, ate=date(2026, 12, 31))

        assert r.criadas == 12, f"dia {dia} não gerou os 12 ciclos"

    def test_dia_31_vence_no_ultimo_dia_de_cada_mes(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Trinta e Um", date(2026, 1, 31))

        charge_service.gerar_mensalidades(db, ate=date(2026, 12, 31))

        vencimentos = [
            c.vencimento.day
            for c in db.execute(select(Charge).order_by(Charge.vencimento)).scalars()
        ]
        assert vencimentos == [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    def test_fevereiro_de_ano_bissexto(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Bissexto", date(2028, 1, 29))

        charge_service.gerar_mensalidades(db, ate=date(2028, 2, 29))

        fev = [c for c in db.execute(select(Charge)).scalars() if c.vencimento.month == 2]
        assert fev[0].vencimento == date(2028, 2, 29), "2028 é bissexto: o 29 existe"

    def test_fevereiro_de_ano_comum(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Comum", date(2026, 1, 29))

        charge_service.gerar_mensalidades(db, ate=date(2026, 2, 28))

        fev = [c for c in db.execute(select(Charge)).scalars() if c.vencimento.month == 2]
        assert fev[0].vencimento == date(2026, 2, 28)


class TestVencidoEDerivado:
    def test_pendente_com_vencimento_passado_esta_vencida(
        self, db: Session, instrutor: User
    ) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Atrasado", date.today() - timedelta(days=60))
        charge_service.gerar_mensalidades(db)

        cobranca = db.execute(select(Charge).order_by(Charge.vencimento)).scalars().first()
        assert cobranca is not None
        assert charge_service.esta_vencida(cobranca)

    def test_nao_existe_coluna_vencido(self, db: Session) -> None:
        """Status gravado exigiria job à meia-noite e mentiria até rodar."""
        assert not hasattr(Charge, "vencido")
        assert set(StatusCobranca) == {
            StatusCobranca.PENDENTE,
            StatusCobranca.PAGO,
            StatusCobranca.CANCELADO,
        }

    def test_pagar_tira_do_vencido(self, db: Session, instrutor: User, recepcao: User) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Pagou", date.today() - timedelta(days=60))
        charge_service.gerar_mensalidades(db)
        cobranca = db.execute(select(Charge)).scalars().first()
        assert cobranca is not None

        charge_service.marcar_pago(db, cobranca.id, registrado_por_id=recepcao.id)

        assert not charge_service.esta_vencida(cobranca)


class TestTotais:
    def test_tres_cards_do_print(self, db: Session, instrutor: User, recepcao: User) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Totais", date.today() - timedelta(days=90), valor=10_000)
        charge_service.gerar_mensalidades(db)
        cobrancas = list(db.execute(select(Charge).order_by(Charge.vencimento)).scalars())
        charge_service.marcar_pago(db, cobrancas[0].id, registrado_por_id=recepcao.id)

        t = charge_service.totais(db)

        assert t.recebido_centavos == 10_000
        assert t.pendente_centavos == 10_000 * (len(cobrancas) - 1)
        # Pendente inclui o vencido: é tudo que ainda não entrou no caixa.
        assert t.vencido_centavos <= t.pendente_centavos


class TestVendaDePacote:
    def test_venda_gera_cobranca_no_ato(self, db: Session, admin: User) -> None:
        """A cobrança do pacote nasce na venda. Não é mensal."""
        servico = criar_servico(db, nome="Fisio Venda", modelo=ModeloCobranca.PACOTE)
        paciente = criar_paciente(db, "Comprador")

        pacote, cobranca = package_service.vender(
            db,
            patient_id=paciente.id,
            service_id=servico.id,
            sessoes_contratadas=10,
            valor_centavos=90_000,
            registrado_por_id=admin.id,
        )

        assert cobranca.tipo is TipoCobranca.PACOTE
        assert cobranca.valor_centavos == 90_000
        assert cobranca.package_id == pacote.id
        assert cobranca.competencia_inicio is None, "pacote não tem competência mensal"

    def test_valores_vem_do_formulario_nao_do_servico(self, db: Session, admin: User) -> None:
        """Cada pacote é negociado caso a caso. A sugestão só pré-preenche."""
        servico = criar_servico(db, nome="Fisio Sug", modelo=ModeloCobranca.PACOTE)
        servico.sugestao_pacote_sessoes = 10
        servico.sugestao_pacote_valor_centavos = 100_000
        db.flush()

        pacote, cobranca = package_service.vender(
            db,
            patient_id=criar_paciente(db, "Negociou").id,
            service_id=servico.id,
            sessoes_contratadas=6,
            valor_centavos=55_000,
            registrado_por_id=admin.id,
        )

        assert pacote.sessoes_contratadas == 6
        assert cobranca.valor_centavos == 55_000

    def test_sugestao_e_apenas_leitura_para_a_tela(self, db: Session) -> None:
        servico = criar_servico(db, nome="Fisio Pre", modelo=ModeloCobranca.PACOTE)
        servico.sugestao_pacote_sessoes = 12
        servico.sugestao_pacote_validade_dias = 90
        db.flush()

        s = package_service.sugestao_para(db, servico.id)

        assert s["sessoes"] == 12
        assert s["validade_dias"] == 90

    def test_validade_em_branco_e_caso_normal(self, db: Session, admin: User) -> None:
        servico = criar_servico(db, nome="Fisio Sem Val", modelo=ModeloCobranca.PACOTE)

        pacote, _ = package_service.vender(
            db,
            patient_id=criar_paciente(db, "Sem Validade").id,
            service_id=servico.id,
            sessoes_contratadas=5,
            valor_centavos=40_000,
            registrado_por_id=admin.id,
        )

        assert pacote.validade_ate is None
        assert package_service.utilizavel(db, pacote)


class TestRbac:
    def test_recepcao_paga_e_desfaz(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Rbac", date.today() - timedelta(days=30))
        charge_service.gerar_mensalidades(db)
        cobranca = db.execute(select(Charge)).scalars().first()
        assert cobranca is not None
        db.commit()
        t = login(client, recepcao.email)

        pago = client.post(
            f"/api/v1/charges/{cobranca.id}/pagar",
            json={"forma_pagamento": "pix"},
            headers=auth(t),
        )
        desfeito = client.post(f"/api/v1/charges/{cobranca.id}/desfazer", headers=auth(t))

        assert pago.status_code == 200 and pago.json()["status"] == "pago"
        assert desfeito.status_code == 200 and desfeito.json()["status"] == "pendente"

    def test_baixa_sem_forma_de_pagamento_e_recusada(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Sem forma, a baixa caía em "outro" calada e o gráfico mentia."""
        criar_configuracao(db)
        _matricula(db, instrutor, "Sem Forma", date.today() - timedelta(days=30))
        charge_service.gerar_mensalidades(db)
        cobranca = db.execute(select(Charge)).scalars().first()
        assert cobranca is not None
        db.commit()
        t = login(client, recepcao.email)

        r = client.post(f"/api/v1/charges/{cobranca.id}/pagar", json={}, headers=auth(t))

        assert r.status_code == 422
        db.refresh(cobranca)
        assert cobranca.status is StatusCobranca.PENDENTE

    def test_recepcao_nao_cancela_cobranca(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Perdoar dívida é decisão da proprietária."""
        criar_configuracao(db)
        _matricula(db, instrutor, "NaoCancela", date.today() - timedelta(days=30))
        charge_service.gerar_mensalidades(db)
        cobranca = db.execute(select(Charge)).scalars().first()
        assert cobranca is not None
        db.commit()
        t = login(client, recepcao.email)

        r = client.request(
            "DELETE", f"/api/v1/charges/{cobranca.id}", json={"motivo": "x"}, headers=auth(t)
        )

        assert r.status_code == 403

    def test_admin_cancela(
        self, client: TestClient, db: Session, instrutor: User, admin: User
    ) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "AdminCancela", date.today() - timedelta(days=30))
        charge_service.gerar_mensalidades(db)
        cobranca = db.execute(select(Charge)).scalars().first()
        assert cobranca is not None
        db.commit()
        t = login(client, admin.email)

        r = client.request(
            "DELETE",
            f"/api/v1/charges/{cobranca.id}",
            json={"motivo": "Cortesia"},
            headers=auth(t),
        )

        assert r.status_code == 200 and r.json()["status"] == "cancelado"

    def test_instrutor_nao_ve_valores(
        self, client: TestClient, db: Session, instrutor: User
    ) -> None:
        criar_configuracao(db)
        t = login(client, instrutor.email)

        assert client.get("/api/v1/charges", headers=auth(t)).status_code == 403
        assert client.get("/api/v1/charges/totais", headers=auth(t)).status_code == 403
        assert client.get("/api/v1/packages", headers=auth(t)).status_code == 403

    def test_totais_so_para_admin(
        self, client: TestClient, db: Session, recepcao: User, admin: User
    ) -> None:
        """Os três cards são da proprietária. A recepção registra pagamentos,
        mas não vê o caixa — bloqueado na API, não só escondido na tela."""
        criar_configuracao(db)

        r_recepcao = client.get(
            "/api/v1/charges/totais", headers=auth(login(client, recepcao.email))
        )
        r_admin = client.get("/api/v1/charges/totais", headers=auth(login(client, admin.email)))

        assert r_recepcao.status_code == 403
        assert r_admin.status_code == 200
        assert set(r_admin.json()) == {
            "recebido_centavos",
            "recebido_liquido_centavos",
            "pendente_centavos",
            "vencido_centavos",
        }

    def test_recepcao_continua_registrando_pagamento(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        criar_configuracao(db)
        t = login(client, recepcao.email)

        assert client.get("/api/v1/charges", headers=auth(t)).status_code == 200


class TestFluxoDePagamento:
    def test_cancelada_nao_pode_ser_paga(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Cancelada", date.today() - timedelta(days=30))
        charge_service.gerar_mensalidades(db)
        cobranca = db.execute(select(Charge)).scalars().first()
        assert cobranca is not None
        charge_service.cancelar(db, cobranca.id, motivo="Erro de lançamento")

        with pytest.raises(HTTPException) as exc:
            charge_service.marcar_pago(db, cobranca.id, registrado_por_id=recepcao.id)

        assert exc.value.status_code == 409

    def test_paga_nao_pode_ser_paga_de_novo(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Duplo envio, ou duas recepcionistas com o modal aberto na mesma cobrança.

        O segundo pagamento não pode trocar a forma e a data do primeiro em
        silêncio — isso muda o caixa de forma e até de mês na análise.
        """
        criar_configuracao(db)
        _matricula(db, instrutor, "PagaDuas", date.today() - timedelta(days=30))
        charge_service.gerar_mensalidades(db)
        cobranca = db.execute(select(Charge)).scalars().first()
        assert cobranca is not None
        charge_service.marcar_pago(
            db, cobranca.id, registrado_por_id=recepcao.id, forma=FormaPagamento.DINHEIRO
        )
        pago_em = cobranca.pago_em

        with pytest.raises(HTTPException) as exc:
            charge_service.marcar_pago(
                db, cobranca.id, registrado_por_id=recepcao.id, forma=FormaPagamento.PIX
            )

        assert exc.value.status_code == 409
        assert exc.value.detail == "Esta cobrança já está paga."
        db.refresh(cobranca)
        assert cobranca.status is StatusCobranca.PAGO
        assert cobranca.forma_pagamento is FormaPagamento.DINHEIRO
        assert cobranca.pago_em == pago_em

    def test_desfazer_libera_pagar_de_novo(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Corrigir a forma é desfazer e pagar de novo, de propósito."""
        criar_configuracao(db)
        _matricula(db, instrutor, "Corrige", date.today() - timedelta(days=30))
        charge_service.gerar_mensalidades(db)
        cobranca = db.execute(select(Charge)).scalars().first()
        assert cobranca is not None
        charge_service.marcar_pago(
            db, cobranca.id, registrado_por_id=recepcao.id, forma=FormaPagamento.DINHEIRO
        )
        charge_service.desfazer_pagamento(db, cobranca.id, registrado_por_id=recepcao.id)

        charge_service.marcar_pago(
            db, cobranca.id, registrado_por_id=recepcao.id, forma=FormaPagamento.PIX
        )

        db.refresh(cobranca)
        assert cobranca.status is StatusCobranca.PAGO
        assert cobranca.forma_pagamento is FormaPagamento.PIX
        assert cobranca.pago_em is not None

    def test_pendente_nao_pode_ser_desfeita(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        _matricula(db, instrutor, "Pendente", date.today() - timedelta(days=30))
        charge_service.gerar_mensalidades(db)
        cobranca = db.execute(select(Charge)).scalars().first()
        assert cobranca is not None

        with pytest.raises(HTTPException) as exc:
            charge_service.desfazer_pagamento(db, cobranca.id, registrado_por_id=recepcao.id)

        assert exc.value.status_code == 409

    def test_cancelar_libera_o_ciclo_para_nova_cobranca(self, db: Session, instrutor: User) -> None:
        """O índice de unicidade é parcial: cancelada sai do índice."""
        criar_configuracao(db)
        _matricula(db, instrutor, "Regerar", date(2026, 1, 10))
        charge_service.gerar_mensalidades(db, ate=date(2026, 1, 31))
        cobranca = db.execute(select(Charge)).scalars().one()
        charge_service.cancelar(db, cobranca.id, motivo="Valor errado")

        r = charge_service.gerar_mensalidades(db, ate=date(2026, 1, 31))

        assert r.criadas == 1


class TestDinheiroEmCentavos:
    def test_valores_sao_inteiros(self, db: Session, instrutor: User) -> None:
        """Float em dinheiro erra o arredondamento."""
        criar_configuracao(db)
        _matricula(db, instrutor, "Centavos", date(2026, 1, 10), valor=12_345)
        charge_service.gerar_mensalidades(db, ate=date(2026, 1, 31))

        cobranca = db.execute(select(Charge)).scalars().one()
        assert isinstance(cobranca.valor_centavos, int)
        assert cobranca.valor_centavos == 12_345


class TestCpfNoFinanceiro:
    """CPF para a nota fiscal. Só a proprietária vê — a nota é emitida por ela."""

    def _cobranca_com_cpf(self, db: Session, cpf: str | None) -> Charge:
        paciente = criar_paciente(db, "Paciente da Nota")
        paciente.cpf = cpf
        cobranca = Charge(
            patient_id=paciente.id,
            tipo=TipoCobranca.AVULSA,
            descricao="Avaliação",
            valor_centavos=10_000,
            vencimento=date.today(),
        )
        db.add(cobranca)
        db.flush()
        return cobranca

    def test_admin_ve_cpf_formatado(self, client: TestClient, db: Session, admin: User) -> None:
        cobranca = self._cobranca_com_cpf(db, "52998224725")
        t = login(client, admin.email)

        lista = client.get("/api/v1/charges", headers=auth(t)).json()["itens"]
        unica = client.get(f"/api/v1/charges/{cobranca.id}", headers=auth(t)).json()

        assert [c["paciente_cpf"] for c in lista] == ["529.982.247-25"]
        assert unica["paciente_cpf"] == "529.982.247-25"

    def test_recepcao_nao_recebe_cpf(self, client: TestClient, db: Session, recepcao: User) -> None:
        cobranca = self._cobranca_com_cpf(db, "52998224725")
        t = login(client, recepcao.email)

        lista = client.get("/api/v1/charges", headers=auth(t))
        unica = client.get(f"/api/v1/charges/{cobranca.id}", headers=auth(t))

        assert "52998224725" not in lista.text and "529.982.247-25" not in lista.text
        assert unica.json()["paciente_cpf"] is None

    def test_paciente_sem_cpf(self, client: TestClient, db: Session, admin: User) -> None:
        self._cobranca_com_cpf(db, None)
        t = login(client, admin.email)

        itens = client.get("/api/v1/charges", headers=auth(t)).json()["itens"]

        assert itens[0]["paciente_cpf"] is None


class TestValorLiquido:
    """Valor líquido = valor - custos extras, por cobrança, em reais fixos.

    Só a proprietária lança o custo e vê o líquido.
    """

    def _cobranca(self, db: Session, valor: int = 20_000) -> Charge:
        cobranca = Charge(
            patient_id=criar_paciente(db, "Paciente Liquido").id,
            tipo=TipoCobranca.AVULSA,
            descricao="Avaliação",
            valor_centavos=valor,
            vencimento=date.today(),
        )
        db.add(cobranca)
        db.flush()
        return cobranca

    def test_admin_lanca_custo_e_ve_liquido(
        self, client: TestClient, db: Session, admin: User
    ) -> None:
        cobranca = self._cobranca(db)
        t = login(client, admin.email)

        r = client.put(
            f"/api/v1/charges/{cobranca.id}/custo-extra",
            json={"custo_extra_centavos": 1_250},
            headers=auth(t),
        )
        item = client.get("/api/v1/charges", headers=auth(t)).json()["itens"][0]

        assert r.status_code == 200
        assert item["custo_extra_centavos"] == 1_250
        assert item["valor_liquido_centavos"] == 18_750
        assert item["valor_centavos"] == 20_000, "o valor cobrado não muda"

    def test_sem_custo_o_liquido_e_o_valor(
        self, client: TestClient, db: Session, admin: User
    ) -> None:
        self._cobranca(db)
        t = login(client, admin.email)

        item = client.get("/api/v1/charges", headers=auth(t)).json()["itens"][0]

        assert item["valor_liquido_centavos"] == 20_000

    def test_custo_maior_que_o_valor_e_recusado(
        self, client: TestClient, db: Session, admin: User
    ) -> None:
        cobranca = self._cobranca(db, valor=1_000)
        t = login(client, admin.email)

        r = client.put(
            f"/api/v1/charges/{cobranca.id}/custo-extra",
            json={"custo_extra_centavos": 1_001},
            headers=auth(t),
        )

        assert r.status_code == 422

    def test_recepcao_nao_ve_nem_lanca(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        cobranca = self._cobranca(db)
        cobranca.custo_extra_centavos = 500
        db.flush()
        t = login(client, recepcao.email)

        item = client.get("/api/v1/charges", headers=auth(t)).json()["itens"][0]
        r = client.put(
            f"/api/v1/charges/{cobranca.id}/custo-extra",
            json={"custo_extra_centavos": 0},
            headers=auth(t),
        )

        assert item["custo_extra_centavos"] is None
        assert item["valor_liquido_centavos"] is None
        assert r.status_code == 403

    def test_total_recebido_liquido(self, db: Session, recepcao: User) -> None:
        paga = self._cobranca(db, valor=10_000)
        charge_service.marcar_pago(db, paga.id, registrado_por_id=recepcao.id)
        charge_service.definir_custo_extra(db, paga.id, custo_extra_centavos=300)
        # Pendente não entra no recebido, nem o custo dela.
        pendente = self._cobranca(db, valor=5_000)
        charge_service.definir_custo_extra(db, pendente.id, custo_extra_centavos=100)

        t = charge_service.totais(db)

        assert t.recebido_centavos == 10_000
        assert t.recebido_liquido_centavos == 9_700
