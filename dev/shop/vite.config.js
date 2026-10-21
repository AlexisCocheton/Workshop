import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// La boutique est servie sur le port 3002 (3000 : back-office, 3001 : Grafana)
// et joignable depuis le réseau du groupe : c'est le site public des clients.
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 3002 },
});
