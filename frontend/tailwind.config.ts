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
