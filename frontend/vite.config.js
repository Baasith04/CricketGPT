import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = (env.VITE_API_BASE_URL || "https://cricketgpt-k4jb.onrender.com")
    .trim()
    .replace(/\/+$/, "");

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        // Proxy /api and /health through Vite in local dev using VITE_API_BASE_URL
        // so browser requests stay same-origin (avoiding CORS blocks on localhost).
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          secure: true,
        },
        "/health": {
          target: apiTarget,
          changeOrigin: true,
          secure: true,
        },
      },
    },
  };
});
