import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Forward API calls to the FastAPI dev server so the browser sees one origin.
const api = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/deadlines": api,
      "/courses": api,
      "/export": api,
      "/syllabi": api,
    },
  },
});
