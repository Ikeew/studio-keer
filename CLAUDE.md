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
nunca entra. O aluno tem um **horário fixo semanal** (matrícula) e paga
**mensalidade**. A aula de Pilates é em **turma com capacidade**; fisioterapia
e avaliação são individuais.

## Decisões de arquitetura

### Sessão, reserva e matrícula são três coisas distintas

Esta é a decisão central do modelo de dados.

- **`sessions`** — a ocorrência concreta: este serviço, com este instrutor,
  neste horário, com esta capacidade.
- **`bookings`** — o vínculo de um paciente com uma sessão. É aqui que vivem
  presença, falta, cancelamento e remarcação.
- **`enrollments`** — o horário fixo contratado, que gera sessões e reservas
  adiante no tempo, e de onde nasce a cobrança mensal.

Turma com capacidade, atendimento individual, falta de uma pessoa só e
remarcação saem todos desse mesmo modelo, sem caso especial. Colapsar sessão e
reserva numa tabela só quebra assim que duas pessoas dividem o horário.

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

Seed: Segunda a Sexta, 06:00–21:00; cancelamento com 24h de antecedência.
Esses valores são premissas não validadas — ver `docs/premissas.md`.

### Timezone

Tudo em `TIMESTAMPTZ`, gravado em UTC, convertido para `America/Sao_Paulo` na
borda da aplicação. Nunca grave horário local ingênuo: o horário de verão
volta a existir um dia e a agenda inteira desanda.

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
