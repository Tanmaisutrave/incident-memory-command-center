/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0B0F14',
        surface: '#111827',
        'surface-secondary': '#172033',
        border: '#263244',
        primary: {
          DEFAULT: '#06B6D4',
          hover: '#0891B2',
        },
        severity: {
          p1: '#EF4444',
          p2: '#F59E0B',
          p3: '#EAB308',
          p4: '#6B7280',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      }
    },
  },
  plugins: [],
}
