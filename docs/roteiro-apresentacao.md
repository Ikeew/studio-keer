# Roteiro de apresentação — 8 minutos

Sequência de demonstração para a avaliação N1, com os cliques exatos.

Começa pelo problema e termina na solução. Os dois momentos mais fortes são a
**turma cheia recusando a quinta pessoa** (minuto 4) e o **painel de
reposições pendentes** (minuto 6) — se o tempo apertar, corte de outro lugar.

---

## ⚠️ ANTES DE COMEÇAR — cinco minutos antes

**Abra o sistema publicado e faça login.** O plano gratuito do Render hiberna
o serviço após 15 minutos sem uso, e a primeira requisição depois disso leva
de **30 a 60 segundos**. Sem esse aquecimento, a banca vê a primeira tela
travada em "Carregando…".

Checklist:

- [ ] Abrir a URL da Vercel e entrar como **recepção** — confirma que a API
      acordou
- [ ] Conferir que a agenda mostra aulas (se estiver vazia, clicar em
      **Atualizar grade**)
- [ ] Abrir **Reposições** e confirmar que há pendências na lista
- [ ] Deixar aberta uma segunda aba no **Dashboard**
- [ ] Ter as três senhas à mão

---

## Minuto 0–1 · O problema

**Fale antes de clicar em qualquer coisa.**

> "O Studio Keer controla os horários em planilha e papel. A dor principal da
> proprietária não é falta de agenda — é acabar com mais gente do que devia
> num horário.
>
> Isso acontece por dois caminhos. Quando alguém falta, ela encaixa a pessoa
> em outro dia, de cabeça, sem contar quantos já estão lá. E quando vende um
> horário fixo, ninguém revisita quantos alunos aquele horário já tem.
>
> Os dois caminhos levam ao mesmo lugar: cinco pessoas numa turma de quatro."

---

## Minuto 1–2 · A agenda como ela é hoje

**Login como recepção** → a tela abre no **Dashboard**.

Aponte os quatro indicadores:

> "Agendamentos de hoje, pacientes ativos, sessões do mês e taxa de ocupação.
> Repare que a ocupação mostra o cálculo embaixo — tantas reservas de tantos
> lugares. Um percentual sozinho não é auditável."

**Clique em Agendamentos.**

> "Esta é a semana. Cada célula mostra a turma, o instrutor e quantas vagas
> restam. Duas coisas para reparar:
>
> Primeiro, o horário pula das onze para as duas — a pausa do almoço não
> aparece, porque o studio não atende. A tela não esconde: a grade nem oferece.
>
> Segundo, cada card diz quantas vagas sobram. A recepção vê isso **antes** de
> oferecer o horário ao paciente, não depois de tentar salvar."

Aponte uma turma com **"Turma cheia"** em vermelho.

---

## Minuto 2–4 · Falta e cancelamento

**Clique numa turma com alunos.**

> "Aqui a recepção registra o que aconteceu. Presente, faltou, faltou com
> justificativa, remarcar, cancelar."

**Marque uma falta justificada** em alguém.

> "Marquei falta justificada. Repare que o sistema não decidiu isso sozinho —
> não existe prazo, nem relógio, nem regra automática. Quem julga é a recepção,
> que é o critério real do studio."

**Cancele outra reserva** e volte à grade.

> "E aqui está a diferença entre faltar e avisar. Quando o paciente avisa que
> não vem, a vaga **libera na hora** — o contador subiu. Quem faltou continua
> ocupando o lugar, porque a aula aconteceu com aquele lugar reservado.
>
> O aviso antecipado não é punido. Ele é aproveitado."

---

## Minuto 4–5 · ⭐ A turma cheia recusa a quinta pessoa

**O momento mais forte da apresentação.** Não corra.

**Vá em Pacientes** → escolha alguém sem matrícula → **Matrículas** → **Nova
matrícula**.

Escolha **Pilates**, o instrutor, um valor, e marque **segunda 08:00** — a
turma que já tem quatro alunos fixos.

**Clique em Matricular.**

Leia a mensagem em voz alta, devagar:

> *"O horário de segunda às 08:00 já tem 4 alunos fixos em Pilates, que é a
> capacidade da turma. **Não é a reserva de hoje que está cheia: é o horário.**
> Escolha outro horário ou libere uma matrícula."*

Então explique:

> "Duas coisas aqui.
>
> A mensagem diz que o problema é o **horário**, não esta reserva. Sem isso, a
> recepcionista tentaria de novo amanhã, e amanhã, e amanhã.
>
> E essa recusa não é uma verificação em código que alguém possa esquecer de
> chamar. É o **banco de dados** que garante. Cada reserva ocupa uma posição
> numerada na turma, e a posição é única. Se duas recepcionistas tentarem a
> última vaga ao mesmo tempo, o banco reprova uma das duas — mesmo que o
> código tenha bug."

---

## Minuto 5–7 · ⭐ Reposições pendentes

**O segundo momento mais forte.**

**Clique em Reposições** na barra lateral.

> "Isto aqui, hoje, **não existe**. Vive na memória da proprietária.
>
> Ela lembra quem faltou, lembra que prometeu repor, e tenta encaixar. Quando
> esquece, o paciente cobra. Quando lembra demais, encaixa em turma cheia."

Aponte um card:

> "Cada falta pendente mostra quem é, quando faltou, o motivo, o telefone para
> ligar, e até quando dá para repor — com a contagem de dias. Prazo de menos
> de uma semana fica destacado."

**Clique em "Ver horários com vaga".**

> "E aqui está o fecho. O sistema lista apenas os horários que **realmente
> têm vaga**, dentro do prazo daquela falta. A recepção liga para o paciente
> já sabendo o que pode oferecer.
>
> Se não houver nenhum, ele diz isso — e não existe caminho para forçar."

**Agende a reposição** clicando num horário.

> "Pronto. A reposição ocupou uma vaga como qualquer outra reserva, e a falta
> saiu da lista. Uma falta gera uma reposição: o banco não deixa repor duas
> vezes a mesma."

---

## Minuto 7–8 · Financeiro e fechamento

**Clique em Financeiro.**

> "Os três totais: recebido, pendente e vencido. 'Vencido' não é um status
> gravado — é calculado na hora, então nunca fica desatualizado esperando
> alguma rotina rodar.
>
> Repare nos vencimentos: cada paciente vence no dia em que começou. Esse
> aqui" — aponte um paciente do dia 31 — "começou dia 31, e o sistema encaixa
> no último dia de cada mês: 31 em agosto, 30 em setembro, 28 em fevereiro."

**Filtre por Vencidos**, depois **marque uma cobrança como paga**.

> "A recepção registra e pode desfazer, se errar. Cancelar uma cobrança —
> perdoar a dívida — é só da proprietária."

### Fechamento

**Saia e entre como instrutor.**

> "E esta é a visão do instrutor: as aulas dele hoje, somente leitura. Ele não
> vê valores, não vê a ficha dos pacientes, não registra presença. Não porque
> a tela esconde, mas porque o servidor recusa.
>
> Resumindo: o studio saiu da planilha, e o overbooking deixou de ser possível
> — não por disciplina, mas porque o banco de dados não permite."

---

## Perguntas prováveis da banca

**"Como vocês calculam a taxa de ocupação?"**
Reservas ativas dividido pela capacidade oferecida no período. Reserva ativa é
agendada, confirmada, presente ou falta. Cancelada não conta, porque a vaga
voltou ao pool. Falta conta, porque o lugar ficou reservado e ninguém mais
pôde usá-lo — a taxa mede ocupação, não comparecimento. O numerador e o
denominador aparecem na tela.

**"E se duas pessoas tentarem a última vaga ao mesmo tempo?"**
Uma passa, a outra recebe erro claro. A garantia é um índice único no banco,
não uma verificação em código. Há teste de concorrência com duas conexões
reais.

**"Por que não guardar o número de vagas ocupadas numa coluna?"**
Porque sai de sincronia. Todo caminho que cria, cancela ou remarca precisaria
atualizá-la, e basta um esquecer para o número mentir em silêncio. Contar é
barato nesta escala.

**"Os dados são reais?"**
Não. São fictícios, gerados por um comando. Nenhum CPF é válido e nenhum
telefone existe — o aviso está na própria tela de login.

**"O que ficou de fora?"**
Prontuário e evolução clínica, deliberadamente: são dados sensíveis sob a
LGPD e exigem tratamento próprio, não um campo a mais numa tabela existente.
Também notificações por WhatsApp e a exportação de dados da LGPD.

**"O que ainda depende da cliente?"**
Está tudo em `docs/premissas.md`, com o custo de mudança de cada item. O maior
é o ciclo de cobrança — adotamos o ciclo por aniversário e isolamos a decisão
num único arquivo, para trocar sem espalhar.
