# Arquitetura do Studio Keer

Este documento explica **por que** o sistema é como é. Foi escrito para quem
nunca viu o código — não pressupõe conhecimento do projeto, e cada decisão vem
com o problema que ela resolve.

O sistema substitui o controle em planilhas e papel de um studio de Pilates e
Fisioterapia. Quem opera é a recepcionista; o paciente nunca entra.

---

## O problema que dá forma a tudo

A dor número um da proprietária é **overbooking**: acabar com mais gente do
que devia num horário. Ela controla as reposições de cabeça e, quando alguém
falta, encaixa a pessoa em outro dia — às vezes num horário que já estava
cheio.

Quase toda decisão estrutural deste sistema existe para tornar isso
impossível. Onde houver conflito entre "mais flexível" e "não deixa furar a
capacidade", o segundo vence.

---

## 1. Matrícula, sessão e reserva são três tabelas

A tentação inicial é ter uma tabela de "agendamentos": paciente, horário,
status. Funciona até duas pessoas dividirem o mesmo horário — e no Pilates
elas sempre dividem, porque a aula é em turma de quatro.

O sistema separa três conceitos que são realmente distintos:

| Tabela | O que é | Exemplo |
|---|---|---|
| **`enrollments`** | O **contrato**: o horário fixo que o paciente comprou | "Maria paga mensalidade e tem segunda e quarta às 8h" |
| **`sessions`** | A **ocorrência**: esta aula, com este instrutor, com esta capacidade | "Pilates de segunda 14/09 às 8h, com a Dra. Belanir, 4 lugares" |
| **`bookings`** | O **vínculo**: um paciente dentro de uma ocorrência | "Maria está na aula de 14/09 às 8h, e faltou" |

### Por que a separação importa

**Falta é de uma pessoa, não da turma.** Se sessão e reserva fossem a mesma
linha, marcar a falta da Maria afetaria as outras três alunas.

**Capacidade pertence à ocorrência.** A turma de segunda pode ter 4 lugares e
a de terça 3, porque um aparelho quebrou. Isso vive em `sessions.capacidade`,
não no contrato nem no cadastro do serviço.

**O contrato sobrevive à ocorrência.** Maria pode suspender a matrícula em
janeiro e voltar em março; as aulas de janeiro continuam no histórico dela.

**Reposição cabe sem caso especial.** É só mais um `booking` numa `session` —
com um campo apontando para a falta que ele cobre.

---

## 2. A capacidade é garantida pelo banco, não pelo código

Esta é a decisão técnica mais importante do projeto.

### Por que verificar em código não basta

O caminho ingênuo é: contar quantas reservas a sessão tem, e se for menos que
a capacidade, inserir mais uma.

```
recepcionista A: conta 3 de 4 → tem vaga → insere
recepcionista B: conta 3 de 4 → tem vaga → insere
resultado: 5 pessoas numa turma de 4
```

As duas leram antes de qualquer uma escrever. Nenhuma fez nada errado, e o
sistema — que existe para impedir exatamente isso — deixou passar.

### A solução: transformar contagem em unicidade

Bancos de dados não sabem garantir "no máximo quatro". Mas sabem garantir
**"este valor não se repete"**, e fazem isso de forma absoluta.

Então cada reserva recebe uma **posição na turma** — 1, 2, 3 ou 4 — e a
posição é única por sessão:

```sql
UNIQUE (session_id, posicao) WHERE status <> 'cancelada'
```

Agora as duas recepcionistas calculam a mesma posição 4, as duas tentam
inserir, e **o banco reprova uma**. Não há como as duas passarem, mesmo que o
código tenha bug, mesmo com dez recepcionistas simultâneas.

Uma segunda trava fecha o resto: cada reserva guarda a capacidade da turma no
momento da marcação, com `CHECK (posicao <= capacidade_sessao)`. Se um erro de
programação tentasse gravar a posição 5 numa turma de 4, o banco recusaria.

### O detalhe que faz o cancelamento funcionar

O índice é **parcial** — a cláusula `WHERE status <> 'cancelada'`. Quando uma
reserva é cancelada, ela sai do índice, e a posição volta a estar livre na
mesma transação.

É isso que dá valor ao aviso antecipado: quem avisa que não vem **libera o
lugar para quem precisa repor**, automaticamente. O sistema não pune quem
avisa; ele aproveita o aviso.

### Três pontos de verificação, não um

Contar reposição contra a capacidade resolve metade do problema. A outra
metade nasce antes, no balcão:

> Se cinco pessoas têm horário fixo às segundas 08:00 numa turma de 4, **toda
> ocorrência nasce lotada**. Nenhuma reposição está envolvida — o overbooking
> foi *vendido*, meses antes.

Por isso a capacidade é verificada em três lugares:

1. **Ao criar qualquer reserva** — inclusive reposição, sem exceção.
2. **Ao vender um horário fixo** — o ponto acima.
3. **Ao reduzir a capacidade** — aqui o sistema apenas **avisa**. Escolher
   quem perde a vaga é decisão humana.

E não existe botão de "encaixar mesmo assim". Um sistema que permite furar o
limite apenas documenta o overbooking em vez de impedi-lo.

---

## 3. O que é derivado nunca é armazenado

Vários números poderiam ser guardados em colunas, e nenhum é:

| Valor | Como é obtido |
|---|---|
| Vagas livres | `capacidade − reservas ativas`, contado na consulta |
| Saldo de um pacote | `sessões contratadas − sessões com presença` |
| Cobrança **vencida** | `pendente E vencimento < hoje` |
| Idade do paciente | calculada da data de nascimento |
| Taxa de ocupação | contada no período pedido |

### Por que

**Contador sai de sincronia.** Um campo `vagas_ocupadas` precisa ser
atualizado em toda reserva, cancelamento, falta e remarcação. Basta um caminho
esquecer — ou uma transação falhar no meio — e o número mente. Pior: mente em
silêncio, e a recepção confia nele.

**Status calculado por relógio precisa de alguém para virá-lo.** Se "vencido"
fosse um status gravado, algum processo teria de rodar toda meia-noite
mudando as cobranças que venceram. Enquanto ele não roda, a tela mostra uma
cobrança vencida como se estivesse em dia. Sendo derivado, ela está correta a
qualquer instante, sem processo nenhum.

**O custo é irrelevante nesta escala.** Um studio tem dezenas de aulas por
semana, não milhões. Contar é barato; estar errado é caro.

---

## 4. Presença e pagamento nunca se misturam

São dois eixos independentes, e o sistema nunca cria um estado que combine os
dois:

```
Presença   (bookings):  agendada → confirmada → presente | falta
Pagamento  (charges):   pendente → pago | cancelado
```

A pessoa pode ter vindo à aula e não ter pago. Pode ter pago o mês inteiro e
faltado a todas as aulas. Os dois fatos são verdadeiros ao mesmo tempo e não
se determinam.

Um enum único com `presente_pago`, `presente_devendo`, `faltou_pago`… teria o
produto de todos os estados, e cada regra nova multiplicaria a tabela.

---

## 5. Dois modelos de cobrança convivendo

O studio vende de duas formas completamente diferentes:

| | **Mensalidade** (Pilates) | **Pacote** (Fisioterapia) |
|---|---|---|
| O que se compra | Horário fixo semanal, por mês | N sessões negociadas |
| Quem define o valor | Tabela de preços | **A doutora, no ato da venda** |
| Cobrança | Uma por mês | Uma só, na venda |
| Como as aulas nascem | Geradas da grade semanal | Marcadas uma a uma |
| Termina quando | A matrícula é encerrada | Saldo zera **ou a validade vence** |

### Por que duas tabelas e não uma com um campo "tipo"

Um pacote não tem horário fixo, não tem vigência mensal e não gera cobrança
periódica. O que ele tem — sessões contratadas, validade, data da compra — não
existe na mensalidade.

Uma tabela única teria mais colunas exclusivas de cada tipo do que colunas
compartilhadas, e cada linha nasceria com metade dos campos vazios. São
`enrollments` e `packages`, separadas.

### Snapshot: o contrato não relê o catálogo

Quando um pacote é vendido, o número de sessões, o preço e a validade são
**copiados** para a venda. Depois disso, o pacote nunca mais consulta o
cadastro do serviço.

O motivo é concreto: a doutora vai reajustar preços. No dia em que fizer isso,
todo pacote já vendido tem de continuar valendo o que foi combinado com o
paciente. Vale o mesmo para o valor da mensalidade.

### A validade é a única trava do pacote

A cliente decidiu que **falta não consome sessão** — quem faltou repõe sem
perder o que comprou. A consequência é que um paciente que falta muito mantém
o saldo intacto indefinidamente.

Por isso toda consulta de saldo verifica a validade junto, e a tela mostra
**saldo e data de expiração lado a lado**. Mostrar "restam 4 sessões" sem dizer
que o pacote venceu ontem faria a recepção prometer algo que o sistema depois
recusa.

---

## 6. A janela de reposição é separada do ciclo de cobrança

Duas coisas que parecem a mesma porque as duas usam a palavra "mês":

- **Ciclo de cobrança** é financeiro. Define o período que a mensalidade
  cobre e quando ela vence.
- **Janela de reposição** é operacional. Define quanto tempo o paciente tem
  para remarcar a aula perdida.

Houve a tentação de unificá-las: adotamos o ciclo de cobrança por aniversário
(quem começou dia 15 tem competência de 15 a 14), e pareceu natural concluir
que "repor dentro do mês" passaria a significar "dentro do ciclo dele".

**Isso foi considerado e descartado.** Quando a cliente disse "dentro do mesmo
mês", falava como pessoa fala — e pessoa que diz "mesmo mês" quase sempre quer
dizer mês do calendário. Nada indica que ela pense a reposição atrelada à data
de vencimento de cada aluno.

Acoplar as duas teria feito uma decisão financeira ainda não confirmada
travar uma funcionalidade operacional. Separadas, cada uma evolui sozinha: a
janela é uma configuração no banco, com três valores possíveis, e trocar é
editar um registro.

---

## 7. Regra de negócio não vive em código

Valores que a cliente pode querer mudar são **registros no banco**, não
constantes:

- dias e horários de funcionamento, incluindo a pausa do almoço;
- capacidade padrão de cada serviço;
- se a reposição exige justificativa;
- se falta consome sessão do pacote;
- a janela de reposição.

Habilitar o sábado, mudar a capacidade de uma turma ou trocar a regra de
reposição é **editar uma linha** — não recompilar e reimplantar o sistema.

Isso teve efeito prático durante o desenvolvimento: a cliente se contradisse
sobre a regra de reposição, e o sistema já estava modelado para acomodar as
duas leituras sem alterar o banco.

---

## 8. O que o sistema deliberadamente não faz

| Não faz | Por quê |
|---|---|
| Permitir furar a capacidade | Documentar o overbooking não é o mesmo que impedi-lo |
| Guardar dado clínico | Dado sensível sob a LGPD; exige base legal, auditoria de leitura e retenção próprias |
| Decidir se uma falta é justificada | É julgamento humano. A recepção marca; o sistema não infere |
| Apagar sessão ao criar um feriado | Cancelar aula com gente marcada é decisão de quem vai avisar os pacientes |
| Remover reservas ao reduzir capacidade | O sistema não escolhe quem perde a vaga |

---

## Como as peças se encaixam

```
  services ─────┬──────────────► sessions ◄─── users (instrutor)
   (catálogo)   │                (ocorrência)
                │                     ▲
  patients ─────┼─► enrollments ──────┤
   (pessoa)     │    (mensalidade)    │
                │         │           │
                └─► packages          │
                     (pacote)         │
                          │           │
                          ▼           │
                       bookings ──────┘
                       (a reserva: presença, falta, reposição)
                          │
                          ▼
                       charges
                       (pagamento — eixo independente)
```

**Camadas do backend:**

- `api/` — apenas HTTP: validação de entrada, código de status, autorização.
- `services/` — a regra de negócio. É onde a capacidade é verificada, o
  ciclo de cobrança é calculado e o saldo é definido.
- `models/` — as tabelas, com as constraints que garantem o que a aplicação
  não pode garantir sozinha.

Regras que valem em um lugar só, de propósito:

| Regra | Onde vive |
|---|---|
| O que consome sessão do pacote | `package_service.sessoes_consumidas` |
| Onde um ciclo de cobrança começa e termina | `ciclo_service` |
| Como a capacidade é respeitada | `booking_service.criar` + índices no banco |
| Quais faltas dão direito a repor | `reposicao_service.listar_pendentes` |

Cada uma dessas é o tipo de regra que alguém reescreveria numa consulta nova
sem perceber que estava mudando o significado.
