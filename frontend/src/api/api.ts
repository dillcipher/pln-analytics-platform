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

/**
 * DLPD is the heaviest read surface in the application. The page can mount
 * KPI, ULP, customer-list and map requests at the same time. Sending those
 * parquet scans concurrently defeats the backend memory guard and can push
 * a 500 MB container into OOM.
 *
 * Keep a tiny FIFO gate in the browser for DLPD GET requests. This does not
 * affect uploads or unrelated API calls, and it preserves the existing API
 * contract. A rejected request always releases the next request.
 */
let dlpdReadQueue: Promise<void> = Promise.resolve();

function isDlpdRead(config: any): boolean {
    const method = String(config?.method ?? "get").toLowerCase();
    const url = String(config?.url ?? "");
    return method === "get" && url.includes("/dlpd/");
}

function normalizeDlpdCustomerParams(config: any): void {
    if (!isDlpdRead(config)) return;

    const url = String(config?.url ?? "");
    if (!url.endsWith("/dlpd/customers")) return;

    const params = config.params;
    if (!params || typeof params !== "object") return;

    // The customer table historically used camelCase while FastAPI exposes
    // snake_case query parameters. Normalize at the transport boundary so
    // older callers cannot silently fall back to the default customer type.
    if (
        params.customer_type == null &&
        params.customerType != null
    ) {
        params.customer_type = params.customerType;
    }

    if (
        params.page_size == null &&
        params.pageSize != null
    ) {
        params.page_size = params.pageSize;
    }

    delete params.customerType;
    delete params.pageSize;
}

api.interceptors.request.use(async (config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
        config.headers = config.headers ?? {};
        config.headers.Authorization = `Bearer ${token}`;
    }

    if (config.data instanceof FormData && config.headers) {
        delete (config.headers as any)["Content-Type"];
        delete (config.headers as any)["content-type"];
    }

    normalizeDlpdCustomerParams(config);

    if (isDlpdRead(config)) {
        // Axios starts its timeout after the request interceptor chain. The
        // DLPD FIFO intentionally waits for the previous heavy read, so the
        // normal 120s timeout is too short for queued all-month requests.
        // Give DLPD reads a generous ceiling while keeping other API calls
        // on their normal timeout.
        const configuredTimeout = Number(
            import.meta.env.VITE_DLPD_API_TIMEOUT ||
            import.meta.env.VITE_API_TIMEOUT ||
            120000,
        );
        config.timeout = Math.max(
            Number.isFinite(configuredTimeout)
                ? configuredTimeout
                : 120000,
            600000,
        );

        let release!: () => void;
        const turn = new Promise<void>((resolve) => {
            release = resolve;
        });

        const previous = dlpdReadQueue;
        dlpdReadQueue = previous.then(() => turn);

        await previous;
        (config as any).__dlpdRelease = release;
    }

    return config;
});

function releaseDlpdRead(config: any): void {
    const release = config?.__dlpdRelease;
    if (typeof release === "function") {
        delete config.__dlpdRelease;
        release();
    }
}

api.interceptors.response.use(
    (response) => {
        releaseDlpdRead(response.config);
        return response;
    },
    (error) => {
        releaseDlpdRead(error?.config);

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
