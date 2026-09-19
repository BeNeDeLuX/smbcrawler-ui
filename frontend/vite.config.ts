import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built bundle is copied into the FastAPI image and served at "/".
// In dev, `npm run dev` proxies /api to the backend on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
