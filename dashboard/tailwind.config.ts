import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        canvas: '#070a13',
      },
      boxShadow: {
        'neon-cyan':    '0 0 30px rgba(6,182,212,0.20), 0 0 60px rgba(6,182,212,0.08)',
        'neon-emerald': '0 0 30px rgba(16,185,129,0.20), 0 0 60px rgba(16,185,129,0.08)',
        'glass':        '0 4px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.06)',
        'glass-lg':     '0 8px 48px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.08)',
      },
      keyframes: {
        blink: {
          '0%,100%': { opacity: '1' },
          '50%':     { opacity: '0.25' },
        },
        'bar-grow': {
          '0%':   { transform: 'scaleY(0)', opacity: '0' },
          '100%': { transform: 'scaleY(1)', opacity: '1' },
        },
        'slide-up': {
          '0%':   { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)',    opacity: '1' },
        },
        'fade-in': {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition:  '200% 0' },
        },
      },
      animation: {
        blink:      'blink 1.8s ease-in-out infinite',
        'bar-grow': 'bar-grow 0.6s ease-out forwards',
        'slide-up': 'slide-up 0.5s ease-out',
        'fade-in':  'fade-in 0.8s ease-out',
        shimmer:    'shimmer 2.5s linear infinite',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
export default config
