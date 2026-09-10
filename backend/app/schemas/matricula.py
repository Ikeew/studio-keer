from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enrollment import StatusMatricula


class HorarioFixo(BaseModel):
    #: 0 = domingo … 6 = sábado
    dia_semana: int = Field(ge=0, le=6)
    hora_inicio: time


class EnrollmentCreate(BaseModel):
    patient_id: int
    service_id: int
    professional_id: int
    vigencia_inicio: date
    vigencia_fim: date | None = None
    valor_mensal_centavos: int = Field(ge=0)
    horarios: list[HorarioFixo] = Field(min_length=1)


class EnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    paciente_nome: str
    service_id: int
    servico_nome: str
    professional_id: int
    instrutor_nome: str
    status: StatusMatricula
    vigencia_inicio: date
    vigencia_fim: date | None
    valor_mensal_centavos: int
    dia_vencimento: int
    horarios: list[HorarioFixo]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def frequencia_semanal(self) -> int:
        """Derivada da contagem de horários — nunca um campo gravado."""
        return len(self.horarios)


class MotivoOpcional(BaseModel):
    motivo: str | None = Field(default=None, max_length=500)


class ResultadoGeracaoRead(BaseModel):
    sessoes_criadas: int
    sessoes_reaproveitadas: int
    reservas_criadas: int
    reservas_ja_existentes: int
    dias_em_blackout: int
    sem_vaga: list[str]


class SaudeDaGradeRead(BaseModel):
    """Até quando a grade está materializada.

    A interface usa isto para avisar antes de a grade acabar — o modo de
    falha da geração manual é silencioso.
    """

    materializado_ate: date | None
    dias_restantes: int
    semanas_restantes: int
    vencida: bool
    precisa_atualizar: bool
    matriculas_ativas: int
    semanas_minimas: int


class BlackoutCreate(BaseModel):
    data_inicio: date
    data_fim: date
    motivo: str = Field(min_length=2, max_length=160)


class SessaoAfetada(BaseModel):
    id: int
    inicia_em: datetime
    ocupadas: int


class BlackoutRead(BaseModel):
    id: int
    data_inicio: date
    data_fim: date
    motivo: str
    #: Sessões que já existiam dentro do período. O sistema AVISA e não apaga.
    sessoes_em_conflito: list[SessaoAfetada]
    reservas_em_conflito: int


class FaltaPendenteRead(BaseModel):
    booking_id: int
    patient_id: int
    paciente_nome: str
    paciente_telefone: str | None
    servico_nome: str
    service_id: int
    faltou_em: datetime
    justificada: bool
    motivo: str | None
    repor_ate: date | None
    dias_restantes: int | None
    #: Janela em que faz sentido procurar vaga para esta falta.
    procurar_de: date
    procurar_ate: date
