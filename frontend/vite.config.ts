import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
    const env = loadEnv(
        mode,
        process.cwd(),
        "",
    );

    /*
     * ==========================================================
     * BACKEND CONFIGURATION
     * ==========================================================
     *
     * Development:
     *   VITE_BACKEND_URL=http://127.0.0.1:8889
     *
     * Production:
     *   VITE_API_URL=https://your-backend-domain.com/api/v1
     *
     * NOTE:
     * Vercel TIDAK bisa mengakses:
     *
     *   http://127.0.0.1:8889
     *
     * karena itu adalah komputer lokal developer.
     */

    const backendUrl = (
        env.VITE_BACKEND_URL ||
        "http://127.0.0.1:8889"
    ).replace(/\/+$/, "");

    /*
     * ==========================================================
     * VITE CONFIG
     * ==========================================================
     */

    return {
        plugins: [
            react(),
        ],

        /*
         * ======================================================
         * DEVELOPMENT SERVER
         * ======================================================
         */

        server: {
            host: "127.0.0.1",

            port: 5173,

            strictPort: false,

            /*
             * Local development:
             *
             * Frontend:
             *   http://127.0.0.1:5173
             *
             * Backend:
             *   http://127.0.0.1:8889
             *
             * Request:
             *   /api/v1/...
             *
             * forwarded to:
             *   http://127.0.0.1:8889/api/v1/...
             */

            proxy: {
                "/api": {
                    target: backendUrl,

                    changeOrigin: true,

                    secure: false,

                    /*
                     * Do NOT rewrite /api.
                     *
                     * /api/v1/executive/charts
                     *
                     * remains:
                     *
                     * /api/v1/executive/charts
                     */
                },
            },
        },

        /*
         * ======================================================
         * PREVIEW SERVER
         * ======================================================
         */

        preview: {
            host: "127.0.0.1",

            port: 4173,

            strictPort: false,
        },

        /*
         * ======================================================
         * BUILD
         * ======================================================
         */

        build: {
            outDir: "dist",

            emptyOutDir: true,

            /*
             * Current application bundle is relatively large
             * because ECharts / Leaflet / MUI are included.
             *
             * This is a warning threshold only.
             * It does NOT affect correctness.
             */

            chunkSizeWarningLimit: 1500,

            sourcemap: false,
        },
    };
});