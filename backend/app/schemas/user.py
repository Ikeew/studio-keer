from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import BCRYPT_MAX_BYTES
from app.models.user import Papel


class UserRead(BaseModel):
    """Usuário como sai da API. Nunca inclui senha_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    papel: Papel
    ativo: bool


class UserCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    # O limite superior é o do bcrypt, que trunca em 72 bytes. Sem ele, duas
    # senhas longas com o mesmo prefixo abririam a mesma conta.
    senha: str = Field(min_length=8, max_length=BCRYPT_MAX_BYTES)
    papel: Papel


class PaginaDeUsuarios(BaseModel):
    itens: list[UserRead]
    total: int
    pagina: int
    tamanho: int
