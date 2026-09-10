from datetime import date
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
)

from app.core.cpf import cpf_valido, formatar_cpf, normalizar_cpf
from app.models.patient import EstadoCivil, Sexo


def _validar_cpf(v: str | None) -> str | None:
    """CPF é opcional, mas se vier tem de ser válido de verdade.

    Guardado sem pontuação: com máscara, o índice único deixaria passar o
    mesmo CPF digitado de duas formas.
    """
    if v is None or not v.strip():
        return None
    if not cpf_valido(v):
        raise ValueError("CPF inválido")
    return normalizar_cpf(v)


# Tipo reaproveitado por PatientCreate e PatientUpdate, para que a regra do
# CPF exista num lugar só.
CPFOpcional = Annotated[str | None, AfterValidator(_validar_cpf)]


class PatientBase(BaseModel):
    nome_completo: str = Field(min_length=3, max_length=160)
    cpf: CPFOpcional = None
    data_nascimento: date | None = None
    sexo: Sexo = Sexo.NAO_INFORMADO
    estado_civil: EstadoCivil = EstadoCivil.NAO_INFORMADO
    profissao: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=20)
    emergencia_nome: str | None = Field(default=None, max_length=160)
    emergencia_telefone: str | None = Field(default=None, max_length=20)
    observacoes: str | None = None
    consentimento_lgpd: bool = False

    @field_validator("data_nascimento")
    @classmethod
    def nascimento_no_passado(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("Data de nascimento não pode estar no futuro")
        return v

    @field_validator("nome_completo")
    @classmethod
    def limpar_nome(cls, v: str) -> str:
        return " ".join(v.split())


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    """Atualização parcial: só o que vier é alterado.

    Repete os campos em vez de herdar de PatientBase porque todos precisam ser
    opcionais aqui, e os defaults de PatientBase sobrescreveriam valores já
    gravados quando o cliente omitisse o campo.
    """

    nome_completo: str | None = Field(default=None, min_length=3, max_length=160)
    cpf: CPFOpcional = None
    data_nascimento: date | None = None
    sexo: Sexo | None = None
    estado_civil: EstadoCivil | None = None
    profissao: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=20)
    emergencia_nome: str | None = Field(default=None, max_length=160)
    emergencia_telefone: str | None = Field(default=None, max_length=20)
    observacoes: str | None = None
    consentimento_lgpd: bool | None = None


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome_completo: str
    cpf: str | None
    data_nascimento: date | None
    sexo: Sexo
    estado_civil: EstadoCivil
    profissao: str | None
    email: EmailStr | None
    telefone: str | None
    emergencia_nome: str | None
    emergencia_telefone: str | None
    observacoes: str | None
    consentimento_lgpd: bool
    consentimento_em: date | None
    ativo: bool

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cpf_formatado(self) -> str | None:
        """CPF com máscara, para a tela não ter de formatar."""
        return formatar_cpf(self.cpf) if self.cpf else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def idade(self) -> int | None:
        """Derivada da data de nascimento — nunca uma coluna.

        Idade armazenada fica errada no dia seguinte ao aniversário.
        """
        if self.data_nascimento is None:
            return None
        hoje = date.today()
        nasc = self.data_nascimento
        return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))


class PaginaDePacientes(BaseModel):
    itens: list[PatientRead]
    total: int
    pagina: int
    tamanho: int
