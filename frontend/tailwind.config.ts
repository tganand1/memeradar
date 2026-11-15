import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "hsl(var(--bg) / <alpha-value>)",
        panel: "hsl(var(--panel) / <alpha-value>)",
        border: "hsl(var(--border) / <alpha-value>)",
        fg: "hsl(var(--fg) / <alpha-value>)",
        muted: "hsl(var(--muted) / <alpha-value>)",
        accent: "hsl(var(--accent) / <alpha-value>)",
        cyan: "hsl(var(--cyan) / <alpha-value>)",
        warn: "hsl(var(--warn) / <alpha-value>)",
        danger: "hsl(var(--danger) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Space Grotesk", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px hsl(var(--accent) / 0.18), 0 0 28px -6px hsl(var(--accent) / 0.35)",
        panel: "0 20px 60px -30px rgba(0,0,0,0.9)",
      },
      keyframes: {
        "radar-sweep": {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.55)", opacity: "0.7" },
          "100%": { transform: "scale(1.7)", opacity: "0" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-6px)" },
        },
        "flash-up": {
          "0%": { backgroundColor: "hsl(var(--accent) / 0.22)" },
          "100%": { backgroundColor: "transparent" },
        },
        "flash-down": {
          "0%": { backgroundColor: "hsl(var(--danger) / 0.22)" },
          "100%": { backgroundColor: "transparent" },
        },
      },
      animation: {
        "radar-sweep": "radar-sweep 4s linear infinite",
        "pulse-ring": "pulse-ring 2.4s cubic-bezier(0.2, 0.6, 0.4, 1) infinite",
        shimmer: "shimmer 2.2s linear infinite",
        float: "float 5s ease-in-out infinite",
        "flash-up": "flash-up 1.2s ease-out",
        "flash-down": "flash-down 1.2s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
