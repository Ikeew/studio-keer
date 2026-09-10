# CLAUDE.md — contexto e convenções do projeto

Instruções para agentes e desenvolvedores trabalhando neste repositório.
Comece pelo [README](README.md) para rodar o projeto.

## Regra inegociável

**`referencia-figma/` é somente leitura.** Não edite, mova nem renomeie nada
dentro dela. São os prints do protótipo, usados como referência visual. Não
existe código-fonte do Figma Make — o export nunca foi obtido, então todo o
frontend é escrito do zero. Ver `referencia-figma/README.md` para o mapa das
telas e a lista do que nos prints **não** deve ser seguido.

## O domínio em uma tela

Studio de Pilates e Fisioterapia. A recepcionista opera o sistema; o paciente
nunca entra.

Pilates e fisioterapia são **em turma, capacidade 4**. Avaliação é
**individual (1)**.

Há **dois modelos de cobrança, em duas tabelas distintas**: `enrollments`
(mensalidade do Pilates, com horário fixo semanal) e `packages` (pacote de
fisioterapia). Avaliação é serviço próprio, cobrado à parte. O modelo completo
está em `docs/modelo-de-dados.md`.

**A dor número um da cliente é overbooking**: acabar com mais gente do que
devia num horário. Toda decisão de agenda se subordina a isso.

## Decisões de arquitetura

### Sessão, reserva e matrícula são três coisas distintas

Esta é a decisão central do modelo de dados.

- **`sessions`** — a ocorrência concreta: este serviço, com este instrutor,
  neste horário, com esta capacidade.
- **`bookings`** — o vínculo de um paciente com uma sessão. É aqui que vivem
  presença, falta, cancelamento e reposição.
- **`enrollments`** — o contrato: mensalidade com horário fixo, ou pacote de
  sessões. É de onde nasce a cobrança.

Turma com capacidade, falta de uma pessoa só, reposição e os dois modelos de
cobrança saem todos desse mesmo modelo, sem caso especial. Colapsar sessão e
reserva numa tabela só quebra assim que duas pessoas dividem o horário.

### Reposição ocupa vaga como qualquer reserva

**Sem exceção, sem "encaixe".** Não existe caminho no sistema que fure a
capacidade — nem para reposição, nem para admin.

A hipótese de trabalho é que as reposições encaixadas de cabeça são a causa
principal do overbooking (`docs/premissas.md`, P10). Contar reposição contra a
capacidade é, sozinho, o que resolve a dor principal da cliente.

**A trava é do banco, não da aplicação.** Cada reserva ocupa uma `posicao`
(1..capacidade) com `UNIQUE (session_id, posicao) WHERE status <> 'cancelada'`,
mais `CHECK (posicao <= capacidade_sessao)`. Índice único não conta, então a
posição é o que transforma contagem em unicidade. O índice ser **parcial** é o
que faz cancelar devolver a vaga na mesma transação.

**Capacidade se verifica em três lugares, não um:**

1. Ao criar qualquer reserva — o índice é a garantia; o `FOR UPDATE` na sessão
   só evita que a segunda recepcionista tome erro em vez de esperar.
2. **Ao criar um horário de matrícula.** Cinco matrículas fixas num horário de
   capacidade 4 fazem toda ocorrência nascer lotada, sem reposição nenhuma
   envolvida. Esquecer este ponto deixa o furo aberto na venda.
3. Ao reduzir capacidade — avisa, não remove reserva existente.

Se não houver vaga, o sistema **diz isso explicitamente** e não oferece saída.
Um sistema que permite furar o limite apenas documenta o overbooking.

### O que é derivado nunca é armazenado

Calcule, não guarde: idade (de `data_nascimento`), última visita, total de
sessões, vagas livres (`capacidade - reservas ativas`) e cobrança **vencida**
(`status = pendente AND vencimento < hoje`).

Um contador desnormalizado de vagas sai de sincronia no primeiro cancelamento
concorrente, e um status `vencido` gravado exige um job para virar a cada
meia-noite — e mente até o job rodar.

### Presença e pagamento são eixos independentes

Não misture. Nunca crie um estado que combine os dois.

```
presença:   agendada → confirmada → presente | falta
pagamento:  pendente → pago | cancelado
```

"Aguardando", nos prints, é confirmação de **presença**.

### Nada de regra de negócio hardcoded

Dias e janela de funcionamento, prazo de cancelamento e capacidade padrão são
**configuração no banco**, não constantes no código. Habilitar sábado ou mudar
a capacidade de uma turma tem que ser edição de registro, não deploy.

Seed: segunda a **sábado** 06:00–21:00 com **pausa 12:00–14:00** (domingo
fechado); cancelamento com 24h de antecedência; capacidade 4 em turma, 1 na
avaliação.

**Não há tela de configuração nesta entrega.** Os valores vêm do seed e se
mudam por comando ou SQL. Agenda funcionando vale mais que painel de ajustes.

**A regra de reposição é configuração, não código**, mesmo agora que a
contradição foi resolvida (P5): `reposicao_exige_justificativa = true` e
`falta_consome_sessao_do_pacote = false` são registros no banco, não
constantes.

### Ciclo de cobrança vive em um arquivo só

`app/services/ciclo_service.py` é o ÚNICO lugar que sabe como um mês de
mensalidade começa e termina. Adotamos o ciclo por **aniversário** (premissa a
confirmar, `docs/premissas.md` P2); trocar para calendário é reescrever
`_competencia_do_mes` e nada mais.

**Nunca calcule data de vencimento fora dele.** Use `dia_seguro()` para
qualquer data de dia fixo: quem começou dia 31 vence 30 em abril e 28 em
fevereiro, e `date(2026, 4, 31)` levanta ValueError. É bug silencioso — passa
em todo teste escrito em março.

### Janela de reposição ≠ ciclo de cobrança

Os dois só se parecem por usarem a palavra "mês", e acoplá-los foi considerado
e descartado (`docs/premissas.md`, P2).

- **Ciclo de cobrança** é financeiro: competência e vencimento. Fase 5.
- **Janela de reposição** é operacional: quanto tempo o paciente tem para
  remarcar. Vive em `configuracao.janela_reposicao`, com padrão
  `mes_calendario`.

### Gerador da grade: idempotente e com horizonte

`gerar_grade` materializa **8 semanas** à frente. Curto demais quebra a
reposição (a Fase 3 definiu que a disponibilidade só enxerga sessão
materializada); longo demais vira lixo quando a matrícula muda.

Rodar duas vezes não duplica: sessão é reaproveitada por equivalência, e o
índice único parcial `(enrollment_id, session_id)` garante no banco que uma
matrícula tem no máximo uma reserva por sessão — inclusive após execução
interrompida no meio.

**O gerador não fura capacidade.** Se a turma encheu por avulsas, ele reporta
em `sem_vaga` em vez de forçar.

### Encerrar e suspender: futuro sim, passado nunca

Reservas **futuras** da matrícula são canceladas (lugar ocupado por quem não
vem mais bloqueia reposição). Reservas com **presença ou falta registrada
ficam intactas** — são fato consumado, e sumir com a falta apagaria o direito
à reposição.

Reativar reverifica a capacidade: o lugar pode ter sido vendido enquanto a
matrícula esteve suspensa.

### Pacote: negociado por venda, e o saldo tem definição exata

Um pacote é **negociado no ato da venda** — a doutora define sessões, preço e
validade caso a caso. `services.sugestao_pacote_*` serve só para pré-preencher
o formulário; **nunca** é fonte de verdade. Depois de vendido, um `package`
não relê nada do serviço.

> **Só reserva com status `presente` consome sessão do saldo.**
> `agendada`, `confirmada`, `cancelada` e `falta` não consomem.

Essa contagem vive em **uma única função**. Não a reescreva numa consulta
nova — é o tipo de regra que alguém quebra sem perceber.

Como falta não consome saldo, **a validade é a única trava do pacote**: quem
falta muito mantém o saldo intacto para sempre. Toda consulta de saldo checa
validade junto, e a tela mostra **saldo e expiração lado a lado** — saldo sem
validade faz a recepção prometer o que o sistema depois recusa.

Preço e quantidade de pacote **não têm valor real no seed**: são
obviamente fictícios e comentados como tal, para ninguém confundir com dado
da cliente na apresentação.

### Timezone

Tudo em `TIMESTAMPTZ`, gravado em UTC, convertido para `America/Sao_Paulo` na
borda da aplicação. Nunca grave horário local ingênuo: o horário de verão
volta a existir um dia e a agenda inteira desanda.

**Datetime sem fuso vindo da API é horário do STUDIO, não do servidor.** O
formulário manda `2026-09-14T08:00:00` pensando em oito da manhã em São Paulo;
`astimezone()` num datetime ingênuo aplicaria o fuso do servidor, que em
container é UTC. Isso já quebrou de verdade: 08:00 virava 05:00 e era recusado,
enquanto 13:00 virava 10:00 e criava turma dentro da pausa. A conversão está
no schema de entrada, com teste de regressão.

### Enum de coluna: use `coluna_enum(...)`, nunca `String(...)`

`Mapped[MeuEnum]` sobre uma coluna `String` faz a anotação mentir: o valor
volta do banco como `str` e toda comparação `x.status is MeuEnum.ALGO` fica
False em silêncio. Em memória funciona, então o bug só aparece depois de um
reload. Há teste de regressão em `tests/test_enums.py`.

## Decisões de escopo

### Instrutor é somente leitura

Quem marca presença e falta é a **recepção**. O instrutor apenas visualiza a
agenda. Isso simplifica o RBAC e reflete a operação real, onde a recepção
centraliza o registro.

**Evolução futura:** dar permissão de escrita ao instrutor é ampliar o RBAC e
ajustar a tela dele — não mexe no modelo de dados.

**Risco operacional conhecido:** se o studio abre às 06:00 e a recepção chega
depois, ninguém registra presença nas primeiras horas. Levantado em
`docs/premissas.md` (P6) para validar com a cliente.

### Instrutor é obrigatório na sessão

`sessions.professional_id` é `NOT NULL` e o campo é obrigatório no formulário.
Os prints omitem o instrutor na grade, mas **a interface deve mostrá-lo** —
sem isso o perfil de instrutor não tem o que ler.

### Dado clínico está fora

Prontuário, evolução e atestado não entram nesta entrega. São dados sensíveis
sob a LGPD e exigem tratamento próprio. Não adicione esses campos a `patients`
"só para adiantar": isso muda a classificação de risco da tabela inteira.

### Autenticação

Token JWT de 12 horas, sem refresh token. O papel vai no payload mas a
autorização **relê o banco**, para que desativar ou rebaixar alguém tenha
efeito imediato em vez de esperar o token expirar.

Rota nova precisa de proteção **nos dois lados**: `require_papel(...)` no
backend (é a que vale) e `ACESSO_POR_ROTA` no frontend (só esconde o menu).
Esconder item de menu não é controle de acesso.

Usuário de teste se cria por `python -m app.cli seed-usuarios`, com senha do
ambiente — **nunca** por migration, e **nunca** com senha no repositório.

O raciocínio completo dessas escolhas está em `docs/decisoes-tecnicas.md`.

## Convenções de código

### Backend

- SQLAlchemy 2.0 declarativo tipado: `Mapped[...]` e `mapped_column()`. Nada
  de estilo 1.x.
- Camadas: `api/` só faz HTTP (validação, status, autorização); regra de
  negócio vive em `services/`; `models/` não conhece Pydantic.
- Schemas de entrada e de saída são **separados** (`PatientCreate` /
  `PatientRead`). Nunca exponha um model do SQLAlchemy direto.
- Dinheiro é **inteiro em centavos** (`preco_centavos`). Float em dinheiro
  erra o arredondamento, e o financeiro é a parte que a proprietária confere.
- Toda migration passa por `alembic revision --autogenerate` e é **revisada à
  mão** antes do commit — o autogenerate não detecta renomeação de coluna, ele
  gera um drop seguido de um add, o que apaga dados.
- `ruff check`, `ruff format` e `mypy` (strict) precisam passar.

### Frontend

- Estado de servidor é do **TanStack Query**. Não replique resposta de API em
  `useState`.
- Formulários com react-hook-form + zod; o schema zod espelha o Pydantic.
- Import absoluto via `@/`.
- Cores só pelos tokens do `tailwind.config.ts`. Nunca escreva um hex direto
  no componente — a paleta foi extraída por amostragem dos prints e vive num
  lugar só.
- Interface **inteira em português**, incluindo os nomes de rota.

### Nomenclatura

A interface diz **"Paciente"**, nunca "Cliente" (os prints usam "Clientes" no
menu; foi corrigido). O produto é **"Studio Keer"** — o "Studio Pilates &
Fisio" dos prints era placeholder.

Código, tabelas e colunas em português, seguindo o domínio, com exceção dos
nomes de tabela já estabelecidos em inglês (`users`, `patients`, `services`,
`sessions`, `bookings`, `enrollments`, `charges`).

## Ao mexer nas premissas

`docs/premissas.md` lista o que foi assumido sem validação com a cliente. Se
uma dessas premissas for confirmada ou refutada na reunião, **atualize o
arquivo** junto com o código. Ele é o registro de por que o sistema é como é.
