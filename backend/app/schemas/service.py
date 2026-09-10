import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.service import ModeloCobranca

HEX_COR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ServiceBase(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    duracao_min: int = Field(gt=0, le=480)
    preco_centavos: int = Field(ge=0)
    capacidade_padrao: int = Field(gt=0, le=50)
    cor: str = Field(default="#06B6D4")
    modelo_cobranca: ModeloCobranca

    # Sugestões para pré-preencher a venda de pacote. NUNCA são fonte de
    # verdade: os valores que valem são os capturados em `packages` no ato da
    # venda, negociados caso a caso. Ver docs/modelo-de-dados.md.
    sugestao_pacote_sessoes: int | None = Field(default=None, gt=0, le=500)
    sugestao_pacote_validade_dias: int | None = Field(default=None, gt=0, le=3650)
    sugestao_pacote_valor_centavos: int | None = Field(default=None, ge=0)

    @field_validator("cor")
    @classmethod
    def cor_hex(cls, v: str) -> str:
        if not HEX_COR.match(v):
            raise ValueError("Cor deve ser hexadecimal no formato #RRGGBB")
        return v.upper()

    @field_validator("nome")
    @classmethod
    def limpar_nome(cls, v: str) -> str:
        return " ".join(v.split())

    @model_validator(mode="after")
    def sugestao_so_em_servico_de_pacote(self) -> "ServiceBase":
        """Sugestão de pacote em serviço de mensalidade não significa nada.

        Validado aqui **e** por CHECK no banco. Esconder o campo na tela não é
        validação: a API é chamável direto.
        """
        if self.modelo_cobranca is ModeloCobranca.PACOTE:
            return self

        preenchidos = [
            nome
            for nome, valor in (
                ("sugestao_pacote_sessoes", self.sugestao_pacote_sessoes),
                ("sugestao_pacote_validade_dias", self.sugestao_pacote_validade_dias),
                ("sugestao_pacote_valor_centavos", self.sugestao_pacote_valor_centavos),
            )
            if valor is not None
        ]
        if preenchidos:
            raise ValueError(
                "Sugestão de pacote só se aplica a serviço com modelo de cobrança "
                f"'pacote'. Recebido em: {', '.join(preenchidos)}"
            )
        return self


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(ServiceBase):
    """Atualização é substituição completa.

    Diferente de PatientUpdate, que é parcial: aqui a validação cruzada entre
    modelo de cobrança e sugestões precisa enxergar o registro inteiro. Com
    campos opcionais seria possível trocar o modelo para 'mensalidade' e
    deixar as sugestões antigas para trás.
    """

    ativo: bool = True


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    duracao_min: int
    preco_centavos: int
    capacidade_padrao: int
    cor: str
    modelo_cobranca: ModeloCobranca
    sugestao_pacote_sessoes: int | None
    sugestao_pacote_validade_dias: int | None
    sugestao_pacote_valor_centavos: int | None
    ativo: bool
