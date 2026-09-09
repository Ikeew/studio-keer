from pydantic import BaseModel

from app.schemas.user import UserRead


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # Devolvido junto para o frontend saber quando o token morre sem precisar
    # decodificar o JWT no navegador.
    expires_in: int
    usuario: UserRead
