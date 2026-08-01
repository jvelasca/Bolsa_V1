import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: Number(process.env.WEB_PORT ?? 5173),
    strictPort: true,
    host: true,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.API_PYTHON_PORT ?? 8000}`,
        changeOrigin: true,
      },
    },
  },
});
