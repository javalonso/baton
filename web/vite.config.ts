import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `design/tokens.css` is imported from outside this package on purpose. The palette was
// verified for contrast once and belongs in one file; a copy inside `web/` would drift the
// first time somebody adjusts a colour and forgets the other one.
export default defineConfig({
  plugins: [react()],
  server: {
    fs: { allow: [".."] },
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
