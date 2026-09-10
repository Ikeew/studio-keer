from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.models.booking import OrigemReserva, StatusReserva
from app.models.session import StatusSessao

FUSO_DO_STUDIO = ZoneInfo(get_settings().TIMEZONE)


class SessionCreate(BaseModel):
    service_id: int
    professional_id: int
    inicia_em: datetime
    # Override opcional da capacidade do serviço (equipamento em manutenção,
    # turma reduzida). Sem valor, herda o padrão do serviço.
    capacidade: int | None = Field(default=None, gt=0, le=50)
    observacoes: str | None = None

    @field_validator("inicia_em")
    @classmethod
    def interpretar_no_fuso_do_studio(cls, v: datetime) -> datetime:
        """Datetime sem fuso é HORÁRIO DO STUDIO, não UTC.

        A recepção manda "2026-09-14T08:00:00" pensando em oito da manhã em
        São Paulo. Sem esta conversão, o Python trata o valor como ingênuo e
        `astimezone()` aplica o fuso do SERVIDOR — que em container é UTC. As
        08:00 viravam 05:00 e eram recusadas como fora da janela, enquanto
        13:00 virava 10:00 e passava, criando turma dentro da pausa.

        Bug encontrado rodando o sistema, não nos testes: eles construíam o
        datetime já com fuso.
        """
        if v.tzinfo is None:
            return v.replace(tzinfo=FUSO_DO_STUDIO)
        return v


class ReservaNaGrade(BaseModel):
    """Reserva como aparece no card da grade."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    paciente_nome: str
    posicao: int
    status: StatusReserva
    origem: OrigemReserva
    justificada: bool


class SessaoNaGrade(BaseModel):
    id: int
    service_id: int
    servico_nome: str
    servico_cor: str
    professional_id: int
    instrutor_nome: str
    inicia_em: datetime
    termina_em: datetime
    hora: str  # 'HH:MM' no fuso do studio, para a grade agrupar sem recalcular
    dia: date
    capacidade: int
    ocupadas: int
    vagas: int
    lotada: bool
    status: StatusSessao
    reservas: list[ReservaNaGrade]


class DiaDaGrade(BaseModel):
    data: date
    dia_semana: int
    aberto: bool
    # Já SEM a pausa e fora da janela: a API nunca devolve horário que o
    # studio não atende.
    horas: list[str]
    hora_abertura: time | None
    hora_fechamento: time | None
    pausa_inicio: time | None
    pausa_fim: time | None


class GradeSemanal(BaseModel):
    inicio: date
    fim: date
    dias: list[DiaDaGrade]
    sessoes: list[SessaoNaGrade]


class BookingCreate(BaseModel):
    session_id: int
    patient_id: int
    origem: OrigemReserva = OrigemReserva.AVULSA
    package_id: int | None = None
    # Liga a reposição à falta que ela cobre. Sem isso a falta continuaria
    # aparecendo como pendente para sempre, e o índice único que impede repor
    # a mesma falta duas vezes nunca entraria em ação.
    substitui_booking_id: int | None = None


class BookingCancel(BaseModel):
    motivo: str | None = Field(default=None, max_length=500)


class BookingFalta(BaseModel):
    """Quem julga se a falta é justificada é a RECEPÇÃO.

    Não há prazo nem relógio que classifique sozinho — a regra das 24h era
    premissa do time e foi descartada (docs/premissas.md, P4).
    """

    justificada: bool = False
    motivo: str | None = Field(default=None, max_length=500)


class BookingRemarcar(BaseModel):
    nova_session_id: int
    origem: OrigemReserva = OrigemReserva.REMARCACAO


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    patient_id: int
    package_id: int | None
    posicao: int
    capacidade_sessao: int
    origem: OrigemReserva
    status: StatusReserva
    justificada: bool
    motivo_justificativa: str | None
    substitui_booking_id: int | None
    cancelado_em: datetime | None
    motivo_cancelamento: str | None
