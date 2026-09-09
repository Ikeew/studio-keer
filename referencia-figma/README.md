# referencia-figma — SOMENTE LEITURA

Prints das telas geradas no Figma Make, usados como **referência visual**.

**Nada aqui deve ser editado, movido ou renomeado.** Não há código-fonte do
Figma Make: o export nunca foi obtido, então todo o frontend é escrito do zero
a partir destas imagens.

## Prints

| Arquivo | Tela |
|---|---|
| `prints/01-dashboard.png` | Dashboard: 4 KPIs + próximos agendamentos |
| `prints/02-agendamentos-semana.png` | Agenda semanal (grade horário × dia, vagas, legenda de cores) |
| `prints/03-pacientes.png` | Lista de pacientes em cards, com busca |
| `prints/04-atividades-modal-nova.png` | Modal "Adicionar Nova Atividade" |
| `prints/05-atividades.png` | Atividades & Serviços + estatísticas |
| `prints/06-financeiro.png` | Financeiro: totais, filtros por status, tabela de cobranças |
| `prints/99-dashboard-com-overlay-figma.png` | Mesmo dashboard, coberto pelo modal de login do Figma. Ruído, ignorar. |

## O que NÃO seguir dos prints

Os prints são um protótipo com dados mockados e divergem dos requisitos
acordados. Onde houver conflito, **o requisito vence**:

- Marca "Studio Pilates & Fisio" → o produto é **Studio Keer**.
- Menu "Clientes" → a nomenclatura da interface é **Paciente**.
- A agenda não mostra o instrutor → `professional_id` é obrigatório e o nome
  do instrutor **deve** aparecer na grade.
- A grade mostra só Segunda–Sexta → os dias vêm da configuração de
  funcionamento, não do layout.
- "Avaliação" não aparece como card em Atividades → é um serviço comum; a tela
  do print estava filtrada.
- Barra superior do Figma, botões "Sign up with email"/"Continue with Google" e
  o aviso de cookies são cromo da ferramenta, não fazem parte do produto.

## Paleta extraída (amostragem por moda de região, não a olho)

Ver `frontend/tailwind.config.ts`. Resumo: a marca é `#7C2D8E` chapado (a
sidebar **não** tem gradiente, e o item ativo é mais escuro: `#6B1E7A`); os
demais tons são a paleta padrão do Tailwind.
