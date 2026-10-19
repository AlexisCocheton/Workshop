import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Le dashboard est servi sur le port 3000 et joignable depuis le réseau du groupe.
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 3000 },
});
