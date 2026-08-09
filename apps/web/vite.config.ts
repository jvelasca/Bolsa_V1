import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: Number(process.env.WEB_PORT ?? 5173),
    strictPort: true,
    host: true,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${process.env.API_PYTHON_PORT ?? 8000}`,
        changeOrigin: true,
        // P3 (F3.7 hardening): en syncs pesados la API puede cerrar la conexión
        // (ECONNRESET). http-proxy emite 'error' en el stream; capturarlo aquí
        // evita que se propague como fallo fatal que derriba el proceso Vite.
        configure: (proxy) => {
          proxy.on("error", (err) => {
            // El proxy error se loguea a consola pero NO debe tumbar Vite.
            console.warn(
              `[dev-proxy] error reenviando a la API (se reintentará): ${err.code ?? err.message}`,
            );
          });
        },
      },
    },
  },
});
