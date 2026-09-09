# Decisões técnicas

Decisões que não são óbvias pelo código e que alguém vai questionar — na
revisão, na banca ou daqui a seis meses. Cada uma traz a alternativa
descartada e o que aceitamos de risco.

Decisões de **domínio** ficam no [CLAUDE.md](../CLAUDE.md). Aqui é
infraestrutura e segurança.

---

## Token de acesso dura 12 horas, e não há refresh token

**Contexto.** A recepcionista abre o sistema no início do expediente e usa o
dia inteiro, entre atendimentos. O studio funciona das 06:00 às 21:00.

**Decisão.** Access token JWT com validade de **12 horas**, sem refresh token.

**Por quê.**

Ser deslogada no meio do expediente inviabiliza o uso: acontece justamente
quando há alguém no balcão esperando. Uma expiração curta (15–30 min, comum em
aplicação financeira) só funciona acompanhada de refresh token, que renova a
sessão em silêncio.

Refresh token custa caro: um segundo token com validade longa, armazenamento
separado, endpoint de renovação, rotação, lista de revogação e tratamento de
corrida quando várias requisições recebem 401 ao mesmo tempo. É bastante
superfície nova — e cada peça dessas é um lugar a mais para errar em
segurança.

O que refresh token compra é **janela curta de token roubado**. Aqui esse
ganho é pequeno: o sistema é interno, sem cadastro público, rodando no
computador da recepção, e não movimenta dinheiro — apenas registra pagamentos
recebidos fora dele.

12 horas cobrem o turno mais longo com folga e ainda garantem que o token
**morra durante a noite**: um navegador esquecido aberto não continua válido
no dia seguinte.

**Risco aceito.** Um token vazado vale até 12 horas. Mitigações no lugar:

- O papel e o campo `ativo` são **relidos do banco** a cada requisição, não
  tirados do payload. Desativar alguém corta o acesso **na hora**, sem esperar
  o token expirar. Coberto por teste.
- HTTPS obrigatório em produção (Render e Vercel entregam por padrão).

**Se mudar de ideia.** `ACCESS_TOKEN_EXPIRE_MINUTES` é configuração de
ambiente: encurtar não exige deploy. Refresh token, se um dia for necessário,
entra sem quebrar o que existe — o access token continua igual.

---

## O token fica em localStorage, não em cookie httpOnly

**Decisão.** `localStorage`, lido pelo interceptor do axios.

**Alternativa descartada.** Cookie `httpOnly` + `Secure` + `SameSite`, que é
mais seguro: JavaScript não alcança o cookie, então XSS não rouba o token.

**Por quê não agora.** O frontend fica na Vercel e a API no Render — domínios
diferentes. Cookie entre domínios exige `SameSite=None`, CORS com
credenciais, e **proteção CSRF própria**, que o header `Authorization` não
precisa. Seria trocar um risco por outro, com mais peças, numa equipe que está
aprendendo a stack.

**Risco aceito.** Se houver XSS na aplicação, o token é roubável. O que reduz
a exposição: o sistema é interno, sem conteúdo enviado por terceiros, e o
React escapa interpolação por padrão. **Nunca use `dangerouslySetInnerHTML`
neste projeto** — é o caminho mais curto para tornar este risco real.

**Se mudar de ideia.** O acesso ao token está isolado em
`frontend/src/auth/storage.ts`. Migrar para cookie mexe nesse arquivo, no
interceptor e no CORS do backend — não espalha pelo resto do código.

---

## O papel vai no token, mas a autorização consulta o banco

**Decisão.** O JWT carrega `papel` no payload, mas `get_current_user` relê o
usuário do banco e é o papel **do banco** que decide o acesso.

**Por quê.** O papel no payload seria uma otimização — evitaria uma consulta
por requisição. Mas tornaria o token uma verdade congelada por 12 horas:
rebaixar alguém de admin para recepção não teria efeito até o token expirar.

Além disso, confiar no payload significa que qualquer falha na emissão do
token vira escalonamento de privilégio. Há teste cobrindo exatamente isso:
um token assinado com `papel: admin` para um usuário que é recepção **recebe
403**.

**Custo.** Uma consulta por id (chave primária) por requisição autenticada.
Irrelevante na escala deste sistema — um studio, alguns usuários simultâneos.

---

## Seed de usuários é comando CLI, nunca migration

**Decisão.** `python -m app.cli seed-usuarios`, com senhas vindas de variável
de ambiente.

**Por quê não migration.** Migration versiona **schema**, não dado
operacional. Uma migration que cria usuário roda igual em todo ambiente,
inclusive produção — plantando conta conhecida no ambiente real, com senha que
está no repositório e no histórico do Git para sempre.

**Garantias do comando.**

- **Nenhuma senha no repositório.** Sem variável definida, o comando recusa e
  explica o que fazer. `--gerar-senhas` sorteia com `secrets` e imprime uma
  única vez.
- **Idempotente.** Rodar de novo não duplica.
- **Não sobrescreve senha existente.** Rodar por engano num ambiente em uso
  não derruba o acesso de ninguém.
- Valida tamanho mínimo e o limite de 72 bytes do bcrypt.

---

## bcrypt fixado em 4.0.1

O passlib 1.7.4 lê `bcrypt.__about__`, atributo removido no bcrypt 4.1. Sem o
pin o login funciona, mas cospe um `AttributeError` em warning a cada hash —
ruído que esconde erro de verdade no log.

**Alternativa** quando o passlib for atualizado (ou substituído): usar a lib
`bcrypt` direto, sem passlib. Não vale mexer agora.

**Cuidado relacionado:** o bcrypt trunca a senha em 72 bytes. `UserCreate`
valida esse limite para o usuário receber erro claro, em vez de uma truncagem
silenciosa — que faria duas senhas longas com o mesmo prefixo abrirem a mesma
conta.

---

## 401 e 403 significam coisas diferentes

- **401** — não autenticado (sem token, expirado, inválido). O frontend
  **desloga** e manda para o login.
- **403** — autenticado, mas sem permissão. O frontend **não desloga**.

Tratar os dois igual expulsaria o instrutor do sistema ao esbarrar numa tela
de admin. A distinção está no interceptor do axios e é coberta por teste no
backend.

---

## Esconder menu não é controle de acesso

`ACESSO_POR_ROTA` no frontend decide o que **aparece**. A autorização de
verdade é do backend, que recusa com 403 mesmo se a pessoa digitar a URL
direto ou chamar a API por fora.

Toda rota nova precisa de proteção **nos dois lados**. A do backend é a que
importa; a do frontend evita que alguém veja um botão que não pode usar.
