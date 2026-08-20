import axios from "axios";

/**
 * ==========================================================
 * API CONFIGURATION
 * ==========================================================
 *
 * Development:
 *   Frontend  -> http://127.0.0.1:8889/api/v1
 *
 * Production:
 *   Uses VITE_API_URL when provided.
 *   Otherwise falls back to /api/v1.
 *
 * This avoids relying on the Vite proxy during local
 * development when the FastAPI backend is already running
 * directly on port 8889.
 * ==========================================================
 */

const envApiUrl =
    typeof import.meta.env.VITE_API_URL === "string"
        ? import.meta.env.VITE_API_URL.trim()
        : "";

const envBackendUrl =
    typeof import.meta.env.VITE_BACKEND_URL === "string"
        ? import.meta.env.VITE_BACKEND_URL.trim()
        : "";

const normalizeBaseUrl = (url: string): string => {
    if (!url) {
        return "";
    }

    return url.replace(/\/+$/, "");
};

const explicitApiUrl = normalizeBaseUrl(envApiUrl);

const backendUrl = normalizeBaseUrl(
    envBackendUrl || "http://127.0.0.1:8889",
);

const API_BASE_URL =
    explicitApiUrl ||
    (import.meta.env.DEV
        ? `${backendUrl}/api/v1`
        : "/api/v1");

/**
 * ==========================================================
 * AXIOS INSTANCE
 * ==========================================================
 */

const api = axios.create({
    baseURL: API_BASE_URL,

    timeout: Number(
        import.meta.env.VITE_API_TIMEOUT || 120000,
    ),

    headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
    },
});

/**
 * ==========================================================
 * REQUEST INTERCEPTOR
 * ==========================================================
 */

api.interceptors.request.use(
    (config) => {
        const token =
            localStorage.getItem("access_token");

        if (token) {
            config.headers = config.headers ?? {};

            config.headers.Authorization =
                `Bearer ${token}`;
        }

        return config;
    },

    (error) => {
        return Promise.reject(error);
    },
);

/**
 * ==========================================================
 * RESPONSE INTERCEPTOR
 * ==========================================================
 */

api.interceptors.response.use(
    (response) => {
        return response;
    },

    (error) => {
        const status =
            error?.response?.status;

        const responseData =
            error?.response?.data;

        const detail =
            responseData?.detail ??
            responseData?.message ??
            error?.message ??
            "Request failed";

        /**
         * Make the actual API URL visible in the browser
         * console. This is useful when debugging a failed
         * Executive Dashboard request.
         */
        console.error(
            "[API ERROR]",
            {
                method:
                    error?.config?.method?.toUpperCase(),

                url:
                    error?.config?.url,

                baseURL:
                    error?.config?.baseURL,

                status,

                detail,
            },
        );

        if (status === 401) {
            console.warn(
                "API unauthorized:",
                detail,
            );
        }

        if (
            status !== undefined &&
            status >= 400 &&
            status < 500 &&
            status !== 401
        ) {
            console.warn(
                "API client error:",
                detail,
            );
        }

        if (
            status !== undefined &&
            status >= 500
        ) {
            console.error(
                "API server error:",
                detail,
            );
        }

        if (!error?.response) {
            console.error(
                "[API NETWORK ERROR]",
                {
                    message:
                        error?.message,
                    baseURL:
                        error?.config?.baseURL,
                    url:
                        error?.config?.url,
                },
            );
        }

        return Promise.reject(error);
    },
);

export default api;