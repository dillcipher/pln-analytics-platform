import axios from "axios";

function normalizeBaseUrl(url: string): string {
    return url.trim().replace(/\/+$/, "");
}

const explicitApiUrl = normalizeBaseUrl(
    typeof import.meta.env.VITE_API_URL === "string"
        ? import.meta.env.VITE_API_URL
        : "",
);

const backendUrl = normalizeBaseUrl(
    typeof import.meta.env.VITE_BACKEND_URL === "string"
        ? import.meta.env.VITE_BACKEND_URL
        : "http://127.0.0.1:8000",
);

/**
 * Production MUST provide VITE_API_URL, e.g.
 * https://<fastapi-cloud-backend>/api/v1
 *
 * Local development uses the Vite /api proxy.
 */
const API_BASE_URL = explicitApiUrl || (
    import.meta.env.DEV
        ? `${backendUrl}/api/v1`
        : "/api/v1"
);

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
