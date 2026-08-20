import axios from "axios";

/**
 * ==========================================================
 * API CONFIGURATION
 * ==========================================================
 *
 * Development:
 *   Frontend -> http://127.0.0.1:8889/api/v1
 *
 * Production:
 *   Uses VITE_API_URL when provided.
 *   Otherwise falls back to /api/v1.
 *
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

function normalizeBaseUrl(
    url: string,
): string {

    if (!url) {
        return "";
    }

    return url.replace(
        /\/+$/,
        "",
    );
}

const explicitApiUrl =
    normalizeBaseUrl(
        envApiUrl,
    );

const backendUrl =
    normalizeBaseUrl(
        envBackendUrl ||
            "http://127.0.0.1:8889",
    );

const API_BASE_URL =
    explicitApiUrl ||
    (
        import.meta.env.DEV
            ? `${backendUrl}/api/v1`
            : "/api/v1"
    );

/**
 * ==========================================================
 * AXIOS INSTANCE
 * ==========================================================
 *
 * IMPORTANT:
 *
 * JANGAN menetapkan Content-Type secara global.
 *
 * Axios harus menentukan Content-Type berdasarkan body.
 *
 * Untuk JSON:
 *   Axios akan menggunakan application/json.
 *
 * Untuk FormData:
 *   Browser/Axios akan menggunakan:
 *
 *   multipart/form-data; boundary=...
 *
 * Ini WAJIB untuk endpoint upload.
 *
 * ==========================================================
 */

const api = axios.create({
    baseURL: API_BASE_URL,

    timeout: Number(
        import.meta.env.VITE_API_TIMEOUT ||
            120000,
    ),

    headers: {
        Accept:
            "application/json",
    },
});

/**
 * ==========================================================
 * REQUEST INTERCEPTOR
 * ==========================================================
 */

api.interceptors.request.use(
    (config) => {

        /**
         * ==================================================
         * AUTH TOKEN
         * ==================================================
         */

        const token =
            localStorage.getItem(
                "access_token",
            );

        if (token) {

            config.headers =
                config.headers ?? {};

            config.headers.Authorization =
                `Bearer ${token}`;
        }

        /**
         * ==================================================
         * FORM DATA FIX
         * ==================================================
         *
         * Ini bagian PALING PENTING.
         *
         * Kalau request menggunakan FormData,
         * hapus Content-Type yang mungkin diwariskan
         * dari konfigurasi Axios.
         *
         * Browser kemudian akan membuat:
         *
         * multipart/form-data;
         * boundary=---------------------------
         *
         * sendiri.
         */

        if (
            config.data instanceof FormData
        ) {

            if (
                config.headers
            ) {

                delete (
                    config.headers as any
                )["Content-Type"];

                delete (
                    config.headers as any
                )["content-type"];
            }
        }

        /**
         * ==================================================
         * DEBUG
         * ==================================================
         */

        console.log(
            "[API REQUEST]",
            {
                method:
                    config.method?.toUpperCase(),

                baseURL:
                    config.baseURL,

                url:
                    config.url,

                fullURL:
                    `${config.baseURL ?? ""}${config.url ?? ""}`,

                isFormData:
                    config.data instanceof FormData,

                contentType:
                    config.headers?.[
                        "Content-Type"
                    ] ??
                    config.headers?.[
                        "content-type"
                    ],
            },
        );

        return config;
    },

    (error) => {
        return Promise.reject(
            error,
        );
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
         * ==================================================
         * API ERROR LOG
         * ==================================================
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

                fullURL:
                    `${error?.config?.baseURL ?? ""}${error?.config?.url ?? ""}`,

                status,

                detail,

                response:
                    responseData,
            },
        );

        /**
         * ==================================================
         * 422 VALIDATION ERROR
         * ==================================================
         */

        if (
            status === 422
        ) {

            console.error(
                "[API VALIDATION ERROR]",
                responseData,
            );
        }

        /**
         * ==================================================
         * 401
         * ==================================================
         */

        if (
            status === 401
        ) {

            console.warn(
                "API unauthorized:",
                detail,
            );
        }

        /**
         * ==================================================
         * 4XX
         * ==================================================
         */

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

        /**
         * ==================================================
         * 5XX
         * ==================================================
         */

        if (
            status !== undefined &&
            status >= 500
        ) {

            console.error(
                "API server error:",
                detail,
            );
        }

        /**
         * ==================================================
         * NETWORK ERROR
         * ==================================================
         */

        if (
            !error?.response
        ) {

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

        return Promise.reject(
            error,
        );
    },
);

console.log(
    "[API CONFIG]",
    {
        environment:
            import.meta.env.MODE,

        baseURL:
            API_BASE_URL,
    },
);

export default api;