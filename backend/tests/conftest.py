import os
from collections.abc import Generator

# Definido antes de qualquer import da app: Settings é lido no import de
# app.db.session, e get_settings() é cacheado com lru_cache.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://keer:keer@localhost:5432/keer_test")
os.environ.setdefault("SECRET_KEY", "chave-de-teste-com-no-minimo-32-caracteres!")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c
