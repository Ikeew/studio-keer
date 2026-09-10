# Premissas e pendências com a cliente

O que foi **assumido** para destravar o desenvolvimento e o que já foi
**confirmado** pela Dra. Belanir. Cada item traz a origem, quem confirma e o
custo de mudar de ideia.

Levar este arquivo para a reunião. Ao confirmar ou refutar um item, atualize o
**Status** junto com o código.

**Legenda de status:**
✅ Confirmado pela cliente · ⏳ Aguardando resposta · ⚠️ Contraditório, precisa de decisão

**Legenda de custo:**
**Baixo** = mudar um registro no banco ou um campo na tela, sem deploy.
**Médio** = mudar código de regra de negócio + testes, sem migration.
**Alto** = migration de schema, retrabalho de tela ou de fluxo.

---

## Índice

| # | Assunto | Status |
|---|---|---|
| P1 | Capacidade das turmas | ✅ Confirmado — 4 em qualquer serviço |
| P2 | Mensalidade (Pilates) | ✅ Modelo confirmado · ⏳ valores em aberto |
| P3 | Pacote de sessões (Fisioterapia) | ⏳ **Bloqueia o Financeiro** |
| P4 | Prazo de cancelamento (24h) | ⏳ Não validado |
| P5 | Reposição de falta | ⚠️ **Contradição em aberto** |
| P6 | Dias e janela de funcionamento | ✅ Sábado confirmado · ⏳ janela do sábado |
| P7 | Avaliação | ✅ Cobrada à parte · ⏳ obrigatoriedade |
| P8 | Instrutor obrigatório e somente leitura | ⏳ Não validado |
| P9 | Cadastro de paciente | ⏳ Conferir a ficha de papel |
| P10 | Reposição como causa do overbooking | 💡 Hipótese a validar |
| P11 | Escopo deliberadamente fora | — |

---

## P1 — Capacidade das turmas ✅

**Confirmado:** capacidade máxima de **4 em qualquer serviço**. Fisioterapia
também é em grupo de até 4, não individual.

**Isso desmentiu a premissa anterior** (Pilates 5, Fisioterapia 1, Avaliação 1),
que era estimativa do time. Foi corrigido antes de qualquer código ser escrito.

**Como ficou:** `services.capacidade_padrao` com **padrão 4 para todos**,
editável na tela de Atividades, com override opcional por sessão. Não há
número de capacidade escrito em código.

**⏳ Dúvida que a resposta abriu — vale reperguntar:**

"4 em qualquer coisa" inclui a **avaliação**? Uma avaliação inicial de
fisioterapia em grupo de 4 é clinicamente incomum: normalmente é uma conversa
individual, com anamnese. Seguimos a instrução (padrão 4 para todos), mas se
avaliação for 1 na prática, é **um campo na tela** — custo baixo.

**Ressalva que continua valendo:** reduzir a capacidade **não** remove reservas
já feitas. Sessões existentes podem ficar acima do novo limite; o sistema
bloqueia reservas novas até caírem abaixo, mas quem remaneja é a recepção.

---

## P2 — Mensalidade (Pilates) ✅ modelo · ⏳ valores

**Confirmado:** plano fixo mensal por matrícula, definido pela frequência
semanal (2x, 3x). O valor **não** varia com sessões realizadas e falta **não**
gera desconto. A cobrança nasce da matrícula, não da contagem de sessões.
Sessão avulsa gera cobrança própria, separada da mensalidade.

**⏳ Ainda em aberto:**
- Quais frequências são vendidas (1x, 2x, 3x, 5x por semana)?
- Qual o valor de cada uma?
- Existe plano trimestral ou semestral, com desconto?
- O mês fecha no dia 1 ou na data de aniversário da matrícula?

**Custo:** **baixo**. Frequências e valores são dados: a frequência é o número
de horários fixos da matrícula, e o valor é campo. Nada disso está em código.

**O mês de referência é a única parte estrutural.** Se a cobrança for por
aniversário da matrícula em vez de mês-calendário, muda a geração de cobranças
e o significado de "mesmo mês" na regra de reposição — custo **médio**.

---

## P3 — Pacote de sessões (Fisioterapia) ⏳ BLOQUEIA O FINANCEIRO

**Confirmado:** existe pacote — fisioterapia não é vendida por mensalidade.

**Não respondido, e é o essencial:**

1. **Quantas sessões tem um pacote?** (10? 12? varia por caso?)
2. **Tem prazo de validade?** Se sim, contado de quando — da compra ou da
   primeira sessão?
3. **Qual o preço?**

**Nenhum desses valores foi chutado no seed.** O seed usa valores
obviamente fictícios e comentados como tal, justamente para que ninguém os
confunda com dado real na apresentação. Tudo é configurável no cadastro do
serviço.

**Perguntas que vão junto, porque afetam a regra:**

- **Falta consome sessão do saldo?** Ver P5 — pode ser exatamente o que ela
  quis dizer com "de boa". Já é configuração
  (`falta_consome_sessao_do_pacote`), não regra fixa.
- Sobrando sessões no fim da validade, elas expiram ou o paciente perde?
- O pacote tem horário fixo semanal como a mensalidade, ou as sessões são
  marcadas uma a uma conforme a evolução do tratamento?
- Pode comprar um pacote novo antes de terminar o anterior?

**Custo:** os três valores são **baixo** (campos de cadastro). A pergunta do
horário fixo é **média**: muda se o pacote gera sessões recorrentes ou só
saldo.

---

## P4 — Prazo de cancelamento (24h) ⏳

**Premissa:** cancelamento com 24h ou mais de antecedência é `cancelada`;
menos que isso vira `falta`.

**Origem:** convenção de mercado. **Não foi validada.**
**Confirma:** Dra. Belanir e a recepcionista, que aplica a regra no dia a dia.

**Perguntas:**
- O studio hoje cobra falta de aviso em cima da hora, ou releva?
- O prazo é o mesmo para Pilates e Fisioterapia?
- A recepção pode marcar "justificada" manualmente, ignorando o prazo
  (atestado, luto)?

**Custo:** **baixo**. O prazo é um registro de configuração, em horas. Prazos
diferentes por serviço custariam **médio**.

---

## P5 — Reposição de falta ⚠️ CONTRADIÇÃO EM ABERTO

A cliente disse duas coisas incompatíveis sobre quem tem direito a repor.

> **Antes:** "ele pode repor se teve uma justificativa, médica ou algo parecido"
>
> **Agora:** "se o paciente faltar ele pode repor de boa"

**Duas leituras possíveis:**

**(a) A regra mudou.** Qualquer falta dá direito a reposição, justificada ou
não. A resposta nova substitui a antiga.

**(b) As duas valem, para coisas diferentes.** O "de boa" respondia sobre o
**pacote de fisioterapia** — a pergunta era se a falta consome sessão do
saldo. Para a **mensalidade**, continua valendo a exigência de justificativa.

A leitura (b) é plausível porque as duas frases respondiam a perguntas
diferentes, e porque as duas cobranças têm lógicas distintas: na mensalidade a
falta não custa nada ao paciente (ele já pagou o mês), enquanto no pacote a
falta pode queimar uma sessão comprada.

**Como o sistema foi modelado para caber nas duas, sem migration:**

| Peça | Para quê |
|---|---|
| `bookings.justificada` (bool) + `bookings.motivo_justificativa` | Registra o julgamento da recepção. Existe mesmo que a regra não o use. |
| `configuracao.reposicao_exige_justificativa` (bool) | Leitura (a) = `false`, leitura (b) = `true`. Trocar é editar um registro. |
| `configuracao.falta_consome_sessao_do_pacote` (bool) | Responde a pergunta que provavelmente gerou o "de boa". |

Com essas três peças, qualquer combinação das duas leituras é representável
sem tocar em schema. **O padrão do seed é a leitura (b)** — a mais restritiva —
porque afrouxar depois é editar um registro, enquanto apertar uma regra que já
foi divulgada aos pacientes é uma conversa desagradável.

**⏳ Perguntas para desempatar:**

1. "Quando a senhora disse que pode repor 'de boa', estava falando do pacote
   de fisioterapia ou de todo mundo?"
2. Se um paciente da mensalidade falta **sem avisar**, ele repõe?
3. Uma reposição por mês, ou uma por falta? Se faltou três vezes, repõe três?
4. Reposição não usada acumula para o mês seguinte, ou expira?
5. Pode repor em outra modalidade? Com outro instrutor?

**Custo:** **baixo** para trocar entre as leituras (configuração). **Médio**
para as perguntas 3 e 4, que mudam a regra de quantas reposições existem.

**Decisão que o sistema não vai tomar sozinha:** "justificada" é julgamento
humano. A recepção marca. O sistema não infere.

---

## P6 — Dias e janela de funcionamento ✅ sábado · ⏳ janela

**Confirmado:** o studio **atende sábado**.

**⏳ Não respondido:** a janela de horário do sábado. O seed usa **a mesma dos
dias úteis (06:00–21:00)** por ora, o que é quase certamente largo demais —
sábado costuma fechar mais cedo.

**Como ficou:** uma linha por dia da semana em `horarios_funcionamento`, com
`aberto`, `hora_abertura` e `hora_fechamento`. Ajustar o sábado é **editar uma
linha**, sem migration e sem deploy. Domingo entra como fechado.

**⏳ Também em aberto:** existe intervalo de almoço em que não se agenda?

**Custo:** **baixo**.

---

## P7 — Avaliação ✅ cobrança · ⏳ obrigatoriedade

**Confirmado:** a avaliação é um **serviço próprio, com preço próprio**,
cobrada à parte — fora da mensalidade e fora do pacote.

**⏳ Não respondido:** é obrigatória antes da primeira aula?

**Como ficou:** serviço comum na tabela `services`, com cobrança avulsa
própria. **Não** é obrigatória — nada no sistema exige avaliação prévia para
agendar.

**Se for obrigatória:** custo **médio**. Exigiria verificar, no agendamento da
primeira sessão de um paciente, se existe avaliação concluída — regra nova no
serviço de agendamento, sem mudança de schema.

**Ver também P1:** se avaliação é individual e não turma de 4.

---

## P8 — Instrutor obrigatório e somente leitura ⏳

**Premissa:** toda sessão tem um instrutor responsável. O instrutor **só
visualiza** a agenda; quem marca presença e falta é a recepção.

**Confirma:** Dra. Belanir e as fisioterapeutas.

**Perguntas:**
- Quantas instrutoras existem? Uma turma pode ter duas?
- **A recepção está presente em todos os horários de atendimento?** Se o
  studio abre às 06:00 e a recepção chega às 08:00, ninguém registra presença
  nas primeiras horas. Este é o furo operacional mais provável da regra —
  e agora vale para o sábado também.
- As instrutoras teriam interesse em marcar presença pelo celular?

**Custo:** **médio**. Dar escrita ao instrutor amplia o RBAC e ajusta a tela
dele, sem tocar no modelo de dados.

---

## P9 — Cadastro de paciente ⏳

**Premissa:** os campos dos prints — nome, CPF, data de nascimento, sexo,
estado civil, profissão, e-mail, telefone — mais consentimento LGPD. CPF
opcional e único.

**Confirma:** a recepcionista, que é quem digita.

**Perguntas:**
- "Estado civil" e "profissão" servem para alguma coisa, ou são herança da
  ficha de papel? Campo que ninguém usa atrasa o cadastro.
- Falta algum dado que a ficha de papel tem? (contato de emergência, convênio,
  indicação, endereço)
- Existe paciente menor de idade? Se sim, precisa de responsável — e o
  consentimento LGPD é dele, não do paciente.

**Custo:** **alto** se faltarem campos descobertos tarde. **Vale conferir a
ficha física antes da Fase 2.** Remover campo não usado é baixo.

---

## P10 — Reposição como causa do overbooking 💡

**Hipótese do time, ainda não confirmada com a cliente.**

A dor número um da Dra. Belanir é acabar com mais gente do que devia num
horário. Ela também disse que sempre cuidou pessoalmente das reposições e que
sempre tenta repor.

**Hipótese:** as reposições são a principal causa do overbooking. Ela encaixa
quem faltou num horário que já estava cheio, controlando de cabeça.

**Por que é plausível:** as matrículas são estáveis — o horário fixo não muda
sozinho. A variação na ocupação vem justamente do que é encaixado fora da
grade: reposição, remarcação e avulsa. E o encaixe é decidido de cabeça, sem
contagem.

**Como o sistema responde, independente da hipótese estar certa:**

1. **Reposição ocupa vaga como qualquer reserva.** Sem exceção, sem "encaixe".
2. A tela mostra os horários com vaga **antes** de a recepção oferecer a
   reposição ao paciente.
3. Sem vaga no mês, o sistema diz isso explicitamente e **não deixa forçar**.
4. Painel de **"reposições pendentes"**, que hoje vive na cabeça dela.

**Perguntas para confirmar a hipótese:**
- Quando aconteceu de ter gente demais num horário, era reposição encaixada?
- Já aconteceu de **vender** um horário fixo para uma quinta pessoa num
  horário que já tinha quatro? (é a outra causa possível, ver abaixo)
- Com que frequência isso acontece — toda semana, todo mês?

**Ressalva importante:** mesmo que a hipótese esteja certa, ela não é a única
causa possível. **Overbooking também nasce na venda da matrícula**, não só na
reserva: se cinco pessoas têm horário fixo às segundas 08:00 e a capacidade é
4, toda ocorrência nasce lotada e nenhuma reposição está envolvida. Por isso a
capacidade é verificada **também na criação da matrícula**, não só na da
reserva.

---

## P11 — Escopo deliberadamente fora

Registrado para não virar surpresa na apresentação:

| Fora do escopo | Por quê | O que seria preciso |
|---|---|---|
| Prontuário / evolução clínica | Dado sensível sob a LGPD | Base legal, acesso por profissional, auditoria de leitura, retenção |
| Notificações WhatsApp / e-mail | Confirmado fora | Provedor, custo por mensagem, opt-in |
| Exportação e anonimização LGPD | Fora do escopo atual | Endpoint de portabilidade e rotina de anonimização |
| Acesso do paciente | Sistema é de uso interno | Autenticação externa, superfície pública |
| Nota fiscal / gateway de pagamento | Não pedido | Integração fiscal |
| **Forçar reserva acima da capacidade** | Contraria a dor principal | Ver abaixo |

**Sobre o último item:** não existe botão de "encaixar mesmo assim". É
deliberado — um sistema que permite furar o limite não resolve o overbooking,
apenas o documenta. Se a Dra. Belanir pedir essa saída, ela deve ser
**exclusiva do perfil admin e registrada em auditoria**, para que o encaixe
deixe de ser invisível. Vale perguntar se ela sente falta disso.

**Pergunta geral:** ela espera alguma dessas? Lembrete por WhatsApp é o pedido
que mais aparece depois da entrega — melhor saber agora se é expectativa.
