# Como trabalhamos com Git

Somos 5 pessoas mexendo no mesmo repositório. Este documento existe para que
ninguém perca trabalho nem passe a tarde resolvendo conflito.

Se você está aprendendo Git agora: leia até o fim uma vez, depois use como
consulta. As três regras que mais evitam problema estão no fim.

---

## A regra principal

**Ninguém commita direto na `main`.** Nem uma correção de typo.

Toda mudança nasce em uma branch, vira pull request, é revisada por outra
pessoa e só então entra na `main`. A `main` precisa estar sempre funcionando —
é dela que sai a apresentação para a banca.

---

## Branches

Sempre parta da `main` atualizada:

```bash
git checkout main
git pull
git checkout -b feature/agenda-semanal
```

### Como nomear

| Prefixo | Quando usar | Exemplo |
|---|---|---|
| `feature/` | Funcionalidade nova | `feature/login-jwt` |
| `fix/` | Correção de bug | `fix/vagas-negativas` |
| `chore/` | Configuração, dependência, build | `chore/pipeline-testes` |
| `docs/` | Só documentação | `docs/manual-recepcao` |

Nome curto, em minúsculas, com hífen. Descreva **o que faz**, não o seu nome:
`feature/cadastro-paciente`, não `feature/joao`.

### Branch pequena e de vida curta

Uma branch por tarefa. Abra o pull request em **até dois ou três dias**.

Isto não é preciosismo: branch que fica duas semanas aberta acumula diferença
em relação à `main` e vira exatamente o conflito gigante que queremos evitar.
Se a tarefa é grande, quebre em partes que entram separadas.

---

## Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/pt-br/):

```
<tipo>(<escopo opcional>): <o que faz, no imperativo>

<por que, se não for óbvio>
```

Tipos: `feat` (funcionalidade), `fix` (correção), `chore` (infra/config),
`docs`, `test`, `refactor`.

**Bom:**

```
feat(agenda): impedir reserva acima da capacidade da turma

A checagem roda dentro da transação porque duas recepcionistas podem
reservar o mesmo horário ao mesmo tempo.
```

**Ruim:** `alteracoes`, `fix`, `agora vai`, `wip`.

Regras práticas:

- Mensagem em **português**, no **imperativo**: "adiciona", não "adicionado".
- Um commit = uma ideia. Não misture correção de bug com formatação.
- Commite com frequência. Commit pequeno é fácil de revisar e de desfazer.
- **O histórico vai ser lido pela banca.** Escreva pensando nisso.

---

## Pull request

```bash
git push -u origin feature/agenda-semanal
```

Abra o PR no GitHub e descreva:

- **O que** muda e **por quê**
- **Como testar** (que tela abrir, que passos seguir)
- Print, se mexeu em interface

### Antes de pedir revisão

Rode as verificações. PR que quebra o build desperdiça o tempo de quem revisa:

```bash
cd backend && uv run pytest && uv run ruff check . && uv run --with mypy mypy app
cd frontend && npm run build
```

### Revisão

**Todo PR precisa da aprovação de outro integrante.** Ninguém aprova o próprio.

Quem revisa: leia o código, rode na sua máquina se mexeu em algo sensível,
pergunte o que não entendeu. Comentário é sobre o código, nunca sobre a pessoa.

Quem recebe: revisão não é crítica pessoal. Se discordar, responda com o
argumento técnico — essa conversa é metade do aprendizado do projeto.

Depois de aprovado, faça **merge pelo GitHub** e apague a branch.

---

## Mantendo sua branch atualizada

Se a sua branch está aberta há mais de um dia, traga a `main` para dentro dela:

```bash
git checkout main
git pull
git checkout feature/sua-branch
git merge main
```

Fazendo isso todo dia, você resolve conflitos pequenos em vez de um enorme
no fim.

> Existe também `git rebase`, que deixa o histórico mais limpo. **Não use
> nesta equipe por enquanto**: rebase reescreve commits e, em branch
> compartilhada, isso apaga trabalho de outra pessoa. `merge` é mais seguro
> para quem está começando.

---

## Quando dá conflito

Conflito **não é erro seu**. Acontece quando duas pessoas editam a mesma
região do mesmo arquivo. É rotina.

O Git avisa:

```
CONFLICT (content): Merge conflict in frontend/src/pages/Agenda.tsx
Automatic merge failed; fix conflicts and then commit the result.
```

### Como resolver

**1. Veja quais arquivos estão em conflito:**

```bash
git status
```

**2. Abra cada arquivo.** O Git marca a região disputada:

```
<<<<<<< HEAD
código que está na SUA branch
=======
código que veio da main
>>>>>>> main
```

**3. Decida o que fica.** Pode ser um lado, o outro, ou uma combinação dos
dois. **Apague as linhas `<<<<<<<`, `=======` e `>>>>>>>`** — elas não são
código e quebram o build se sobrarem.

Na dúvida sobre o que o outro lado fazia: **fale com quem escreveu**. Trinta
segundos de conversa valem mais que meia hora adivinhando.

**4. Marque como resolvido e finalize:**

```bash
git add frontend/src/pages/Agenda.tsx
git commit
```

**5. Rode o projeto antes de dar push.** Merge que compila ainda pode estar
logicamente errado, se você escolheu o lado errado do conflito.

### Deu ruim no meio do merge

Enquanto não commitou, dá para voltar ao estado anterior sem perder nada:

```bash
git merge --abort
```

### Como evitar conflito

- Puxe a `main` todo dia.
- Branch curta, PR rápido.
- Avise no grupo quando for mexer em arquivo compartilhado
  (`routes.tsx`, `tailwind.config.ts`, `docker-compose.yml`).
- Divida as tarefas por módulo, não por arquivo: duas pessoas na mesma tela
  ao mesmo tempo é conflito garantido.

---

## O que nunca vai para o repositório

Já estão no `.gitignore`, mas confira antes de `git add .`:

- `.env` — **contém senha e chave de assinatura**
- `.venv/`, `node_modules/` — pesados e recriáveis com `uv sync` / `npm install`
- `dist/`, `__pycache__/`, caches em geral

Se você commitou um `.env` por engano, **avise a equipe imediatamente**.
Remover o arquivo em um commit seguinte **não basta**: ele continua no
histórico e a chave precisa ser trocada.

Use `git add <arquivo>` em vez de `git add .` sempre que puder. Assim você
enxerga o que está commitando.

---

## Situações comuns

**Commitei na `main` sem querer, ainda não dei push:**

```bash
git branch feature/minha-mudanca   # salva o trabalho numa branch
git reset --hard origin/main       # limpa a main local
git checkout feature/minha-mudanca
```

> `git reset --hard` **descarta** alterações não commitadas. Só rode depois de
> criar a branch acima.

**Preciso trocar de tarefa e meu trabalho está pela metade:**

```bash
git stash          # guarda
git stash pop      # devolve depois
```

**Quero desfazer o último commit mas manter as alterações:**

```bash
git reset --soft HEAD~1
```

**Não sei em que estado estou:** `git status` responde quase sempre. Quando
não resolver, **pergunte no grupo antes de tentar comando que você não
conhece** — a maioria dos casos de trabalho perdido começa assim.

---

## As três regras

1. **Nunca commite na `main`.** Sempre branch + pull request.
2. **Puxe a `main` todo dia.** Conflito pequeno é fácil; grande é uma tarde.
3. **Na dúvida, pergunte antes de rodar.** Nenhum commit vale um dia perdido.
