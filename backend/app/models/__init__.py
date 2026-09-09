"""Models do SQLAlchemy.

Todo model precisa ser importado aqui: o Alembic descobre as tabelas por
`Base.metadata`, que só é populado quando a classe é importada. Model que
falta nesta lista some silenciosamente do autogenerate.
"""

from app.models.user import Papel, User

__all__ = ["Papel", "User"]
