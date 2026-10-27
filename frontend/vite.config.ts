import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API runs on :8100 and is proxied, so the session cookie is same-origin.
// Ports are chosen to avoid clashing with other local projects (8000/5173).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: {
      "/api": "http://localhost:8100",
      "/health": "http://localhost:8100",
    },
  },
});
