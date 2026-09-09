from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verificar_senha
from app.models.user import User


def buscar_por_email(db: Session, email: str) -> User | None:
    # E-mail é normalizado em minúsculas na escrita e na leitura: ninguém
    # deve ficar de fora por ter digitado "Maria@" em vez de "maria@".
    stmt = select(User).where(User.email == email.strip().lower())
    return db.execute(stmt).scalar_one_or_none()


def autenticar(db: Session, email: str, senha: str) -> User | None:
    """Valida credenciais e devolve o usuário, ou None.

    Devolve None indistintamente para e-mail inexistente, senha errada e
    usuário desativado. Mensagens diferentes revelariam quais e-mails têm
    conta no sistema.
    """
    user = buscar_por_email(db, email)
    if user is None:
        return None
    if not verificar_senha(senha, user.senha_hash):
        return None
    if not user.ativo:
        return None
    return user
