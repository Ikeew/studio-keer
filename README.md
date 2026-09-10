# Studio Keer — Sistema de Agendamento

Sistema web interno de agendamento para o **Studio Keer Pilates e Fisioterapia**.
Substitui o controle atual em planilhas e papel.

Projeto acadêmico (avaliação N1), equipe de 5 pessoas.

## Quem usa

O sistema é de **uso interno**. Pacientes não têm acesso: marcam, remarcam e
faltam através da recepção.

| Perfil | O que faz |
|---|---|
| **Proprietária** (admin) | Visão geral da operação e controle financeiro |
| **Recepcionista** | Usuária principal: agenda, presença, faltas, remarcações, pagamentos |
| **Fisioterapeuta / Instrutor** | Visualiza a agenda do dia (**somente leitura** nesta entrega) |

## Stack

**Backend** — Python 3.12 · FastAPI · PostgreSQL 16 · SQLAlchemy 2.0 (tipado) ·
Alembic · Pydantic v2 · JWT + bcrypt · pytest + httpx · [uv](https://docs.astral.sh/uv/)

**Frontend** — React 18 · Vite · TypeScript · TailwindCSS · React Router ·
TanStack Query · react-hook-form + zod

**Infra** — docker-compose para desenvolvimento · deploy em Render/Railway
(backend + banco) e Vercel (frontend)

## Rodando localmente

Requisitos: Docker e Docker Compose.

```bash
git clone <repo> && cd studio-keer
docker compose up
```

- Frontend: http://localhost:5173
- API: http://localhost:8000 — documentação em http://localhost:8000/docs

O backend roda `alembic upgrade head` antes de subir, então o banco já sobe
migrado. O Dashboard mostra um cartão "Status da instalação" que confirma se o
caminho frontend → API → Postgres está fechado.

### Se a porta 5432 já estiver em uso

É comum já haver um Postgres na máquina. Copie `.env.example` para `.env` na
raiz e troque a porta:

```bash
cp .env.example .env
# edite POSTGRES_PORT=5433
```

Só o mapeamento no host muda; os containers continuam falando entre si pela
rede interna do compose.

## Desenvolvendo fora do Docker

**Backend:**

```bash
cd backend
cp .env.example .env          # ajuste DATABASE_URL e gere um SECRET_KEY real
uv sync                       # instala tudo, incluindo o Python 3.12
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

## Verificações

Os testes usam um Postgres real (não SQLite) e criam sozinhos o database
`keer_test` — basta ter o banco no ar (`docker compose up db`).

```bash
cd backend
uv run pytest                 # testes
uv run ruff check .           # lint
uv run ruff format .          # formatação
uv run --with mypy mypy app   # tipos (strict)

cd frontend
npm run build                 # inclui typecheck (tsc -b)
```

> Se o editor acusar "package não instalado" no `pyproject.toml`, ele está
> apontando para o interpretador errado. Selecione `backend/.venv/bin/python`.

## Estrutura

```
studio-keer/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/            configuração, segurança, dependências
│   │   ├── models/          SQLAlchemy
│   │   ├── schemas/         Pydantic
│   │   ├── api/v1/          routers por módulo
│   │   ├── services/        regras de negócio
│   │   └── db/              session, base declarativa
│   ├── alembic/             migrations
│   └── tests/
├── frontend/src/
│   ├── pages/               uma por rota
│   ├── components/          layout + ui reutilizável
│   ├── features/            agenda, pacientes, financeiro
│   ├── api/                 client axios + hooks do TanStack Query
│   └── types/
├── referencia-figma/        prints do protótipo — SOMENTE LEITURA
├── docs/premissas.md        o que ainda precisa ser validado com a cliente
└── docker-compose.yml
```

## Fases

| Fase | Entrega | Estado |
|---|---|---|
| **0** | Fundação: build, banco, migrations, shell de navegação | **concluída** |
| **1** | Autenticação JWT e perfis de acesso | **concluída** |
| **2** | Cadastro de pacientes e de serviços | **concluída** |
| **3** | Agenda semanal: sessões, reservas, presença, falta, remarcação | **concluída** |
| 4 | Matrículas e geração recorrente de sessões | |
| 5 | Financeiro: mensalidades, cobranças avulsas, baixa de pagamento | |
| 6 | Dashboard com indicadores reais e agenda do instrutor | |
| 7 | Testes de ponta a ponta, seed de demonstração, deploy | |

Cada fase entrega algo demonstrável. As decisões de arquitetura e de escopo
estão em [CLAUDE.md](CLAUDE.md); o modelo de dados em
[docs/modelo-de-dados.md](docs/modelo-de-dados.md); as de infraestrutura e
segurança, em [docs/decisoes-tecnicas.md](docs/decisoes-tecnicas.md).

## Criando os usuários de acesso

Depois de subir o sistema pela primeira vez, crie os três perfis. As senhas
vêm do ambiente — **nenhuma senha fica no repositório**:

```bash
docker compose exec \
  -e SEED_ADMIN_SENHA='...' \
  -e SEED_RECEPCAO_SENHA='...' \
  -e SEED_INSTRUTOR_SENHA='...' \
  backend python -m app.cli seed-usuarios
```

Para desenvolvimento, `--gerar-senhas` sorteia e imprime as senhas de quem não
tiver variável definida:

```bash
docker compose exec backend python -m app.cli seed-usuarios --gerar-senhas
```

O comando é idempotente e **não** sobrescreve a senha de quem já existe.

Depois, crie a configuração e os serviços de demonstração:

```bash
docker compose exec backend python -m app.cli seed-configuracao
docker compose exec backend python -m app.cli seed-servicos
```

> Os **preços dos serviços são fictícios**. A cliente ainda não informou
> valores reais, e o pacote é negociado no ato da venda
> ([docs/premissas.md](docs/premissas.md), P3). Não use na apresentação como
> se fossem dados do studio.

| E-mail | Perfil | Enxerga |
|---|---|---|
| `admin@studiokeer.com.br` | Proprietária | Tudo |
| `recepcao@studiokeer.com.br` | Recepção | Tudo exceto administração de usuários |
| `instrutor@studiokeer.com.br` | Instrutor | Só a agenda, somente leitura |

## Escopo

### Incluído em LGPD

Hash de senha (bcrypt), controle de acesso por perfil, `audit_log` das
operações, exclusão lógica (soft delete) e campo de consentimento no cadastro
do paciente.

### Fora do escopo desta entrega

- **Dado clínico** (queixa, evolução, atestado). É a exclusão mais relevante:
  sob a LGPD isso é **dado pessoal sensível** (art. 5º, II) e exige base legal
  própria, restrição de acesso ao profissional responsável, auditoria de
  leitura e política de retenção. Entraria como fase dedicada, não como
  campo extra numa tela existente.
- **Notificações** por WhatsApp ou e-mail.
- **Exportação e anonimização** de dados pessoais.
- **Acesso do paciente** ao sistema.

## Premissas ainda não validadas

Parte já foi confirmada pela cliente: capacidade 4 em qualquer serviço,
atendimento aos sábados, mensalidade para Pilates e pacote para fisioterapia.

Continuam em aberto os valores do pacote (quantas sessões, validade, preço), a
janela do sábado, o prazo de cancelamento — e uma **contradição sobre a regra
de reposição**, que o sistema acomoda por configuração até ser resolvida.

Estão em **[docs/premissas.md](docs/premissas.md)**, com o custo de mudança de
cada um. Esse documento é a pauta da reunião com a Dra. Belanir.
