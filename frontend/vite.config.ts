import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The host loads dist/index.html from a local server, so asset paths stay relative.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  server: { port: 5199, strictPort: true },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 800 },
});
