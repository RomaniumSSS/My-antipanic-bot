import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: "var(--tg-theme-button-color)",
        "primary-text": "var(--tg-theme-button-text-color)",
        "bg-color": "var(--tg-theme-bg-color)",
        "text-color": "var(--tg-theme-text-color)",
        "hint-color": "var(--tg-theme-hint-color)",
        "link-color": "var(--tg-theme-link-color)",
        "secondary-bg": "var(--tg-theme-secondary-bg-color)",
      },
    },
  },
  plugins: [],
};

export default config;
