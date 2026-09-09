"""Comandos de linha de comando para operação do sistema.

Uso:
    uv run python -m app.cli seed-usuarios

As senhas vêm SEMPRE de variável de ambiente. Nenhuma senha no repositório,
e nada disso em migration: migration é versionamento de schema, e uma que
cria usuário roda igual em produção, plantando conta conhecida no ambiente
real.
"""

import argparse
import os
import secrets
import sys

from sqlalchemy.orm import Session

from app.core.security import BCRYPT_MAX_BYTES, hash_senha
from app.db.session import SessionLocal
from app.models.user import Papel, User
from app.services.auth_service import buscar_por_email

# (variável de ambiente, e-mail, nome, papel)
USUARIOS_SEED = [
    ("SEED_ADMIN_SENHA", "admin@studiokeer.com.br", "Dra. Belanir", Papel.ADMIN),
    ("SEED_RECEPCAO_SENHA", "recepcao@studiokeer.com.br", "Recepção", Papel.RECEPCAO),
    ("SEED_INSTRUTOR_SENHA", "instrutor@studiokeer.com.br", "Instrutor", Papel.INSTRUTOR),
]

SENHA_MIN = 8


def _ler_senha(env_var: str, gerar: bool) -> str:
    senha = os.environ.get(env_var)
    if senha:
        if len(senha) < SENHA_MIN:
            raise SystemExit(f"{env_var}: senha muito curta (mínimo {SENHA_MIN} caracteres).")
        if len(senha.encode()) > BCRYPT_MAX_BYTES:
            raise SystemExit(f"{env_var}: senha acima de {BCRYPT_MAX_BYTES} bytes.")
        return senha
    if gerar:
        return secrets.token_urlsafe(12)
    raise SystemExit(
        f"Variável {env_var} não definida.\n"
        f"Defina as senhas no ambiente ou use --gerar-senhas para sortear:\n"
        f"  {env_var}='...' uv run python -m app.cli seed-usuarios"
    )


def seed_usuarios(gerar: bool) -> None:
    """Cria os usuários de teste. Idempotente: rodar de novo não duplica.

    Não sobrescreve senha de usuário existente — rodar o seed sem querer num
    ambiente já em uso não pode derrubar o acesso de ninguém.
    """
    db: Session = SessionLocal()
    geradas: list[tuple[str, str]] = []
    try:
        for env_var, email, nome, papel in USUARIOS_SEED:
            if buscar_por_email(db, email) is not None:
                print(f"  = {email:32} já existe, mantido")
                continue

            senha = _ler_senha(env_var, gerar)
            db.add(
                User(
                    nome=nome,
                    email=email.lower(),
                    senha_hash=hash_senha(senha),
                    papel=papel,
                    ativo=True,
                )
            )
            print(f"  + {email:32} criado ({papel.value})")
            if not os.environ.get(env_var):
                geradas.append((email, senha))
        db.commit()
    finally:
        db.close()

    if geradas:
        print("\nSenhas geradas — anote agora, não são exibidas de novo:\n")
        for email, senha in geradas:
            print(f"  {email:32} {senha}")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    p_seed = sub.add_parser("seed-usuarios", help="cria os usuários de teste")
    p_seed.add_argument(
        "--gerar-senhas",
        action="store_true",
        help="sorteia senha para quem não tiver variável de ambiente definida",
    )

    args = parser.parse_args(argv)
    if args.comando == "seed-usuarios":
        seed_usuarios(gerar=args.gerar_senhas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
