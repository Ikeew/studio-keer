"""Estoque simples de meia e camiseta.

Quantidade por produto (por tamanho), baixa automática na venda, entrada
manual e aviso quando está acabando. A venda nasce paga.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.charge import Charge, FormaPagamento, StatusCobranca, TipoCobranca
from app.models.produto import Produto
from app.models.user import User
from app.services import charge_service, produto_service
from tests.conftest import auth, criar_paciente, login


def _produto(
    db: Session, *, tamanho: str = "M", preco: int = 5_000, minimo: int = 2, estoque: int = 0
) -> Produto:
    produto = produto_service.criar(
        db, nome="Camiseta", tamanho=tamanho, preco_centavos=preco, estoque_minimo=minimo
    )
    return produto


def _repor(db: Session, produto: Produto, quantidade: int, usuario: User) -> None:
    produto_service.registrar_entrada(
        db, produto.id, quantidade=quantidade, registrado_por_id=usuario.id
    )


class TestEstoque:
    def test_comeca_zerado_e_entrada_soma(self, db: Session, recepcao: User) -> None:
        produto = _produto(db)
        assert produto_service.estoque(db, produto.id) == 0

        _repor(db, produto, 10, recepcao)
        _repor(db, produto, 5, recepcao)

        assert produto_service.estoque(db, produto.id) == 15

    def test_tamanhos_tem_estoques_separados(self, db: Session, recepcao: User) -> None:
        p = _produto(db, tamanho="P")
        g = _produto(db, tamanho="G")
        _repor(db, p, 3, recepcao)

        assert produto_service.estoque(db, p.id) == 3
        assert produto_service.estoque(db, g.id) == 0

    def test_mesmo_nome_e_tamanho_nao_duplica(self, db: Session) -> None:
        _produto(db, tamanho="M")

        with pytest.raises(HTTPException) as exc:
            _produto(db, tamanho="M")

        assert exc.value.status_code == 409

    def test_acabando_quando_chega_ao_minimo(self, db: Session, recepcao: User) -> None:
        produto = _produto(db, minimo=2)
        _repor(db, produto, 3, recepcao)

        def acabando() -> bool:
            return next(
                i for i in produto_service.listar(db) if i.produto.id == produto.id
            ).acabando

        assert acabando() is False
        produto_service.vender(
            db, produto.id, quantidade=1, forma=FormaPagamento.PIX, registrado_por_id=recepcao.id
        )
        assert acabando() is True


class TestVenda:
    def test_baixa_no_estoque_e_cobranca_ja_paga(self, db: Session, recepcao: User) -> None:
        produto = _produto(db, preco=4_500)
        _repor(db, produto, 5, recepcao)
        paciente = criar_paciente(db, "Compradora")

        cobranca = produto_service.vender(
            db,
            produto.id,
            quantidade=2,
            forma=FormaPagamento.DINHEIRO,
            registrado_por_id=recepcao.id,
            patient_id=paciente.id,
        )

        assert produto_service.estoque(db, produto.id) == 3
        assert cobranca.tipo is TipoCobranca.PRODUTO
        assert cobranca.status is StatusCobranca.PAGO
        assert cobranca.pago_em is not None
        assert cobranca.forma_pagamento is FormaPagamento.DINHEIRO
        assert cobranca.valor_centavos == 9_000
        assert cobranca.patient_id == paciente.id

    def test_venda_para_quem_nao_e_paciente(self, db: Session, recepcao: User) -> None:
        produto = _produto(db)
        _repor(db, produto, 2, recepcao)

        anonima = produto_service.vender(
            db, produto.id, quantidade=1, forma=FormaPagamento.PIX, registrado_por_id=recepcao.id
        )
        nomeada = produto_service.vender(
            db,
            produto.id,
            quantidade=1,
            forma=FormaPagamento.PIX,
            registrado_por_id=recepcao.id,
            comprador_nome="Visitante",
        )

        assert anonima.patient_id is None
        assert anonima.comprador_nome == "Studio Keer"
        assert nomeada.comprador_nome == "Visitante"

    def test_sem_estoque_e_recusada_e_nada_e_lancado(self, db: Session, recepcao: User) -> None:
        produto = _produto(db)
        _repor(db, produto, 1, recepcao)

        with pytest.raises(HTTPException) as exc:
            produto_service.vender(
                db,
                produto.id,
                quantidade=2,
                forma=FormaPagamento.PIX,
                registrado_por_id=recepcao.id,
            )

        assert exc.value.status_code == 409
        assert "restam 1" in exc.value.detail
        assert produto_service.estoque(db, produto.id) == 1
        assert db.query(Charge).filter(Charge.tipo == TipoCobranca.PRODUTO).count() == 0

    def test_inativo_nao_vende(self, db: Session, recepcao: User) -> None:
        produto = _produto(db)
        _repor(db, produto, 1, recepcao)
        produto.ativo = False

        with pytest.raises(HTTPException):
            produto_service.vender(
                db,
                produto.id,
                quantidade=1,
                forma=FormaPagamento.PIX,
                registrado_por_id=recepcao.id,
            )

    def test_cancelar_a_venda_devolve_ao_estoque_uma_vez(
        self, db: Session, recepcao: User, admin: User
    ) -> None:
        produto = _produto(db)
        _repor(db, produto, 3, recepcao)
        venda = produto_service.vender(
            db, produto.id, quantidade=2, forma=FormaPagamento.PIX, registrado_por_id=recepcao.id
        )

        charge_service.cancelar(db, venda.id, motivo="Trocou de ideia", cancelado_por_id=admin.id)
        charge_service.cancelar(db, venda.id, motivo="De novo", cancelado_por_id=admin.id)

        assert produto_service.estoque(db, produto.id) == 3


class TestApi:
    def test_fluxo_de_balcao(
        self, client: TestClient, db: Session, admin: User, recepcao: User
    ) -> None:
        ta = login(client, admin.email)
        tr = login(client, recepcao.email)

        criado = client.post(
            "/api/v1/produtos",
            json={"nome": " Meia ", "tamanho": "Único", "preco_centavos": 2_000},
            headers=auth(ta),
        )
        assert criado.status_code == 201
        pid = criado.json()["id"]
        assert criado.json()["nome"] == "Meia"

        entrada = client.post(
            f"/api/v1/produtos/{pid}/entradas", json={"quantidade": 4}, headers=auth(tr)
        )
        assert entrada.json()["estoque"] == 4

        venda = client.post(
            f"/api/v1/produtos/{pid}/vendas",
            json={"quantidade": 3, "forma_pagamento": "pix"},
            headers=auth(tr),
        )
        assert venda.status_code == 201
        assert venda.json()["status"] == "pago"
        assert venda.json()["paciente_nome"] == "Studio Keer"
        assert venda.json()["patient_id"] is None

        lista = client.get("/api/v1/produtos", headers=auth(tr)).json()
        assert [(p["estoque"], p["acabando"]) for p in lista] == [(1, True)]

        # A venda aparece no financeiro mesmo sem paciente.
        cobrancas = client.get("/api/v1/charges", headers=auth(tr)).json()["itens"]
        assert [c["tipo"] for c in cobrancas] == ["produto"]

        sem_estoque = client.post(
            f"/api/v1/produtos/{pid}/vendas",
            json={"quantidade": 2, "forma_pagamento": "pix"},
            headers=auth(tr),
        )
        assert sem_estoque.status_code == 409

    def test_venda_exige_forma_de_pagamento(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        produto = _produto(db)
        _repor(db, produto, 1, recepcao)
        t = login(client, recepcao.email)

        r = client.post(f"/api/v1/produtos/{produto.id}/vendas", json={}, headers=auth(t))

        assert r.status_code == 422

    def test_recepcao_nao_cadastra_nem_muda_preco(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        produto = _produto(db)
        t = login(client, recepcao.email)

        criar = client.post(
            "/api/v1/produtos",
            json={"nome": "Meia", "tamanho": "P", "preco_centavos": 1},
            headers=auth(t),
        )
        mudar = client.patch(
            f"/api/v1/produtos/{produto.id}", json={"preco_centavos": 1}, headers=auth(t)
        )

        assert criar.status_code == 403
        assert mudar.status_code == 403

    def test_instrutor_nao_acessa(self, client: TestClient, instrutor: User) -> None:
        t = login(client, instrutor.email)

        assert client.get("/api/v1/produtos", headers=auth(t)).status_code == 403
