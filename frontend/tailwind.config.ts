import type { Config } from 'tailwindcss'

/**
 * Paleta extraída dos prints em `referencia-figma/prints/` por amostragem de
 * moda de região (não a olho, e não por pixel único — pixel único cai em
 * antialiasing de texto e devolve cor errada).
 *
 * Duas descobertas que contrariam o que o protótipo aparenta:
 *   - a sidebar é #7C2D8E CHAPADO, não gradiente (amostrado de y=80 a y=880);
 *   - o item de menu ativo é MAIS ESCURO (#6B1E7A), não mais claro.
 *
 * Só `brand` é cor custom. O resto coincide com a paleta padrão do Tailwind
 * (cyan-500, purple-500, gray-200/500), o que era esperado num export de
 * ferramenta de prototipagem.
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#7C2D8E', // sidebar, botão primário, filtro ativo, preços
          dark: '#6B1E7A', // item de menu ativo
        },
        // Cores de modalidade — usadas na legenda e nos cards da agenda.
        pilates: '#06B6D4',
        fisioterapia: '#7C2D8E',
        avaliacao: '#BB4D00',
        falta: '#E7000B',

        accent: '#06B6D4', // ícones de KPI, chip de hora, ação "Marcar Pago"
        violet: '#A855F7',
        danger: '#E7000B',

        ink: '#1A1A2E', // títulos, números de KPI, nomes
        muted: '#6B7280', // subtítulos e labels

        canvas: '#F8F9FB', // fundo da página
        surface: '#FFFFFF', // cards
        subtle: '#F7F7F9', // linhas de lista, header de tabela
        edge: '#E5E7EB', // bordas e botão secundário

        // Gráficos da análise do Dashboard. Paleta validada com o validador de
        // dataviz: presente/justificada/falta separam com CVD ΔE 18,1 e visão
        // normal ΔE 24,4. `justificada` e `apoio` ficam abaixo de 3:1 contra o
        // branco, por isso SEMPRE aparecem com rótulo de texto ao lado — a cor
        // nunca é o único jeito de ler o valor. A falta reutiliza o token
        // `falta` e a ênfase reutiliza `brand`.
        grafico: {
          apoio: '#B39BBB', // barras que não são o destaque
          trilho: '#F3EEF5', // fundo das barras
          presente: '#0891B2',
          justificada: '#F59E0B',
          'sem-registro': '#9CA3AF',
        },
      },
      keyframes: {
        // Barras crescem a partir da base. Usar com `motion-safe:` e
        // `origin-left` / `origin-bottom`; o atraso escalonado vai por style.
        'crescer-x': {
          from: { transform: 'scaleX(0)' },
          to: { transform: 'scaleX(1)' },
        },
        'crescer-y': {
          from: { transform: 'scaleY(0)' },
          to: { transform: 'scaleY(1)' },
        },
      },
      animation: {
        'crescer-x': 'crescer-x 600ms cubic-bezier(0.22, 1, 0.36, 1) both',
        'crescer-y': 'crescer-y 600ms cubic-bezier(0.22, 1, 0.36, 1) both',
      },
      backgroundColor: {
        'badge-confirmado': '#C7EAF1',
        'badge-aguardando': '#E5D5E8',
        'badge-pago': '#CDF0F6',
        'badge-alerta': '#FFE2E2',
        'stat-ciano': '#E6F7FA',
        'stat-rosa': '#F1EAF3',
        'stat-violeta': '#F6EEFE',
      },
      fontFamily: {
        // A fonte dos prints não foi identificada com segurança. Poppins é a
        // aproximação mais próxima do desenho das headings.
        heading: ['Poppins', 'system-ui', 'sans-serif'],
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      borderRadius: {
        card: '12px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(26, 26, 46, 0.06), 0 1px 2px rgba(26, 26, 46, 0.04)',
      },
    },
  },
  plugins: [],
} satisfies Config
