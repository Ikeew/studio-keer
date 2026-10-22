from pydantic import BaseModel, Field, field_validator

from app.models.charge import FormaPagamento


class ProdutoCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=80)
    #: Texto livre: "P", "M", "G", "Único".
    tamanho: str = Field(min_length=1, max_length=20)
    preco_centavos: int = Field(ge=0)
    estoque_minimo: int = Field(default=3, ge=0, le=10_000)

    @field_validator("nome", "tamanho")
    @classmethod
    def limpar(cls, v: str) -> str:
        return " ".join(v.split())


class ProdutoUpdate(BaseModel):
    """Só o que a proprietária ajusta no dia a dia. Nome e tamanho não mudam:
    seria outro produto, com outro histórico."""

    preco_centavos: int | None = Field(default=None, ge=0)
    estoque_minimo: int | None = Field(default=None, ge=0, le=10_000)
    ativo: bool | None = None


class ProdutoRead(BaseModel):
    id: int
    nome: str
    tamanho: str
    preco_centavos: int
    estoque_minimo: int
    ativo: bool
    #: Soma dos movimentos — nunca coluna.
    estoque: int
    #: Chegou ao mínimo: a tela avisa.
    acabando: bool


class EntradaDeEstoque(BaseModel):
    quantidade: int = Field(gt=0, le=10_000)
    observacao: str | None = Field(default=None, max_length=300)


class VendaDeProduto(BaseModel):
    """Venda de balcão: nasce paga, então a forma de pagamento é obrigatória."""

    quantidade: int = Field(default=1, gt=0, le=1_000)
    forma_pagamento: FormaPagamento
    #: Opcional: a venda pode ser para quem não é paciente.
    patient_id: int | None = None
    #: Nome de quem comprou, quando não é paciente. Em branco: "Studio Keer".
    comprador_nome: str | None = Field(default=None, max_length=160)

    @field_validator("comprador_nome")
    @classmethod
    def limpar_comprador(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return " ".join(v.split()) or None
