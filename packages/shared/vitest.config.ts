import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  resolve: {
    alias: {
      // Permite que los tests importen desde el código fuente (src) en vez del
      // paquete ya compilado (dist), evitando depender de un build previo.
      "@bolsa/shared": path.resolve(__dirname, "./src/index.ts"),
      "@src": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
