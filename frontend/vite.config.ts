import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  base: "/assistant/",
  plugins: [react()],
  build: { assetsInlineLimit: 0 },
});
