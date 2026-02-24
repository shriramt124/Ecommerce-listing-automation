/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        prime: {
          // Backgrounds (Vercel/Linear inspired deep darks)
          bg: '#000000', // Pure black base
          surface: '#0C0C0C', // Highly elevated
          panel: '#161616', // Cards & modals
          input: '#1A1A1A', // Inputs
          hover: '#262626', // Subtle hover state

          // Borders (Subtle outlines)
          border: '#2E2E2E',
          divider: '#1F1F1F',

          // Typography (High contrast legibility)
          text: '#EDEDED', // Primary readable white
          muted: '#A1A1AA', // Secondary text (zinc-400)
          label: '#71717A', // Tertiary/labels (zinc-500)

          // Accents & Semantic
          accent: '#EDEDED', // Neutral high contrast accent
          primary: '#3B82F6', // Crisp blue
          primaryBg: '#3B82F615',
          success: '#10B981', // Clean emerald
          successBg: '#10B98115',
          warning: '#F59E0B', // Amber
          warningBg: '#F59E0B15',
          danger: '#EF4444', // Red
          dangerBg: '#EF444415',
          info: '#6366F1', // Indigo
          infoBg: '#6366F115',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
      },
      boxShadow: {
        'glow-primary': '0 0 15px -3px rgba(59, 130, 246, 0.4)',
        'glow-success': '0 0 15px -3px rgba(16, 185, 129, 0.4)',
        'glow-subtle': '0 0 20px -5px rgba(255, 255, 255, 0.05)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
