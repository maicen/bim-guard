import animate from 'tailwindcss-animate';

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{svelte,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Single chromatic accent, reserved for interactive elements (DESIGN.md).
        // Defined per theme in app.css so it can diverge without touching markup.
        accent: {
          DEFAULT: 'rgb(var(--color-accent) / <alpha-value>)',
          hover: 'rgb(var(--color-accent-hover) / <alpha-value>)',
        },
        // Surface/text ramp. The variables invert between themes, which is why
        // components carry no `dark:` variants: `bg-slate-900` is a near-black
        // card in dark mode and a white one in light mode.
        slate: {
          50: 'rgb(var(--color-slate-50) / <alpha-value>)',
          100: 'rgb(var(--color-slate-100) / <alpha-value>)',
          200: 'rgb(var(--color-slate-200) / <alpha-value>)',
          300: 'rgb(var(--color-slate-300) / <alpha-value>)',
          400: 'rgb(var(--color-slate-400) / <alpha-value>)',
          500: 'rgb(var(--color-slate-500) / <alpha-value>)',
          600: 'rgb(var(--color-slate-600) / <alpha-value>)',
          700: 'rgb(var(--color-slate-700) / <alpha-value>)',
          800: 'rgb(var(--color-slate-800) / <alpha-value>)',
          900: 'rgb(var(--color-slate-900) / <alpha-value>)',
          950: 'rgb(var(--color-slate-950) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      // Dense-tool type ramp below Tailwind's 12px `text-xs`, with the negative
      // tracking DESIGN.md calls for at every size.
      fontSize: {
        nano: ['0.5625rem', { lineHeight: '0.875rem', letterSpacing: '0.01em' }],
        micro: ['0.625rem', { lineHeight: '0.9375rem', letterSpacing: '0.005em' }],
        caption: ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0' }],
      },
      // Radius scale capped at 12px for rectangles (DESIGN.md §7); `full` stays
      // available for pills and avatars.
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'scale-up': {
          from: { opacity: '0', transform: 'scale(0.96)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 200ms ease-out',
        'scale-up': 'scale-up 200ms ease-out',
      },
      borderRadius: {
        sm: '5px',
        DEFAULT: '8px',
        md: '8px',
        lg: '11px',
        xl: '12px',
        '2xl': '12px',
      },
    },
  },
  plugins: [animate],
};
