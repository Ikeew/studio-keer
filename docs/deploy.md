# Deploy

Backend no **Render**, banco no **Neon**, frontend na **Vercel**. O deploy foi antecipado
de propósito: problema de infraestrutura descoberto na véspera da
apresentação não tem conserto, e as três fases já entregues encontraram três
erros que só apareceram rodando de verdade.

**Custo: zero.** Todos os planos usados são gratuitos.

---

## O que já está pronto no repositório

| Arquivo | Para quê |
|---|---|
| `render.yaml` | Provisiona a API (Blueprint) |
| `neon.ts` | Declara o banco no Neon (projeto `quiet-bar-22053390`, branch `production`) |
| `backend/start.sh` | Aplica migrations e sobe respeitando `$PORT` |
| `backend/Dockerfile` | Imagem usada nos dois ambientes |
| `frontend/vercel.json` | Build e o **rewrite de SPA** |
| `frontend/.env.production.example` | A variável que a Vercel precisa |

Três armadilhas já foram resolvidas antes do primeiro deploy:

**1. A URL do banco.** Render e Railway entregam `postgres://...`, que o
SQLAlchemy 2.0 recusa; e `postgresql://` usaria o psycopg2, que não está
instalado. A app subiria e morreria na primeira query. `Settings` normaliza
para `postgresql+psycopg://`, com teste. O Neon entrega `postgresql://` e
cai na mesma normalização.

**1b. Pooled para a app, direta para as migrations.** O Neon dá duas URLs:
`DATABASE_URL` (host com `-pooler`, PgBouncer em modo transação) e
`DATABASE_URL_UNPOOLED`. A API usa a primeira; o Alembic usa a segunda
quando ela existe (`Settings.url_migrations`), porque PgBouncer em modo
transação não guarda estado de sessão e migration falha por ali sem
mencionar pooling.

**2. A porta.** O provedor injeta `$PORT` e muda o valor entre deploys. Porta
fixa faz o health check falhar e o serviço nunca ficar pronto — sem erro
visível no log da aplicação. `start.sh` lê `$PORT`.

**3. O refresh em rota interna.** Sem `rewrites`, recarregar `/agenda` na
Vercel devolve **404**: o servidor procura um arquivo nesse caminho. O
`vercel.json` manda tudo para o `index.html`.

---

## O que preciso de você

Não tenho como criar contas nem acessar painéis. Preciso de:

1. **Repositório no GitHub** (o histórico está pronto, falta o `git push`).
2. **Conta no Render** — grátis, login com o GitHub.
3. **Conta na Vercel** — grátis, login com o GitHub.

Se preferir que eu automatize, me passe um **token de API** de cada um e eu
faço pelo CLI. Sem token, o passo a passo abaixo leva uns 15 minutos.

---

## Passo a passo

### 1. Publicar o repositório

```bash
gh repo create studio-keer --private --source=. --remote=origin --push
```

Sem o `gh`: crie o repositório vazio no GitHub e depois

```bash
git remote add origin git@github.com:<usuario>/studio-keer.git
git push -u origin main
```

### 2. Banco no Neon

Já provisionado (`neon init` + `neon deploy` na raiz). Para obter as URLs de
novo:

```bash
neon env pull        # grava DATABASE_URL e DATABASE_URL_UNPOOLED em .env.local
```

O `.env.local` é ignorado pelo git. Nunca versione essas URLs: carregam a
senha do banco.

### 3. Backend no Render

1. Painel do Render → **New** → **Blueprint**.
2. Selecione o repositório. Ele lê o `render.yaml` e propõe **um serviço
   web** (o banco não é mais do Render).
3. Preencha as variáveis `sync: false`:

   | Nome | Valor |
   |---|---|
   | `DATABASE_URL` | a URL **pooled** do Neon (host com `-pooler`) |
   | `DATABASE_URL_UNPOOLED` | a URL **direta** do Neon (sem `-pooler`) |
   | `CORS_ORIGINS` | **qualquer valor** por enquanto (`https://exemplo.com`); voltaremos no passo 5 |

   Trocar as duas URLs de lugar não quebra na hora, mas tira o pooling da API
   ou põe as migrations atrás do PgBouncer.
4. **Apply**. O primeiro build leva de 5 a 10 minutos.

Se o serviço já existia com o banco do Render, basta trocar `DATABASE_URL`,
criar `DATABASE_URL_UNPOOLED` em **Environment** e salvar. O banco antigo do
Render não é apagado por sair do `render.yaml`; apague-o no painel depois de
conferir o Neon (e de copiar os dados, se havia algum que importe).

Ao terminar, anote a URL: `https://studio-keer-api.onrender.com`.

**Confira:**

```bash
curl https://studio-keer-api.onrender.com/api/v1/health
# {"status":"ok","database":"ok"}
```

`database: ok` prova que as migrations rodaram e o banco responde.

### 4. Frontend na Vercel

1. Painel da Vercel → **Add New** → **Project** → o repositório.
2. **Root Directory: `frontend`** ← o passo mais fácil de esquecer. Sem isso
   a Vercel procura o `package.json` na raiz e o build falha.
3. Framework: Vite (detectado automaticamente).
4. Environment Variables:

   | Nome | Valor |
   |---|---|
   | `VITE_API_URL` | `https://studio-keer-api.onrender.com/api/v1` |

5. **Deploy**. Anote a URL: `https://studio-keer.vercel.app`.

### 5. Fechar o CORS

De volta ao Render, no serviço da API → **Environment**:

```
CORS_ORIGINS = https://studio-keer.vercel.app
```

Salve. O Render reinicia sozinho.

**Sem este passo o sistema parece quebrado sem dar erro:** a tela abre, o
login não funciona, e a mensagem só aparece no console do navegador.

### 6. Criar os usuários

No Render, serviço da API → **Shell**:

```sh
SEED_ADMIN_SENHA='...' \
SEED_RECEPCAO_SENHA='...' \
SEED_INSTRUTOR_SENHA='...' \
python -m app.cli seed-usuarios

python -m app.cli seed-configuracao
python -m app.cli seed-servicos
```

Use senhas reais e anote-as. Os comandos são idempotentes.

> Os **preços dos serviços são fictícios** (`docs/premissas.md`, P3). Não
> apresente como se fossem dados do studio.

### 7. Conferir no ar

- Abrir a URL da Vercel e entrar com os três perfis.
- **Recarregar a página em `/agenda`** — se der 404, o `vercel.json` não foi
  aplicado.
- Criar um paciente e conferir que ele aparece depois de recarregar.

---

## Limitações do plano gratuito

**O serviço hiberna após 15 minutos sem uso.** A primeira requisição depois
disso leva de 30 a 60 segundos, e a tela fica "Carregando…" nesse tempo.

**Isto importa na apresentação.** Abra o sistema alguns minutos antes de
começar, para a banca não ver a primeira tela travada.

**O banco do Neon suspende após 5 minutos sem uso** e acorda na primeira
query, com algumas centenas de milissegundos a mais. Não expira como o
gratuito do Render, e o `pool_pre_ping` da engine descarta a conexão que o
Neon fechou ao suspender. Somado à hibernação da API, abrir o sistema antes
da apresentação continua valendo.

---

## Deploys seguintes

Push na `main` → Render e Vercel refazem o deploy sozinhos. As migrations
rodam no boot pelo `start.sh`.

**Cuidado com migration destrutiva.** O `start.sh` usa `set -e`: se a
migration falhar, o container não sobe e o Render mantém a versão anterior no
ar — o que é o comportamento certo. Mas uma migration que apaga coluna
funciona sem erro e leva os dados junto. Toda migration continua sendo
revisada à mão antes do commit (ver CLAUDE.md).

---

## Evolução futura

**Job agendado para a grade recorrente.** Hoje a geração é manual, com aviso
na interface quando o horizonte está acabando (`AvisoDeGrade`). Um cron job
no Render eliminaria o passo manual:

```
0 3 1 * *   python -m app.cli gerar-grade
```

Ficou de fora porque cron no Render exige plano pago, e o aviso na tela já
ataca o modo de falha real, que era a grade esvaziar **sem ninguém perceber**.

**Backup do banco.** O Neon tem restauração por ponto no tempo, mas a janela
do plano gratuito é curta. Antes de qualquer uso real com dados de paciente,
uma rotina de backup própria deixa de ser opcional — inclusive por LGPD.
