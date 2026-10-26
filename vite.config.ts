import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/Kedao-Exploration/",
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
