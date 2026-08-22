import { uploadFiles, type UploadFilesResponse } from "./upload";

export interface BatchUploadFailure {
    filename: string;
    error: string;
}

export interface BatchUploadResponse {
    success: boolean;
    total_files: number;
    uploaded_files: number;
    files: UploadFilesResponse["files"];
    jobs: UploadFilesResponse["jobs"];
    failures: BatchUploadFailure[];
}

function errorMessage(error: unknown): string {
    const value = error as any;
    const detail = value?.response?.data?.detail;

    if (Array.isArray(detail)) {
        return detail
            .map((item: any) =>
                typeof item === "string"
                    ? item
                    : item?.msg || JSON.stringify(item),
            )
            .join(" | ");
    }

    if (detail !== undefined && detail !== null) {
        return String(detail);
    }

    return value?.message
        ? String(value.message)
        : "Upload gagal.";
}

/**
 * Upload files strictly one-by-one.
 *
 * The existing chunk uploader is already retry-safe per chunk. Running one
 * complete file at a time is intentional: it prevents several large XLSX
 * jobs from being queued simultaneously and exhausting the ETL runtime.
 * A bad file does not abort the remaining files in the batch.
 */
export async function uploadBatchFiles(
    files: File[],
): Promise<BatchUploadResponse> {
    if (!files.length) {
        throw new Error("No files selected.");
    }

    const uploaded: UploadFilesResponse["files"] = [];
    const jobs: UploadFilesResponse["jobs"] = [];
    const failures: BatchUploadFailure[] = [];

    for (const file of files) {
        try {
            const result = await uploadFiles([file]);
            uploaded.push(...result.files);
            jobs.push(...result.jobs);
        } catch (error) {
            failures.push({
                filename: file.name,
                error: errorMessage(error),
            });
        }
    }

    if (!uploaded.length && failures.length) {
        throw new Error(
            failures
                .map((item) => `${item.filename}: ${item.error}`)
                .join("\n"),
        );
    }

    return {
        success: failures.length === 0,
        total_files: files.length,
        uploaded_files: uploaded.length,
        files: uploaded,
        jobs,
        failures,
    };
}
