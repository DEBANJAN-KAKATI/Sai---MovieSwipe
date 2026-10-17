import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API = process.env.MOVIESWIPE_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    // 5173 is often taken by other Vite projects; 0.0.0.0 lets phones on the same Wi-Fi open the live preview.
    port: 5175,
    host: true,
    // The Android/Gradle build rewrites thousands of files under android/; watching them crashed the dev server.
    watch: { ignored: ["**/android/**", "**/dist/**"] },
    proxy: {
      "/api": { target: API, changeOrigin: true, ws: true },
    },
  },
});
