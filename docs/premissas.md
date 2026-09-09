# Premissas a validar com a cliente

Este documento lista o que foi **assumido** para destravar o desenvolvimento e
que ainda **não foi validado** com a Dra. Belanir. Cada item traz quem confirma
e o custo de mudança.

Levar este arquivo para a reunião. Ao confirmar ou refutar um item, atualize a
coluna **Status** e abra a tarefa correspondente.

Legenda de custo:
**Baixo** = mudar um registro no banco ou um campo na tela, sem deploy.
**Médio** = mudar código de regra de negócio + testes, sem migration.
**Alto** = migration de schema, retrabalho de tela ou de fluxo.

---

## P1 — Capacidade das turmas

**Premissa:** Pilates 5 vagas, Fisioterapia 1, Avaliação 1.

**Origem:** estimativa do time. Não houve levantamento no studio.
**Confirma:** Dra. Belanir (proprietária).

**Perguntas para a reunião:**
- Quantos aparelhos/tapetes existem de fato?
- O limite é o equipamento ou a atenção da instrutora?
- Uma instrutora atende 5 pessoas ao mesmo tempo com segurança?

**Se a resposta for outra:** custo **baixo**. A capacidade é um campo editável
por serviço na tela de Atividades e pode ter override por sessão. Trocar 5 por
4 é editar um registro — sem migration, sem deploy.

**Ressalva:** reduzir a capacidade de um serviço **não** remove reservas já
feitas. Sessões existentes podem ficar acima do novo limite, e o sistema vai
bloquear novas reservas nelas até caírem abaixo. Se a mudança vier depois da
agenda estar populada, a recepção precisa remanejar manualmente.

---

## P2 — Frequência e valor da mensalidade

**Premissa:** o plano é mensal por matrícula, definido pela frequência semanal
(2x/semana, 3x/semana). O valor **não** varia com sessões realizadas e falta
**não** gera desconto. Sessão avulsa gera cobrança própria, separada.

**Origem:** decisão do cliente do projeto, a partir do subtítulo
"Pagamento mensal" no print da agenda. Os valores em si não foram definidos.
**Confirma:** Dra. Belanir.

**Perguntas para a reunião:**
- Quais frequências são vendidas (1x, 2x, 3x, 5x por semana)?
- Qual o valor de cada uma, por modalidade?
- Existe plano trimestral/semestral ou desconto por pacote?
- Existe pacote de sessões (ex.: 10 sessões de fisioterapia) em vez de
  mensalidade? Este é o caso mais provável para **fisioterapia**, que
  costuma ser vendida por pacote fechado, não por mês.
- O mês é fechado no dia 1 ou na data de aniversário da matrícula?

**Se a resposta for outra:** custo **médio a alto**. Frequências e valores são
dados (baixo). Mas **pacote de sessões** é um modelo de cobrança diferente do
de mensalidade: exigiria um saldo de sessões decrementado a cada presença,
com nova tabela e novo fluxo no Financeiro. É o maior risco de retrabalho da
lista — vale perguntar cedo.

---

## P3 — Prazo de cancelamento (24h)

**Premissa:** cancelamento com 24h ou mais de antecedência é `cancelada`;
menos que isso vira `falta`.

**Origem:** convenção de mercado. Não foi validada.
**Confirma:** Dra. Belanir e a recepcionista (que aplica a regra no dia a dia).

**Perguntas para a reunião:**
- O studio hoje cobra falta de aviso em cima da hora? Ou releva?
- O prazo é o mesmo para Pilates (turma) e Fisioterapia (individual)? Uma
  falta em atendimento individual custa mais ao studio: o horário fica ocioso.
- Vale a pena a recepção poder marcar "justificada" manualmente, ignorando o
  prazo? (atestado médico, luto, etc.)

**Se a resposta for outra:** custo **baixo**. O prazo é um registro na
configuração do sistema, em horas. Prazos diferentes por serviço custariam
**médio** (campo por serviço + ajuste na regra).

---

## P4 — Reposição de falta

**Premissa:** falta **justificada** dá direito a uma reposição dentro do mesmo
mês de referência, condicionada a vaga livre. Falta **não justificada** não dá.

**Origem:** decisão do cliente do projeto.
**Confirma:** Dra. Belanir.

**Perguntas para a reunião:**
- Quem decide se a falta é justificada, e com base em quê? Hoje isso é
  critério da recepção ou da proprietária?
- Uma reposição por mês, ou uma por falta justificada? Se o paciente faltar
  três vezes com justificativa, tem direito a três reposições?
- A reposição pode ser em outra modalidade? (faltou Pilates, repõe em Fisio)
- Pode ser com outro instrutor?
- Reposição não usada acumula para o mês seguinte, ou expira?

**Se a resposta for outra:** custo **médio**. A regra vive no serviço de
agendamento e é coberta por testes. O vínculo já está modelado
(`bookings.remarcado_de_id`), então o histórico não se perde — o que muda é
a condição de autorização.

**Ponto em aberto que precisa de decisão explícita:** o sistema **não** vai
inferir "justificada" sozinho. Isso exige um campo que a recepção marca. Se a
Dra. Belanir preferir não ter esse julgamento no sistema, a alternativa é dar
reposição para toda falta, ou para nenhuma.

---

## P5 — Dias e janela de funcionamento

**Premissa:** Segunda a Sexta, 06:00 às 21:00.

**Origem:** os prints mostram apenas Segunda–Sexta a partir das 06:00. O
horário de fechamento foi inferido.
**Confirma:** Dra. Belanir.

**Perguntas para a reunião:**
- O studio abre sábado? Em que janela?
- Existe intervalo de almoço em que não se agenda?
- A janela é a mesma todos os dias?

**Se a resposta for outra:** custo **baixo** para dias e janela — é um registro
de configuração, e habilitar sábado não exige deploy. **Médio** se a janela
variar por dia da semana (ex.: sábado só até 12:00), porque a configuração
passa a ser por dia em vez de global.

---

## P6 — Instrutor obrigatório e somente leitura

**Premissa:** toda sessão tem um instrutor responsável. O instrutor **só
visualiza** a agenda; quem marca presença e falta é a recepção.

**Origem:** decisão do cliente do projeto, refletindo a operação atual onde a
recepção centraliza o registro.
**Confirma:** Dra. Belanir e as fisioterapeutas.

**Perguntas para a reunião:**
- Quantas instrutoras existem? Uma turma pode ter duas?
- A recepção está sempre presente nos horários de atendimento? Se o studio
  abre às 06:00 e a recepção chega às 08:00, **ninguém** registra presença nas
  primeiras duas horas — este é o furo operacional mais provável da regra.
- As instrutoras teriam interesse em marcar presença pelo celular?

**Se a resposta for outra:** custo **médio**. Dar permissão de escrita ao
instrutor é ampliar o RBAC e ajustar a tela dele, sem mexer no modelo de
dados. Já está registrado como evolução futura no CLAUDE.md.

---

## P7 — Cadastro de paciente

**Premissa:** os campos são os dos prints — nome, CPF, data de nascimento,
sexo, estado civil, profissão, e-mail, telefone — mais um campo de
consentimento LGPD. CPF é opcional e único.

**Origem:** print `03-pacientes.png` + exigência de LGPD.
**Confirma:** recepcionista (é quem digita).

**Perguntas para a reunião:**
- "Estado civil" e "profissão" são usados para alguma coisa, ou são herança da
  ficha de papel? Campo que ninguém usa é campo que atrasa o cadastro.
- Falta algum dado que a ficha de papel tem hoje? (contato de emergência,
  convênio, indicação, endereço)
- Paciente menor de idade existe? Se sim, precisa de responsável — e o
  consentimento LGPD tem que ser dele, não do paciente.

**Se a resposta for outra:** custo **alto** se faltarem campos descobertos
tarde (migration + formulário + tela). Vale conferir a ficha física **antes**
da Fase 2. Remover campo não usado é baixo.

---

## P8 — Escopo deliberadamente fora

Registrado aqui para não virar surpresa na apresentação. Nada disso está sendo
construído:

| Fora do escopo | Por quê | O que seria preciso |
|---|---|---|
| Prontuário / evolução clínica | Dado sensível sob a LGPD | Base legal, controle de acesso por profissional, auditoria de leitura, retenção |
| Notificações WhatsApp / e-mail | Confirmado fora | Provedor, custo por mensagem, opt-in |
| Exportação e anonimização LGPD | Fora do escopo atual | Endpoint de portabilidade e rotina de anonimização |
| Acesso do paciente | Sistema é de uso interno | Autenticação externa, superfície pública |
| Emissão de nota fiscal / integração com gateway | Não pedido | Integração fiscal |

**Pergunta para a reunião:** a Dra. Belanir espera alguma dessas? Notificação
de lembrete é o pedido que mais aparece depois da entrega — melhor saber agora
se é expectativa dela.
