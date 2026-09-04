import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b0f17",
        panel: "#111827",
        panel2: "#0e1420",
        line: "#1f2937",
        accent: "#6366f1",
        mint: "#34d399",
      },
    },
  },
  plugins: [],
};
export default config;
