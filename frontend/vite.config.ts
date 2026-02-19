import path from "node:path"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src")
    }
  },
  server: {
    proxy: {
      "/analyze": "http://localhost:8080",
      "/process": "http://localhost:8080",
      "/progress": "http://localhost:8080",
      "/events": "http://localhost:8080",
      "/results": "http://localhost:8080",
      "/download": "http://localhost:8080",
      "/health": "http://localhost:8080"
    }
  },
  build: {
    outDir: "dist",
    emptyOutDir: true
  }
})
