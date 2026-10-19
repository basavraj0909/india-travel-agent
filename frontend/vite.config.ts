/**
 * ⚡ Vite Bundler & Dev Server Configuration (Port 3002)
 *
 * ============================================================================
 * BEGINNER DEVELOPER ARCHITECTURE GUIDE:
 * ============================================================================
 *
 * 1. Why is Vite running on Port 3002?
 *    The React frontend runs at http://localhost:3002.
 *
 * 2. Why do we need the 'proxy' setting?
 *    In web browsers, making requests across different ports (e.g. from port 3002
 *    to port 4002) triggers CORS (Cross-Origin Resource Sharing) restrictions.
 *    By setting up a proxy for `/api/copilotkit`, the browser sends requests directly
 *    to http://localhost:3002/api/copilotkit, and Vite transparently forwards them
 *    behind the scenes to http://127.0.0.1:4002 (the Hono gateway server).
 *    This avoids CORS issues completely in local development!
 */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 3002,
    host: "0.0.0.0",
    allowedHosts: true,
    strictPort: true,
    proxy: {
      "/api/copilotkit": "http://127.0.0.1:4002",
    },
  },
});

