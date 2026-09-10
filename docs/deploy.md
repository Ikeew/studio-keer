# Deploy

Backend e banco no **Render**, frontend na **Vercel**. O deploy foi antecipado
de propósito: problema de infraestrutura descoberto na véspera da
apresentação não tem conserto, e as três fases já entregues encontraram três
erros que só apareceram rodando de verdade.

**Custo: zero.** Todos os planos usados são gratuitos.

---

## O que já está pronto no repositório

| Arquivo | Para quê |
|---|---|
| `render.yaml` | Provisiona banco e API de uma vez (Blueprint) |
| `backend/start.sh` | Aplica migrations e sobe respeitando `$PORT` |
| `backend/Dockerfile` | Imagem usada nos dois ambientes |
| `frontend/vercel.json` | Build e o **rewrite de SPA** |
| `frontend/.env.production.example` | A variável que a Vercel precisa |

Três armadilhas já foram resolvidas antes do primeiro deploy:

**1. A URL do banco.** Render e Railway entregam `postgres://...`, que o
SQLAlchemy 2.0 recusa; e `postgresql://` usaria o psycopg2, que não está
instalado. A app subiria e morreria na primeira query. `Settings` normaliza
para `postgresql+psycopg://`, com teste.

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

### 2. Backend e banco no Render

1. Painel do Render → **New** → **Blueprint**.
2. Selecione o repositório. Ele lê o `render.yaml` e propõe **um banco** e
   **um serviço web**.
3. Em `CORS_ORIGINS`, ponha **qualquer valor** por enquanto
   (`https://exemplo.com`). Voltaremos aqui no passo 4.
4. **Apply**. O primeiro build leva de 5 a 10 minutos.

Ao terminar, anote a URL: `https://studio-keer-api.onrender.com`.

**Confira:**

```bash
curl https://studio-keer-api.onrender.com/api/v1/health
# {"status":"ok","database":"ok"}
```

`database: ok` prova que as migrations rodaram e o banco responde.

### 3. Frontend na Vercel

1. Painel da Vercel → **Add New** → **Project** → o repositório.
2. **Root Directory: `frontend`** ← o passo mais fácil de esquecer. Sem isso
   a Vercel procura o `package.json` na raiz e o build falha.
3. Framework: Vite (detectado automaticamente).
4. Environment Variables:

   | Nome | Valor |
   |---|---|
   | `VITE_API_URL` | `https://studio-keer-api.onrender.com/api/v1` |

5. **Deploy**. Anote a URL: `https://studio-keer.vercel.app`.

### 4. Fechar o CORS

De volta ao Render, no serviço da API → **Environment**:

```
CORS_ORIGINS = https://studio-keer.vercel.app
```

Salve. O Render reinicia sozinho.

**Sem este passo o sistema parece quebrado sem dar erro:** a tela abre, o
login não funciona, e a mensagem só aparece no console do navegador.

### 5. Criar os usuários

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

### 6. Conferir no ar

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

**O banco gratuito do Render expira em 90 dias.** Suficiente para a N1, mas
anote a data. Para uso real do studio, o plano pago é obrigatório — e aí entra
também rotina de backup, que não existe no gratuito.

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

**Backup do banco.** Não existe no plano gratuito. Antes de qualquer uso real
com dados de paciente, isto deixa de ser opcional — inclusive por LGPD.
