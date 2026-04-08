import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--color-bg-rgb) / <alpha-value>)",
        border: "rgb(var(--color-border-rgb) / <alpha-value>)",
        "border-strong": "rgb(var(--color-border-strong-rgb) / <alpha-value>)",
        text: "rgb(var(--color-text-rgb) / <alpha-value>)",
        muted: "rgb(var(--color-text-muted-rgb) / <alpha-value>)",
        "muted-strong": "rgb(var(--color-text-soft-rgb) / <alpha-value>)",
        accent: "rgb(var(--color-primary-rgb) / <alpha-value>)",
        "accent-2": "rgb(var(--color-secondary-rgb) / <alpha-value>)",
        success: "rgb(var(--color-success-rgb) / <alpha-value>)",
        danger: "rgb(var(--color-danger-rgb) / <alpha-value>)",
        warning: "rgb(var(--color-warning-rgb) / <alpha-value>)",
        card: "rgb(var(--color-bg-elevated-rgb) / <alpha-value>)",
        "card-hover": "rgb(var(--color-bg-soft-rgb) / <alpha-value>)",
        sidebar: "rgb(var(--color-bg-panel-rgb) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["var(--font-body)", "sans-serif"],
        display: ["var(--font-display)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      backgroundImage: {
        "gradient-accent":
          "linear-gradient(135deg, rgb(var(--color-primary-rgb)) 0%, rgb(var(--color-secondary-rgb)) 55%, rgb(var(--color-accent-rgb)) 100%)",
      },
    },
  },
  plugins: [],
};

export default config;
