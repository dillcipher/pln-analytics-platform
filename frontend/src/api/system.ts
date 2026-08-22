import api, { API_ORIGIN } from "./api";

/* ==========================================================
 * TYPES — DATA MANAGEMENT
 * ========================================================== */

export interface DatasetInfo {
    name: string;
    rows: number;
    size_mb: number;
    status?: string;
    [key: string]: unknown;
}

export interface DataOverview {
    total_dataset: number;
    total_rows: number;
    total_size_mb: number;
    datasets: DatasetInfo[];
}

export interface JobHistory {
    job_id?: string;
    status?: string;
    progress?: number;
    current_step?: string;
    created_at?: string;
    uploaded_at?: string;
    started_at?: string;
    finished_at?: string;
    total_files?: number;
    processed_files?: number;
    files?: unknown[];
    [key: string]: unknown;
}

export type ExportFormat = "csv" | "xlsx";

export interface DataManagementExportParams {
    dataset?: string;
    month?: string;
    unitupi?: string;
    unitap?: string;
    unitup?: string;
    tariff?: string;
    segment?: string;
    suspect_name?: string;
    classification?: string;
    location_code?: string;
    idpel?: string;
    columns?: string;
}

export interface DlpdExportParams {
    customer_type?: string;
    month?: string;
    unitupi?: string;
    unitap?: string;
    unitup?: string;
    tariff?: string;
    segment?: string;
    status?: string;
    inspection_status?: string;
    dlpd_repeat?: string;
    kendala?: string;
    search?: string;
    idpel?: string;
}

export interface SuspectExportParams {
    month?: string;
    unitupi?: string;
    unitap?: string;
    unitup?: string;
    classification?: string;
    tariff?: string;
    segment?: string;
    search?: string;
    idpel?: string;
}

export interface SuspectSummaryExportParams {
    month?: string;
    unitupi?: string;
    unitap?: string;
    unitup?: string;
    classification?: string;
    tariff?: string;
    segment?: string;
}

function unwrap<T>(value: unknown): T {
    if (value && typeof value === "object" && !Array.isArray(value)) {
        const record = value as Record<string, unknown>;
        if (record.data !== undefined) return record.data as T;
        if (record.result !== undefined) return record.result as T;
    }
    return value as T;
}

function cleanParams(params: object): Record<string, unknown> {
    return Object.fromEntries(
        Object.entries(params).filter(([, value]) => {
            if (value === undefined || value === null) return false;
            if (typeof value === "string" && value.trim() === "") return false;
            return true;
        }),
    );
}

function downloadBlob(blob: Blob, filename: string): void {
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
}

function safeFilename(value: unknown): string {
    return String(value ?? "")
        .trim()
        .replace(/[^a-zA-Z0-9._-]+/g, "_")
        .replace(/^_+|_+$/g, "");
}

function filenameMonth(month?: string): string {
    if (!month) return "";
    const value = safeFilename(month);
    return value ? `_${value}` : "";
}

export async function getDataOverview(): Promise<DataOverview> {
    const response = await api.get("/data-management/overview");
    const data = unwrap<Partial<DataOverview>>(response.data) || {};
    const datasets = Array.isArray(data.datasets) ? data.datasets : [];
    return {
        total_dataset: Number(data.total_dataset ?? 0),
        total_rows: Number(data.total_rows ?? 0),
        total_size_mb: Number(data.total_size_mb ?? 0),
        datasets: datasets as DatasetInfo[],
    };
}

export async function getJobHistory(): Promise<JobHistory[]> {
    const response = await api.get("/history");
    const data = unwrap<unknown>(response.data);
    return Array.isArray(data) ? (data as JobHistory[]) : [];
}

export async function getJobStatus(jobId: string): Promise<JobHistory> {
    const response = await api.get(`/jobs/${encodeURIComponent(jobId)}`);
    return unwrap<JobHistory>(response.data);
}

/* ==========================================================
 * SYSTEM HEALTH
 * ========================================================== */

/**
 * The frontend is hosted on Vercel while FastAPI runs separately. The old
 * implementation incorrectly queried window.location.origin (/health on
 * Vercel), so Settings always reported OFFLINE even when FastAPI was healthy.
 */
export async function getSystemHealth() {
    const response = await fetch(`${API_ORIGIN}/health`, {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
    });

    if (!response.ok) {
        throw new Error(`Health ${response.status}`);
    }

    return response.json() as Promise<{
        status?: string;
        application?: string;
        environment?: string;
    }>;
}

export async function refreshWarehouse() {
    const response = await api.post("/warehouse/refresh");
    return response.data;
}

export async function downloadDataManagementExport(
    params: DataManagementExportParams,
): Promise<Blob> {
    const response = await api.get("/data-management/export", {
        params: cleanParams(params),
        responseType: "blob",
    });
    return response.data as Blob;
}

export async function exportDataManagement(
    params: DataManagementExportParams,
    filename = "data-management-export",
): Promise<void> {
    const blob = await downloadDataManagementExport(params);
    const dataset = safeFilename(params.dataset || "dataset");
    const month = filenameMonth(params.month);
    downloadBlob(blob, `${safeFilename(filename)}_${dataset}${month}.xlsx`);
}

export async function downloadDlpdExport(
    format: ExportFormat,
    params: DlpdExportParams,
): Promise<Blob> {
    const response = await api.get(`/dlpd/customers/export/${format}`, {
        params: cleanParams(params),
        responseType: "blob",
    });
    return response.data as Blob;
}

export async function exportDlpd(
    format: ExportFormat,
    params: DlpdExportParams,
): Promise<Blob> {
    return downloadDlpdExport(format, params);
}

export async function downloadAndExportDlpd(
    format: ExportFormat,
    params: DlpdExportParams,
    filename = "dlpd",
): Promise<void> {
    const blob = await downloadDlpdExport(format, params);
    const customerType = safeFilename(params.customer_type || "all");
    const month = filenameMonth(params.month);
    downloadBlob(blob, `${safeFilename(filename)}_${customerType}${month}.${format}`);
}

export async function downloadSuspectExport(
    format: ExportFormat,
    params: SuspectExportParams,
): Promise<Blob> {
    const response = await api.get(`/suspect/export/${format}`, {
        params: cleanParams(params),
        responseType: "blob",
    });
    return response.data as Blob;
}

export async function exportSuspect(
    format: ExportFormat,
    params: SuspectExportParams,
    filename = "suspect",
): Promise<void> {
    const blob = await downloadSuspectExport(format, params);
    const month = filenameMonth(params.month);
    downloadBlob(blob, `${safeFilename(filename)}${month}.${format}`);
}

export async function downloadSuspectSummaryExport(
    format: ExportFormat,
    params: SuspectSummaryExportParams,
): Promise<Blob> {
    const response = await api.get(`/suspect/summary/export/${format}`, {
        params: cleanParams(params),
        responseType: "blob",
    });
    return response.data as Blob;
}

export async function exportSuspectSummary(
    format: ExportFormat,
    params: SuspectSummaryExportParams,
): Promise<Blob> {
    return downloadSuspectSummaryExport(format, params);
}

export async function downloadAndExportSuspectSummary(
    format: ExportFormat,
    params: SuspectSummaryExportParams,
    filename = "suspect-summary",
): Promise<void> {
    const blob = await downloadSuspectSummaryExport(format, params);
    const month = filenameMonth(params.month);
    downloadBlob(blob, `${safeFilename(filename)}${month}.${format}`);
}

export async function downloadDlpdCsv(params: DlpdExportParams): Promise<void> {
    await downloadAndExportDlpd("csv", params, "dlpd");
}

export async function downloadDlpdXlsx(params: DlpdExportParams): Promise<void> {
    await downloadAndExportDlpd("xlsx", params, "dlpd");
}

export async function downloadSuspectCsv(params: SuspectExportParams): Promise<void> {
    await exportSuspect("csv", params, "suspect");
}

export async function downloadSuspectXlsx(params: SuspectExportParams): Promise<void> {
    await exportSuspect("xlsx", params, "suspect");
}

export async function downloadSuspectSummaryCsv(
    params: SuspectSummaryExportParams,
): Promise<void> {
    await downloadAndExportSuspectSummary("csv", params, "suspect-summary");
}

export async function downloadSuspectSummaryXlsx(
    params: SuspectSummaryExportParams,
): Promise<void> {
    await downloadAndExportSuspectSummary("xlsx", params, "suspect-summary");
}
