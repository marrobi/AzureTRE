import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// The FastAPI app serves the built files from nfportal/static.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../nfportal/static", emptyOutDir: true, sourcemap: false },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000", "/files": "http://127.0.0.1:8000" },
  },
});
