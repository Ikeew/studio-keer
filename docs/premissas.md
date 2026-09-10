# Premissas e pendências com a cliente

O que foi **assumido** para destravar o desenvolvimento e o que já foi
**confirmado** pela Dra. Belanir. Cada item traz a origem, quem confirma e o
custo de mudar de ideia.

Levar este arquivo para a reunião. Ao confirmar ou refutar um item, atualize o
**Status** junto com o código.

**Legenda de status:**
✅ Confirmado pela cliente · ⏳ Aguardando resposta · ⚠️ Contraditório · ❌ Premissa descartada

**Legenda de custo:**
**Baixo** = mudar um registro no banco ou um campo na tela, sem deploy.
**Médio** = mudar código de regra de negócio + testes, sem migration.
**Alto** = migration de schema, retrabalho de tela ou de fluxo.

---

## Índice

| # | Assunto | Status |
|---|---|---|
| P1 | Capacidade das turmas | ✅ **Fechado** — 4 em turma, 1 na avaliação |
| P2 | Mensalidade (Pilates) | ✅ Vencimento · ⏳ **ciclo: aniversário adotado** |
| P3 | Pacote de sessões (Fisioterapia) | ✅ **Fechado** — negociado por venda |
| P4 | Prazo de cancelamento (24h) | ❌ **Descartada** — premissa do time, não da cliente |
| P5 | Reposição de falta | ✅ **Contradição resolvida** |
| P6 | Dias e janela de funcionamento | ✅ **Fechado** — inclui sábado e pausa |
| P7 | Avaliação | ✅ Cobrada à parte · ⏳ obrigatoriedade |
| P8 | Instrutor obrigatório e somente leitura | ⏳ Não validado |
| P9 | Cadastro de paciente | ⏳ Conferir a ficha de papel |
| P10 | Reposição como causa do overbooking | 💡 Hipótese a validar |
| P11 | Escopo deliberadamente fora | — |

---

## P1 — Capacidade das turmas ✅ FECHADO

**Confirmado:**

| Serviço | Capacidade |
|---|---|
| Pilates | 4 |
| Fisioterapia | 4 (também é em turma, não individual) |
| **Avaliação** | **1** (atendimento individual) |

**Duas premissas do time foram desmentidas ao longo do caminho**, e as duas
antes de virar código:

1. "Pilates 5, Fisioterapia 1" — errado nos dois. Fisioterapia é em turma.
2. "4 em qualquer coisa" incluiria a avaliação — não inclui. A dúvida foi
   levantada porque avaliação inicial em grupo é clinicamente incomum
   (é anamnese, conversa individual), e a cliente confirmou: o "qualquer
   coisa" dela era sobre Pilates e fisioterapia.

**Como ficou:** `services.capacidade_padrao` por serviço, editável na tela de
Atividades, com override opcional por sessão. Nenhum número de capacidade
escrito em código.

**Ressalva que continua valendo:** reduzir a capacidade **não** remove reservas
já feitas. Sessões existentes podem ficar acima do novo limite; o sistema
bloqueia reservas novas até caírem abaixo, mas quem remaneja é a recepção.

---

## P2 — Mensalidade (Pilates) ✅ vencimento · ⏳ ciclo

**Confirmado:** plano fixo mensal por matrícula, definido pela frequência
semanal (2x, 3x). O valor **não** varia com sessões realizadas e falta **não**
gera desconto. Sessão avulsa gera cobrança própria, separada.

**Confirmado também:** cada paciente vence **no dia em que começou** — cada um
no seu dia, **mês cheio, sem proporcional**.

### ⏳ O que ainda falta é o ciclo, não o vencimento

Sutil, e fácil de confundir com a pergunta já respondida. O **vencimento** está
definido; o **mês de referência** (a competência) não.

Duas leituras, para um paciente que começou em **15/03**:

| | Competência | Vencimento |
|---|---|---|
| **(a) Calendário** | 01/03 a 31/03 | dia 15 |
| **(b) Aniversário** | 15/03 a 14/04 | dia 15 |

**Adotamos (b), o ciclo por aniversário**, e está **implementado** como
premissa a confirmar.

A decisão vive num arquivo só: `app/services/ciclo_service.py`. Nenhum outro
ponto do código calcula data de competência ou de vencimento. Trocar para
calendário é reescrever `_competencia_do_mes`; o resto do sistema não sabe
que ciclo existe.

**Por quê:** é a leitura consistente com o que ela já respondeu. Ela disse
"mês cheio a partir do dia em que começou" e "cada um no seu dia". Se fosse
calendário, quem entrasse dia 28 pagaria o mês inteiro por três dias de
aula — que é exatamente o proporcional que ela disse **não** fazer.

**Não é pendência bloqueante.** O Financeiro é a Fase 5, e a decisão está
tomada com justificativa.

### A janela de reposição NÃO depende disto

Uma versão anterior deste documento concluía que, com ciclo por aniversário,
"repor dentro do mês" passaria a significar "dentro do ciclo do paciente".
**Isso foi considerado e descartado**: acoplava duas coisas que só se parecem
por usarem a palavra "mês".

| | O que é | Onde vive |
|---|---|---|
| **Ciclo de cobrança** | Competência e vencimento | Financeiro (Fase 5) |
| **Janela de reposição** | Quanto tempo o paciente tem para remarcar | Operação (Fase 4) |

Quando a cliente disse "dentro do mesmo mês", falava como pessoa fala — e
pessoa que diz "mesmo mês" quase sempre quer dizer **mês do calendário**. Nada
indica que ela pense a reposição atrelada à data de vencimento de cada aluno.

`configuracao.janela_reposicao` é configuração própria, com três valores:
`mes_calendario` (padrão), `ciclo_do_paciente` e `sem_prazo`. Trocar é editar
um registro, sem migration, caso ela confirme o contrário.

**Ganho prático:** a Fase 4 deixou de depender desta pendência. O ciclo de
cobrança voltou a ser problema só da Fase 5.

**Onde isto ainda importa:** geração da cobrança mensal, que precisa saber
onde um ciclo termina.

**⏳ Ainda em aberto, de menor peso:**
- Quais frequências são vendidas (1x, 2x, 3x, 5x por semana)?
- Qual o valor de cada uma?
- Existe plano trimestral ou semestral, com desconto?

**Custo:** trocar (b) por (a) é **médio** — muda a geração de cobranças e a
janela da reposição, sem migration. Frequências e valores são **baixo**: a
frequência é o número de horários fixos da matrícula, e o valor é campo.

---

## P3 — Pacote de sessões (Fisioterapia) ✅ FECHADO

**Confirmado:** o pacote é **negociado no ato da venda**, caso a caso,
conforme a necessidade clínica. Quem define número de sessões, preço e
validade é a doutora, na hora — não o cadastro.

**Isso encerra as três perguntas que bloqueavam o Financeiro.** Não existe
mais "quantas sessões tem um pacote": tem as que foram vendidas naquele
pacote.

**Como ficou:**

- `packages` é a entidade do **pacote vendido**, com os valores capturados no
  ato: sessões contratadas, valor, validade, data da compra, quem registrou.
- `services.sugestao_pacote_*` existe **apenas para pré-preencher** o
  formulário de venda. Nunca é obrigatório e nunca é fonte de verdade.
- Os valores do pacote vendido são **snapshot**. Mudar a sugestão do serviço
  amanhã não toca em nada já vendido.
- **Validade opcional.** Em branco significa que vale até acabar o saldo.
- A cobrança nasce no ato da venda, com o valor negociado. Não é mensal.

**⏳ Ainda em aberto (menor, não bloqueia):**
- Sobrando sessões no vencimento da validade, o paciente perde ou renegocia?
- Pode comprar pacote novo antes de terminar o anterior?
- O pacote tem horário fixo semanal, ou as sessões são marcadas uma a uma
  conforme a evolução? O modelo assume **uma a uma**.

**Consequência que a resposta de P5 criou — vale atenção:**

Como falta **não** consome sessão do saldo, a **validade é a única trava do
pacote**. Um paciente que falta muito mantém o saldo intacto indefinidamente.
Um pacote vendido sem validade e com muitas faltas nunca termina.

Por isso a validade é respeitada em toda consulta de saldo, e a tela mostra
**saldo e data de expiração juntos** — ver saldo sem ver validade dá a
impressão errada de que ainda dá para agendar.

---

## P4 — Prazo de cancelamento ❌ PREMISSA DESCARTADA

**A regra das 24h nunca existiu no negócio.** Ela foi inventada pelo time ao
montar as premissas iniciais, a partir de convenção de mercado. A cliente
**nunca mencionou antecedência**, em momento nenhum.

Fica registrado assim, e não como "pendente", para o histórico ser honesto:
não é uma pergunta esperando resposta, é uma premissa nossa que foi retirada.

**Por que não foi levada à reunião:** perguntar "qual é o seu prazo de
cancelamento?" induziria uma regra que o negócio dela não tem. A pergunta
carrega a resposta.

**O critério real é justificativa, não relógio.** Ela disse: repõe se teve
justificativa médica ou algo parecido. Quem classifica é a **recepção**,
marcando justificada sim ou não — que é o que ela já faz hoje.

### O que mudou no sistema

| Antes (premissa nossa) | Agora (realidade da cliente) |
|---|---|
| `configuracao.cancelamento_antecedencia_horas = 24` | Coluna **removida** |
| Cancelar em cima da hora virava `falta` automaticamente | Cancelamento **nunca** vira falta sozinho |
| O relógio classificava | A **recepção** classifica |

`bookings.cancelado_em` continua existindo, mas como **informação, não como
regra**: serve para saber quando a vaga liberou.

### O valor do aviso antecipado é operacional, não punitivo

Esta é a parte que importa de verdade. Quando o paciente avisa que não vem,
**a vaga libera e passa a poder receber uma reposição** — igual a qualquer
outra vaga, sem tratamento especial.

É assim que o cancelamento antecipado gera valor no studio dela: não punindo
quem avisa, mas devolvendo o horário para quem precisa repor. A implementação
disso é literal — o índice de capacidade ignora reservas canceladas, então
cancelar devolve a posição ao pool na mesma transação.

---

## P5 — Reposição de falta ✅ CONTRADIÇÃO RESOLVIDA

A cliente havia dito duas coisas incompatíveis:

> **Antes:** "ele pode repor se teve uma justificativa, médica ou algo parecido"
>
> **Agora:** "se o paciente faltar ele pode repor de boa"

**Resolvido: valia a leitura (b).** O "de boa" respondia sobre o **pacote de
fisioterapia** — se a falta queima uma sessão do saldo comprado — e não sobre
afrouxar a exigência de justificativa para reposição.

**Como ficou:**

| Configuração | Valor | Significado |
|---|---|---|
| `reposicao_exige_justificativa` | `true` | Só falta justificada dá direito a repor |
| `falta_consome_sessao_do_pacote` | `false` | Falta **não** desconta do saldo do pacote |

As duas continuam sendo **configuração no banco**, não regra em código. A
contradição foi resolvida, mas o mecanismo que permitia acomodá-la fica: se a
regra mudar, é editar um registro.

### Definição precisa de "sessão consumida"

Registrado aqui porque é o tipo de definição que alguém quebra sem perceber:

> **Só reserva com status `presente` decrementa o saldo do pacote.**
> Reserva `agendada`, `confirmada`, `cancelada` ou com `falta` **não** conta.

Note que isso difere do que o modelo previa antes, quando `agendada` e
`confirmada` também seguravam saldo. A cliente decidiu que não: o saldo só
cai quando a sessão realmente acontece.

**Efeito colateral aceito:** um paciente pode ter mais sessões marcadas do que
o saldo comprado, já que reservas futuras não reservam saldo. Na prática o
limite é a validade, e a recepção vê o saldo na tela. Se isso incomodar, a
correção é somar as reservas futuras na conta — custo baixo, sem migration.

**⏳ Ainda em aberto:**
1. Uma reposição por mês, ou uma por falta? Se faltou três vezes, repõe três?
2. Reposição não usada acumula para o mês seguinte, ou expira?
3. Pode repor em outra modalidade? Com outro instrutor?

**Decisão que o sistema não toma sozinho:** "justificada" é julgamento
humano. A recepção marca. O sistema não infere.

---

## P6 — Dias e janela de funcionamento ✅ FECHADO

**Confirmado:** segunda a **sábado**, **06:00 às 21:00**, com **pausa das
12:00 às 14:00**. Domingo fechado.

O sábado tem a mesma janela dos dias úteis, incluindo a pausa.

**Como ficou:** uma linha por dia da semana em `horarios_funcionamento`, com
`aberto`, `hora_abertura`, `hora_fechamento`, `pausa_inicio` e `pausa_fim`.
Mudar qualquer coisa é **editar uma linha** — sem migration, sem deploy.

**Observação, não pendência:** um sábado de 06:00 às 21:00 é uma jornada
longa, e sábado à noite é horário de baixa procura na maioria dos studios. O
sistema não impede nada — apenas oferece grade vazia onde não houver
matrícula. Se na prática o sábado esvaziar depois das 12:00, fechar mais cedo
é editar uma linha e deixa a agenda mais legível.

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

**Resolvido em P1:** a avaliação é **individual** (capacidade 1).

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

**Confirmado:** **contato de emergência** (nome e telefone) — a cliente já
coleta hoje. Entrou no cadastro.

**Premissa:** os demais campos são os dos prints — nome, CPF, data de
nascimento, sexo, estado civil, profissão, e-mail, telefone — mais
consentimento LGPD. CPF opcional (ela pode não ter de todo mundo), único
quando informado, e **validado de verdade** (dígitos verificadores, não só
contagem de caracteres).

**Confirma:** a recepcionista, que é quem digita.

**⏳ Perguntas:**
- "Estado civil" e "profissão" servem para alguma coisa, ou são herança da
  ficha de papel? Campo que ninguém usa atrasa o cadastro.
- Falta algum outro dado que a ficha de papel tem? (convênio, indicação,
  endereço)
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

**A pergunta não será levada à cliente, deliberadamente.** Os três pontos de
verificação cobrem as duas causas de qualquer jeito, então a resposta não
mudaria nenhuma linha do sistema. Fica registrada como diagnóstico, não como
pendência.

**A segunda causa é provavelmente a principal.** Overbooking também nasce na
**venda da matrícula**, não só na reserva: se cinco pessoas têm horário fixo
às segundas 08:00 e a capacidade é 4, toda ocorrência nasce lotada e nenhuma
reposição está envolvida. Studio que cresceu com planilha vende a quinta vaga
sem perceber, e ninguém revisita o contrato depois.

É por isso que a capacidade é verificada **também na criação do horário de
matrícula** — o ponto que a hipótese da reposição, sozinha, não cobriria.

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
