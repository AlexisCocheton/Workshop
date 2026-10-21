/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Charte « confiserie » : rose bonbon sur fond crème, texte prune.
        candy: { ink: "#4A1942", pink: "#E84A8A", light: "#FDE7F0", cream: "#FFF8F1" },
      },
      fontFamily: {
        sans: ["Montserrat", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};
