/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: [
    "./SpotImageViewer.Native/UI/**/*.html",
    "./SpotImageViewer.Native/UI/**/*.js"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--app-font)', 'Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['0.70rem', { lineHeight: '0.85rem' }],
        'xs': ['0.78rem', { lineHeight: '1.05rem' }],
        'sm': ['0.85rem', { lineHeight: '1.20rem' }],
        'base': ['0.95rem', { lineHeight: '1.35rem' }],
        'lg': ['1.05rem', { lineHeight: '1.45rem' }],
        'xl': ['1.20rem', { lineHeight: '1.60rem' }],
        '2xl': ['1.40rem', { lineHeight: '1.75rem' }],
      }
    }
  },
  plugins: []
};
