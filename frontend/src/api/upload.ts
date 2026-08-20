import api from "./api";

/**
 * ==========================================================
 * CHUNKED UPLOAD CONFIGURATION
 * ==========================================================
 *
 * 5 MB per chunk.
 *
 * Flow:
 *
 *   File
 *     ↓
 *   /upload/chunk
 *     ↓
 *   /upload/chunk
 *     ↓
 *   ...
 *     ↓
 *   /upload/complete
 *     ↓
 *   job_id
 *     ↓
 *   BACKEND AUTOMATICALLY RUNS:
 *       assembly
 *       ↓
 *       ETL
 *
 * IMPORTANT:
 *
 * Frontend MUST NOT call:
 *
 *   /upload/process/{job_id}
 *
 * because backend /upload/complete already queues
 * assembly + ETL as a background task.
 *
 * ==========================================================
 */

const CHUNK_SIZE = 5 * 1024 * 1024; // 5 MB

/**
 * Retry hanya untuk error transient.
 *
 * Jangan retry 400/401/403/404/405/409/422
 * karena biasanya request memang invalid atau
 * backend sedang memberikan state yang harus ditunggu.
 */

const MAX_RETRIES = 8;

const RETRYABLE_STATUS_CODES = new Set([
    408,
    429,
    500,
    502,
    503,
    504,
]);

/**
 * ==========================================================
 * TYPES
 * ==========================================================
 */

interface ChunkUploadResponse {
    success: boolean;
    upload_id: string;
    filename: string;
    chunk_number: number;
    total_chunks: number;
    received_bytes: number;
    storage?: string;
}

interface CompleteUploadResponse {
    success: boolean;
    job_id: string;
    uploaded_at?: string;
    total_files?: number;
    files?: unknown[];
    status?: string;
}

export interface UploadResult {
    filename: string;
    upload_id: string;
    job_id: string;
    total_chunks: number;
    complete: CompleteUploadResponse;
}

export interface UploadFilesResponse {
    success: boolean;
    total_files: number;
    files: UploadResult[];

    jobs: Array<{
        filename: string;
        upload_id: string;
        job_id: string;
        total_chunks: number;
        status: string;
    }>;
}

/**
 * ==========================================================
 * HELPERS
 * ==========================================================
 */

function sleep(
    milliseconds: number,
): Promise<void> {

    return new Promise(
        (resolve) => {

            window.setTimeout(
                resolve,
                milliseconds,
            );

        },
    );
}

/**
 * ==========================================================
 * CREATE UNIQUE UPLOAD ID
 * ==========================================================
 */

function createUploadId(
    file: File,
): string {

    const now =
        new Date();

    const date =
        `${now.getFullYear()}` +
        `${String(
            now.getMonth() + 1,
        ).padStart(2, "0")}` +
        `${String(
            now.getDate(),
        ).padStart(2, "0")}`;

    const time =
        `${String(
            now.getHours(),
        ).padStart(2, "0")}` +
        `${String(
            now.getMinutes(),
        ).padStart(2, "0")}` +
        `${String(
            now.getSeconds(),
        ).padStart(2, "0")}`;

    const random =
        Math.random()
            .toString(36)
            .substring(2, 8)
            .toUpperCase();

    const safeFilename =
        file.name
            .replace(
                /[^a-zA-Z0-9]/g,
                "",
            )
            .substring(
                0,
                20,
            );

    return (
        `UPLOAD_${date}_${time}_${random}_${safeFilename}`
    );
}

/**
 * ==========================================================
 * ERROR EXTRACTION
 * ==========================================================
 */

function getApiErrorDetail(
    error: any,
): string {

    const detail =
        error?.response?.data?.detail;

    if (Array.isArray(detail)) {

        return detail
            .map(
                (item: any) => {

                    if (
                        typeof item === "string"
                    ) {
                        return item;
                    }

                    if (
                        item?.msg
                    ) {
                        return String(
                            item.msg,
                        );
                    }

                    return JSON.stringify(
                        item,
                    );
                },
            )
            .join(" | ");
    }

    if (
        detail !== undefined &&
        detail !== null
    ) {

        return String(
            detail,
        );
    }

    const message =
        error?.response?.data?.message ??
        error?.message;

    if (
        message !== undefined &&
        message !== null
    ) {

        return String(
            message,
        );
    }

    return "Request failed.";
}

/**
 * ==========================================================
 * RETRY DECISION
 * ==========================================================
 */

function shouldRetry(
    error: any,
): boolean {

    const status =
        error?.response?.status;

    /**
     * Network error:
     * tidak ada HTTP response.
     */

    if (
        !error?.response
    ) {

        return true;
    }

    return RETRYABLE_STATUS_CODES.has(
        Number(status),
    );
}

/**
 * ==========================================================
 * UPLOAD ONE CHUNK
 * ==========================================================
 */

async function uploadChunkWithRetry(
    uploadId: string,
    file: File,
    chunk: Blob,
    chunkNumber: number,
    totalChunks: number,
): Promise<ChunkUploadResponse> {

    let lastError: unknown =
        null;

    for (
        let attempt = 1;
        attempt <= MAX_RETRIES;
        attempt++
    ) {

        try {

            const formData =
                new FormData();

            /**
             * IMPORTANT:
             *
             * Nama field HARUS sama dengan
             * parameter FastAPI:
             *
             * upload_id
             * filename
             * chunk_number
             * total_chunks
             * file
             */

            formData.append(
                "upload_id",
                uploadId,
            );

            formData.append(
                "filename",
                file.name,
            );

            formData.append(
                "chunk_number",
                String(
                    chunkNumber,
                ),
            );

            formData.append(
                "total_chunks",
                String(
                    totalChunks,
                ),
            );

            formData.append(
                "file",
                chunk,
                `chunk_${String(
                    chunkNumber,
                ).padStart(
                    3,
                    "0",
                )}.part`,
            );

            console.log(
                `Uploading chunk ${
                    chunkNumber + 1
                } / ${totalChunks}`,
            );

            console.log(
                "Chunk info:",
                {
                    uploadId,
                    filename:
                        file.name,
                    chunkNumber,
                    totalChunks,
                    chunkSize:
                        chunk.size,
                },
            );

            /**
             * IMPORTANT:
             *
             * JANGAN set:
             *
             * Content-Type:
             * multipart/form-data
             *
             * secara manual.
             *
             * Browser harus membuat boundary.
             */

            const response =
                await api.post<ChunkUploadResponse>(
                    "/upload/chunk",
                    formData,
                    {
                        timeout: 180000,

                        headers: {
                            Accept:
                                "application/json",
                        },
                    },
                );

            console.log(
                "CHUNK SUCCESS",
                {
                    chunkNumber,
                    response:
                        response.data,
                },
            );

            return response.data;

        }

        catch (error: any) {

            lastError =
                error;

            const status =
                error?.response?.status;

            const detail =
                getApiErrorDetail(
                    error,
                );

            console.error(
                "CHUNK ERROR",
                {
                    chunkNumber,
                    attempt,
                    status,
                    detail,
                },
            );

            /**
             * 422 tidak di-retry.
             *
             * 422 berarti request sudah sampai
             * backend tetapi validasi gagal.
             */

            if (
                !shouldRetry(
                    error,
                )
            ) {

                throw new Error(
                    `Chunk ${
                        chunkNumber + 1
                    } gagal (${
                        status ?? "NETWORK"
                    }): ${detail}`,
                );
            }

            if (
                attempt >= MAX_RETRIES
            ) {

                break;
            }

            const delay =
                Math.min(
                    2000 * attempt,
                    10000,
                );

            console.warn(
                `Retry chunk ${
                    chunkNumber + 1
                } dalam ${delay}ms...`,
            );

            await sleep(
                delay,
            );
        }
    }

    throw lastError ??
        new Error(
            `Chunk ${
                chunkNumber + 1
            } gagal di-upload.`,
        );
}

/**
 * ==========================================================
 * UPLOAD SINGLE FILE
 * ==========================================================
 */

async function uploadSingleFile(
    file: File,
): Promise<UploadResult> {

    const uploadId =
        createUploadId(
            file,
        );

    const totalChunks =
        Math.ceil(
            file.size /
                CHUNK_SIZE,
        );

    console.log(
        "================================",
    );

    console.log(
        "START CHUNKED UPLOAD",
    );

    console.log(
        "Filename:",
        file.name,
    );

    console.log(
        "Size:",
        file.size,
        "bytes",
    );

    console.log(
        "Chunk size:",
        CHUNK_SIZE,
        "bytes",
    );

    console.log(
        "Total chunks:",
        totalChunks,
    );

    console.log(
        "Upload ID:",
        uploadId,
    );

    console.log(
        "================================",
    );

    /**
     * ======================================================
     * 1. UPLOAD ALL CHUNKS
     * ======================================================
     */

    for (
        let chunkNumber = 0;
        chunkNumber < totalChunks;
        chunkNumber++
    ) {

        const start =
            chunkNumber *
            CHUNK_SIZE;

        const end =
            Math.min(
                start +
                    CHUNK_SIZE,
                file.size,
            );

        const chunk =
            file.slice(
                start,
                end,
            );

        await uploadChunkWithRetry(
            uploadId,
            file,
            chunk,
            chunkNumber,
            totalChunks,
        );
    }

    console.log(
        "================================",
    );

    console.log(
        "ALL CHUNKS UPLOADED",
    );

    console.log(
        {
            uploadId,
            totalChunks,
        },
    );

    console.log(
        "================================",
    );

    /**
     * ======================================================
     * 2. COMPLETE UPLOAD
     * ======================================================
     *
     * Backend:
     *
     *   /upload/complete
     *
     * akan:
     *
     *   - verify seluruh chunk
     *   - membuat job_id
     *   - queue assembly
     *   - queue ETL
     *   - return job_id
     *
     * Frontend TIDAK perlu memanggil
     * /upload/process/{job_id}.
     */

    const completeForm =
        new FormData();

    completeForm.append(
        "upload_id",
        uploadId,
    );

    completeForm.append(
        "filename",
        file.name,
    );

    completeForm.append(
        "total_chunks",
        String(
            totalChunks,
        ),
    );

    completeForm.append(
        "content_type",
        file.type ||
            "application/octet-stream",
    );

    console.log(
        "Completing upload...",
    );

    let completeResponse;

    try {

        completeResponse =
            await api.post<CompleteUploadResponse>(
                "/upload/complete",
                completeForm,
                {
                    timeout: 180000,

                    headers: {
                        Accept:
                            "application/json",
                    },
                },
            );

    }

    catch (error: any) {

        const detail =
            getApiErrorDetail(
                error,
            );

        throw new Error(
            `Complete upload gagal: ${detail}`,
        );
    }

    const complete =
        completeResponse.data;

    console.log(
        "UPLOAD COMPLETE",
        complete,
    );

    if (
        !complete.success
    ) {

        throw new Error(
            "Backend menyatakan upload completion gagal.",
        );
    }

    if (
        !complete.job_id
    ) {

        throw new Error(
            "Upload selesai tetapi backend tidak mengembalikan job_id.",
        );
    }

    /**
     * ======================================================
     * 3. BACKEND PIPELINE QUEUED
     * ======================================================
     *
     * JANGAN panggil:
     *
     *   /upload/process/{job_id}
     *
     * lagi.
     *
     * Backend sudah melakukan:
     *
     *   /upload/complete
     *        ↓
     *   background assembly
     *        ↓
     *   manifest
     *        ↓
     *   ETL
     *
     * UploadPage akan melakukan polling job status.
     */

    console.log(
        "================================",
    );

    console.log(
        "UPLOAD ACCEPTED",
    );

    console.log(
        "Job ID:",
        complete.job_id,
    );

    console.log(
        "Backend status:",
        complete.status ||
            "ASSEMBLY_QUEUED",
    );

    console.log(
        "Assembly + ETL running in background.",
    );

    console.log(
        "DO NOT CALL /upload/process/{job_id}",
    );

    console.log(
        "================================",
    );

    /**
     * ======================================================
     * 4. RETURN
     * ======================================================
     */

    return {
        filename:
            file.name,

        upload_id:
            uploadId,

        job_id:
            complete.job_id,

        total_chunks:
            totalChunks,

        complete,
    };
}

/**
 * ==========================================================
 * PUBLIC UPLOAD FUNCTION
 * ==========================================================
 */

export async function uploadFiles(
    files: File[],
): Promise<UploadFilesResponse> {

    console.log(
        "================================",
    );

    console.log(
        "UPLOAD START",
    );

    console.log(
        "Total Files:",
        files.length,
    );

    console.log(
        "================================",
    );

    if (
        !files.length
    ) {

        throw new Error(
            "No files selected.",
        );
    }

    console.time(
        "UPLOAD",
    );

    try {

        const results:
            UploadResult[] = [];

        /**
         * ==================================================
         * SEQUENTIAL FILE UPLOAD
         * ==================================================
         *
         * Jangan upload beberapa file secara paralel.
         */

        for (
            const file of files
        ) {

            const result =
                await uploadSingleFile(
                    file,
                );

            results.push(
                result,
            );
        }

        console.timeEnd(
            "UPLOAD",
        );

        console.log(
            "UPLOAD ACCEPTED",
            results,
        );

        /**
         * ==================================================
         * RESPONSE UNTUK UploadPage
         * ==================================================
         */

        return {
            success: true,

            total_files:
                results.length,

            files:
                results,

            jobs:
                results.map(
                    (
                        result,
                    ) => ({
                        filename:
                            result.filename,

                        upload_id:
                            result.upload_id,

                        job_id:
                            result.job_id,

                        total_chunks:
                            result.total_chunks,

                        status:
                            result.complete
                                .status ||
                            "ASSEMBLY_QUEUED",
                    }),
                ),
        };

    }

    catch (error) {

        console.timeEnd(
            "UPLOAD",
        );

        console.error(
            "UPLOAD FAILED",
            error,
        );

        throw error;
    }
}