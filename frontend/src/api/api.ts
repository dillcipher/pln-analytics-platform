import axios from "axios";

const DEFAULT_BACKEND_ORIGIN = "https://pln-analytics-platform.fastapicloud.dev";

function normalizeBaseUrl(url: string): string {
    return url.trim().replace(/\/+$/, "");
}

function normalizeProductionApiUrl(url: string): string {
    const normalized = normalizeBaseUrl(url);
    if (!normalized) return "";
    return normalized.endsWith("/api/v1")
        ? normalized
        : `${normalized}/api/v1`;
}

const explicitApiUrl = normalizeProductionApiUrl(
    typeof import.meta.env.VITE_API_URL === "string"
        ? import.meta.env.VITE_API_URL
        : "",
);

const configuredBackendUrl = normalizeBaseUrl(
    typeof import.meta.env.VITE_BACKEND_URL === "string"
        ? import.meta.env.VITE_BACKEND_URL
        : "",
);

const sameOrigin =
    typeof window !== "undefined"
        ? normalizeBaseUrl(window.location.origin)
        : "";

/**
 * Production deployment is intentionally self-contained:
 *
 * 1. VITE_API_URL may explicitly point to the deployed FastAPI service.
 * 2. Otherwise Vercel's /api/v1 rewrite proxies to the production backend.
 * 3. Local development keeps using VITE_BACKEND_URL or localhost.
 *
 * This prevents a successful Vercel build from producing a frontend that
 * silently points at 127.0.0.1 or requires a missing production env var.
 */
const backendOrigin =
    explicitApiUrl
        ? explicitApiUrl.replace(/\/api\/v1$/, "")
        : configuredBackendUrl ||
          (!import.meta.env.DEV
              ? DEFAULT_BACKEND_ORIGIN
              : "http://127.0.0.1:8000");

export const API_ORIGIN = normalizeBaseUrl(
    explicitApiUrl
        ? explicitApiUrl.replace(/\/api\/v1$/, "")
        : configuredBackendUrl ||
          (!import.meta.env.DEV
              ? DEFAULT_BACKEND_ORIGIN
              : "http://127.0.0.1:8000"),
);

const API_BASE_URL =
    explicitApiUrl ||
    (sameOrigin && !import.meta.env.DEV
        ? `${sameOrigin}/api/v1`
        : `${backendOrigin}/api/v1`);

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: Number(import.meta.env.VITE_API_TIMEOUT || 120000),
    headers: { Accept: "application/json" },
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
        config.headers = config.headers ?? {};
        config.headers.Authorization = `Bearer ${token}`;
    }

    if (config.data instanceof FormData && config.headers) {
        delete (config.headers as any)["Content-Type"];
        delete (config.headers as any)["content-type"];
    }

    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error?.response?.status === 401) {
            const requestUrl = String(error?.config?.url ?? "");
            if (!requestUrl.includes("/auth/login")) {
                localStorage.removeItem("access_token");
                window.dispatchEvent(new Event("pln-auth-expired"));
            }
        }
        return Promise.reject(error);
    },
);

export default api;
