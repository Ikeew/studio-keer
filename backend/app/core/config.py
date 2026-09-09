from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da aplicação, lida do ambiente.

    Nada aqui tem default utilizável em produção: se faltar variável, a app
    não sobe. Falhar no boot é melhor que rodar com uma chave previsível.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: Literal["local", "test", "production"] = "local"
    PROJECT_NAME: str = "Studio Keer API"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: PostgresDsn

    # Segurança
    SECRET_KEY: str = Field(min_length=32)
    # 12 horas. A recepcionista abre o sistema no início do expediente e usa
    # o dia inteiro; expirar durante o turno a deslogaria no meio de um
    # agendamento. Como o studio funciona das 06:00 às 21:00, 12h cobrem o
    # turno mais longo com folga e ainda garantem que o token morra durante a
    # noite — um navegador esquecido aberto não continua válido no dia
    # seguinte. Ver docs/decisoes-tecnicas.md para por que não há refresh token.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    ALGORITHM: str = "HS256"

    # Origens do frontend liberadas no CORS, separadas por vírgula.
    CORS_ORIGINS: str = "http://localhost:5173"

    # Fuso de referência do studio. Todo timestamp é gravado em UTC
    # (TIMESTAMPTZ) e convertido para este fuso na borda da aplicação.
    TIMEZONE: str = "America/Sao_Paulo"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
