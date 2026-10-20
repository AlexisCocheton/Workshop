/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Charte du workshop EPSI (support de présentation officiel).
        epsi: { ink: "#261E48", bg: "#E4E6F3", accent: "#A1A6D4" },
        // Couleurs de statut : réservées aux états, toujours accompagnées d'une icône et d'un libellé.
        status: { good: "#0ca30c", warning: "#fab219", critical: "#d03b3b" },
      },
      fontFamily: {
        sans: ["Montserrat", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};
