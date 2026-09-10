from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.charge import FormaPagamento, StatusCobranca, TipoCobranca


class ChargeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    paciente_nome: str
    tipo: TipoCobranca
    descricao: str
    competencia_inicio: date | None
    competencia_fim: date | None
    valor_centavos: int
    vencimento: date
    status: StatusCobranca
    pago_em: datetime | None
    forma_pagamento: FormaPagamento | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def vencida(self) -> bool:
        """Derivado, nunca coluna.

        Um status `vencido` gravado exigiria um job à meia-noite e mentiria
        até ele rodar.
        """
        return self.status is StatusCobranca.PENDENTE and self.vencimento < date.today()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dias_de_atraso(self) -> int:
        if not self.vencida:
            return 0
        return (date.today() - self.vencimento).days


class PaginaDeCobrancas(BaseModel):
    itens: list[ChargeRead]
    total: int
    pagina: int
    tamanho: int


class TotaisRead(BaseModel):
    """Os três cards do topo, como no print."""

    recebido_centavos: int
    pendente_centavos: int
    vencido_centavos: int


class MarcarPago(BaseModel):
    forma_pagamento: FormaPagamento = FormaPagamento.OUTRO


class CancelarCobranca(BaseModel):
    motivo: str | None = Field(default=None, max_length=300)


class ResultadoFaturamentoRead(BaseModel):
    criadas: int
    ja_existentes: int
    matriculas: int


class SugestaoDePacote(BaseModel):
    """Valores para PRÉ-PREENCHER a venda. Nunca fonte de verdade."""

    sessoes: int | None
    validade_dias: int | None
    valor_centavos: int | None


class VendaDePacote(BaseModel):
    patient_id: int
    service_id: int
    # Tudo negociado no ato, e nada herdado automaticamente do serviço.
    sessoes_contratadas: int = Field(gt=0, le=500)
    valor_centavos: int = Field(ge=0)
    #: Em branco = vale até acabar o saldo. Como falta não consome sessão, a
    #: validade é a única trava do pacote.
    validade_ate: date | None = None


class PackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    paciente_nome: str
    service_id: int
    servico_nome: str
    sessoes_contratadas: int
    valor_centavos: int
    validade_ate: date | None
    comprado_em: date
    status: str
    #: Só reserva com status `presente` consome sessão.
    sessoes_usadas: int
    saldo: int
    #: Saldo E validade juntos — saldo sem validade faz a recepção prometer
    #: o que o sistema depois recusa.
    utilizavel: bool
