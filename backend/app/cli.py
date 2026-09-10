"""Comandos de linha de comando para operação do sistema.

Uso:
    uv run python -m app.cli seed-usuarios
    uv run python -m app.cli seed-configuracao
    uv run python -m app.cli seed-servicos
    uv run python -m app.cli seed-demo          # dados fictícios de demonstração
    uv run python -m app.cli limpar-demo

As senhas vêm SEMPRE de variável de ambiente. Nenhuma senha no repositório,
e nada disso em migration: migration é versionamento de schema, e uma que
cria usuário roda igual em produção, plantando conta conhecida no ambiente
real.
"""

import argparse
import os
import secrets
import sys
from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import BCRYPT_MAX_BYTES, hash_senha
from app.db.session import SessionLocal
from app.models.configuracao import Configuracao, HorarioFuncionamento
from app.models.service import ModeloCobranca, Service
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


# Segunda a sábado, 06:00-21:00, pausa 12:00-14:00. Domingo fechado.
# Confirmado pela cliente — ver docs/premissas.md (P6).
# 0 = domingo … 6 = sábado.
FUNCIONAMENTO = [
    (0, False, time(6, 0), time(21, 0), None, None),  # domingo: fechado
    (1, True, time(6, 0), time(21, 0), time(12, 0), time(14, 0)),
    (2, True, time(6, 0), time(21, 0), time(12, 0), time(14, 0)),
    (3, True, time(6, 0), time(21, 0), time(12, 0), time(14, 0)),
    (4, True, time(6, 0), time(21, 0), time(12, 0), time(14, 0)),
    (5, True, time(6, 0), time(21, 0), time(12, 0), time(14, 0)),
    (6, True, time(6, 0), time(21, 0), time(12, 0), time(14, 0)),  # sábado
]


def seed_configuracao() -> None:
    """Cria a configuração e a grade de funcionamento, se ainda não existirem.

    Não há tela de configuração nesta entrega: estes valores se mudam por
    SQL ou por este comando. Ver CLAUDE.md.
    """
    db: Session = SessionLocal()
    try:
        if db.get(Configuracao, 1) is None:
            db.add(Configuracao(id=1))
            print("  + configuracao criada com os padrões")
        else:
            print("  = configuracao já existe, mantida")

        existentes = {d for (d,) in db.execute(select(HorarioFuncionamento.dia_semana)).all()}
        nomes = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"]
        for dia, aberto, abre, fecha, p_ini, p_fim in FUNCIONAMENTO:
            if dia in existentes:
                print(f"  = {nomes[dia]:8} já existe, mantido")
                continue
            db.add(
                HorarioFuncionamento(
                    dia_semana=dia,
                    aberto=aberto,
                    hora_abertura=abre,
                    hora_fechamento=fecha,
                    pausa_inicio=p_ini,
                    pausa_fim=p_fim,
                )
            )
            janela = f"{abre:%H:%M}-{fecha:%H:%M}" if aberto else "fechado"
            pausa = f" (pausa {p_ini:%H:%M}-{p_fim:%H:%M})" if p_ini else ""
            print(f"  + {nomes[dia]:8} {janela}{pausa}")
        db.commit()
    finally:
        db.close()


# ATENÇÃO: PREÇOS E QUANTIDADES SÃO FICTÍCIOS.
#
# A cliente não informou nenhum valor real, e o pacote é negociado caso a caso
# no ato da venda (docs/premissas.md, P3). Os números abaixo são propositalmente
# redondos e improváveis, para que ninguém os confunda com dado do studio numa
# demonstração. As capacidades, sim, são reais e confirmadas (P1).
SERVICOS_DEMO = [
    {
        "nome": "Pilates",
        "duracao_min": 60,
        "preco_centavos": 10_000,  # FICTÍCIO — R$ 100,00
        "capacidade_padrao": 4,  # confirmado (P1)
        "cor": "#06B6D4",
        "modelo_cobranca": ModeloCobranca.MENSALIDADE,
    },
    {
        "nome": "Fisioterapia",
        "duracao_min": 60,
        "preco_centavos": 10_000,  # FICTÍCIO
        "capacidade_padrao": 4,  # confirmado (P1)
        "cor": "#7C2D8E",
        "modelo_cobranca": ModeloCobranca.PACOTE,
        # Sugestões apenas para pré-preencher a venda. NUNCA fonte de verdade:
        # quem define é a doutora no ato. Todos FICTÍCIOS.
        "sugestao_pacote_sessoes": 10,
        "sugestao_pacote_validade_dias": 90,
        "sugestao_pacote_valor_centavos": 100_000,  # FICTÍCIO — R$ 1.000,00
    },
    {
        "nome": "Avaliação",
        "duracao_min": 60,
        "preco_centavos": 10_000,  # FICTÍCIO
        "capacidade_padrao": 1,  # individual — confirmado (P1)
        "cor": "#BB4D00",
        "modelo_cobranca": ModeloCobranca.MENSALIDADE,
    },
]


def seed_servicos() -> None:
    """Cria os serviços de demonstração. Idempotente.

    Os preços são fictícios de propósito — ver comentário em SERVICOS_DEMO.
    """
    db: Session = SessionLocal()
    try:
        for dados in SERVICOS_DEMO:
            nome = str(dados["nome"])
            existe = db.execute(select(Service).where(Service.nome == nome)).scalar_one_or_none()
            if existe is not None:
                print(f"  = {nome:14} já existe, mantido")
                continue
            db.add(Service(**dados))
            print(f"  + {nome:14} capacidade {dados['capacidade_padrao']}")
        db.commit()
    finally:
        db.close()

    print("\n  ATENÇÃO: os preços cadastrados são FICTÍCIOS.")
    print("  A cliente ainda não informou valores reais (docs/premissas.md, P3).\n")


def seed_demo() -> None:
    """Popula o studio de demonstração com dados FICTÍCIOS.

    Idempotente: limpa o que criou antes e recria. Todas as datas são
    relativas a hoje, então o resultado continua fazendo sentido em qualquer
    dia da apresentação.
    """
    from app.services import demo_service

    db: Session = SessionLocal()
    try:
        r = demo_service.semear(db)
    finally:
        db.close()

    print("  Pacientes .................. ", r.pacientes)
    print("  Matrículas ................. ", r.matriculas)
    print("  Sessões .................... ", r.sessoes)
    print("  Reservas ................... ", r.reservas)
    print("  Presenças registradas ...... ", r.presencas)
    print("  Faltas justificadas ........ ", r.faltas_justificadas)
    print("  Faltas não justificadas .... ", r.faltas_nao_justificadas)
    print("  Reposições já feitas ....... ", r.reposicoes_feitas)
    print("  Cancelamentos com motivo ... ", r.cancelamentos)
    print("  Pacotes de fisioterapia .... ", r.pacotes)
    print("  Cobranças pagas ............ ", r.cobrancas_pagas)
    print("  Cobranças pendentes ........ ", r.cobrancas_pendentes)
    print("  Cobranças vencidas ......... ", r.cobrancas_vencidas)
    for aviso in r.avisos:
        print(f"  ! {aviso}")
    print()
    print("  ATENÇÃO: todos estes dados são FICTÍCIOS.")
    print("  Nenhum CPF é válido; os telefones usam prefixo reservado.")
    print()


def limpar_demo() -> None:
    """Remove tudo que o seed de demonstração criou."""
    from app.services import demo_service

    db: Session = SessionLocal()
    try:
        contagem = demo_service.limpar(db)
    finally:
        db.close()
    for chave, qtd in contagem.items():
        print(f"  - {chave:12} {qtd}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    p_seed = sub.add_parser("seed-usuarios", help="cria os usuários de teste")
    p_seed.add_argument(
        "--gerar-senhas",
        action="store_true",
        help="sorteia senha para quem não tiver variável de ambiente definida",
    )

    sub.add_parser("seed-configuracao", help="cria a configuração e a grade de horários")
    sub.add_parser("seed-servicos", help="cria os serviços de demonstração")
    sub.add_parser("seed-demo", help="popula o studio de demonstração (dados fictícios)")
    sub.add_parser("limpar-demo", help="remove os dados de demonstração")

    args = parser.parse_args(argv)
    if args.comando == "seed-usuarios":
        seed_usuarios(gerar=args.gerar_senhas)
    elif args.comando == "seed-configuracao":
        seed_configuracao()
    elif args.comando == "seed-servicos":
        seed_servicos()
    elif args.comando == "seed-demo":
        seed_demo()
    elif args.comando == "limpar-demo":
        limpar_demo()
    return 0


if __name__ == "__main__":
    sys.exit(main())
