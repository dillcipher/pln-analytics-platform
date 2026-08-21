import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

function normalizeApiUrl(value: string): string {
    const url = value.trim().replace(/\/+$/, "");
    if (!url) return "";
    return url.endsWith("/api/v1") ? url : `${url}/api/v1`;
}

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), "");
    const backendUrl = (
        env.VITE_BACKEND_URL || "http://127.0.0.1:8889"
    ).replace(/\/+$/, "");

    const productionApiUrl = normalizeApiUrl(env.VITE_API_URL || "");
    if (mode === "production" && !productionApiUrl) {
        throw new Error(
            "VITE_API_URL is required for production builds. " +
            "Set it to the deployed FastAPI base URL, for example " +
            "https://your-backend.example.com/api/v1."
        );
    }

    return {
        plugins: [react()],
        server: {
            host: "127.0.0.1",
            port: 5173,
            strictPort: false,
            proxy: {
                "/api": {
                    target: backendUrl,
                    changeOrigin: true,
                    secure: false,
                },
            },
        },
        preview: {
            host: "127.0.0.1",
            port: 4173,
            strictPort: false,
        },
        build: {
            outDir: "dist",
            emptyOutDir: true,
            chunkSizeWarningLimit: 1500,
            sourcemap: false,
        },
    };
});
