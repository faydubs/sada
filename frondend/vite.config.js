import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// خادم التطوير على المنفذ 5173 (مسموح به في CORS الخاص بالـ backend).
// proxy لتحويل /api و /ws إلى FastAPI أثناء التطوير بدون مشاكل CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  },
});
