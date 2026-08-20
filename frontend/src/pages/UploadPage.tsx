import {
    useEffect,
    useRef,
    useState,
} from "react";

import UploadDropzone from "../components/upload/UploadDropzone";
import UploadFileTable from "../components/upload/UploadFileTable";

import { uploadFiles } from "../api/upload";
import {
    getJobStatus,
    type JobHistory,
} from "../api/system";

const POLL_INTERVAL = 2000;

export default function UploadPage() {

    const [files, setFiles] =
        useState<File[]>([]);

    const [uploadResult, setUploadResult] =
        useState<any>(null);

    const [job, setJob] =
        useState<JobHistory | null>(null);

    const [loading, setLoading] =
        useState(false);

    const pollTimer =
        useRef<number | null>(null);

    useEffect(() => {

        return () => {

            if (pollTimer.current !== null) {
                window.clearTimeout(
                    pollTimer.current,
                );
            }

        };

    }, []);

    async function pollJob(
        jobId: string,
    ): Promise<JobHistory> {

        const current =
            await getJobStatus(jobId);

        setJob(current);

        const status =
            String(
                current.status || "",
            ).toUpperCase();

        if (status === "FINISHED") {
            return current;
        }

        if (
            status === "FAILED" ||
            status === "ERROR"
        ) {

            const errorMessage =
                current.error != null
                    ? String(current.error)
                    : `ETL gagal dengan status ${status}`;

            throw new Error(
                errorMessage,
            );
        }

        await new Promise<void>(
            (resolve) => {

                pollTimer.current =
                    window.setTimeout(
                        resolve,
                        POLL_INTERVAL,
                    );

            },
        );

        return pollJob(jobId);
    }

    async function handleUpload() {

        if (files.length === 0) {

            alert(
                "Pilih file terlebih dahulu.",
            );

            return;
        }

        setLoading(true);
        setUploadResult(null);
        setJob(null);

        if (pollTimer.current !== null) {

            window.clearTimeout(
                pollTimer.current,
            );

            pollTimer.current = null;
        }

        try {

            console.log(
                "==============================",
            );

            console.log(
                "UPLOAD START",
            );

            console.log(
                "Total Files :",
                files.length,
            );

            const result =
                await uploadFiles(files);

            console.log(
                "UPLOAD RESPONSE",
                result,
            );

            setUploadResult(result);

            /*
             * Backend response sekarang:
             *
             * {
             *   success: true,
             *   total_files: 1,
             *   files: [...],
             *   jobs: [
             *     {
             *       filename: "...",
             *       upload_id: "...",
             *       job_id: "...",
             *       total_chunks: 143,
             *       status: "UPLOADED"
             *     }
             *   ]
             * }
             *
             * Jadi job_id berada di:
             *
             * result.jobs[0].job_id
             */

            const jobs =
                Array.isArray(result?.jobs)
                    ? result.jobs
                    : [];

            if (jobs.length === 0) {

                throw new Error(
                    "Upload berhasil tetapi daftar job tidak ditemukan.",
                );
            }

            const firstJob =
                jobs[0];

            const jobId =
                firstJob?.job_id;

            if (!jobId) {

                throw new Error(
                    "Upload berhasil tetapi job_id tidak ditemukan.",
                );
            }

            console.log(
                "ETL JOB:",
                jobId,
            );

            /*
             * Backend sudah membuat job.
             * Sekarang frontend polling status
             * sampai FINISHED / FAILED.
             */

            const finishedJob =
                await pollJob(
                    String(jobId),
                );

            console.log(
                "ETL FINISHED:",
                finishedJob,
            );

            setJob(
                finishedJob,
            );

        }

        catch (err: any) {

            console.error(
                "UPLOAD / ETL FAILED",
                err,
            );

            const message =
                err?.response?.data?.detail != null
                    ? Array.isArray(
                        err.response.data.detail,
                    )
                        ? err.response.data.detail
                            .map((item: any) =>
                                typeof item === "string"
                                    ? item
                                    : item?.msg ||
                                      JSON.stringify(item),
                            )
                            .join("\n")
                        : String(
                            err.response.data.detail,
                        )
                    : err?.message
                        ? String(err.message)
                        : "Upload atau proses ETL gagal.";

            alert(message);

        }

        finally {

            setLoading(false);

        }
    }

    const progress =
        Number(
            job?.progress ?? 0,
        );

    const safeProgress =
        Math.min(
            Math.max(
                Number.isFinite(progress)
                    ? progress
                    : 0,
                0,
            ),
            100,
        );

    const status =
        String(
            job?.status || "",
        ).toUpperCase();

    const isFinished =
        status === "FINISHED";

    const isFailed =
        status === "FAILED" ||
        status === "ERROR";

    const currentStep =
        job?.current_step != null
            ? String(job.current_step)
            : "Menunggu proses...";

    const jobError =
        job?.error != null
            ? String(job.error)
            : "";

    return (

        <div>

            <h1>
                Upload Center
            </h1>

            <UploadDropzone
                files={files}
                setFiles={setFiles}
            />

            <UploadFileTable
                files={files}
            />

            <button
                onClick={handleUpload}
                disabled={loading}
                style={{
                    marginTop: 20,
                    padding: "12px 24px",
                    cursor: loading
                        ? "not-allowed"
                        : "pointer",
                }}
            >
                {loading
                    ? "Processing..."
                    : "Upload Files"}
            </button>

            {loading && (

                <div
                    style={{
                        marginTop: 20,
                        padding: 20,
                        border:
                            "1px solid #2d4f70",
                        borderRadius: 10,
                        background:
                            "#111827",
                    }}
                >

                    <h3>
                        ETL sedang diproses
                    </h3>

                    <div
                        style={{
                            marginBottom: 10,
                        }}
                    >
                        Status:{" "}
                        <strong>
                            {job?.status
                                ? String(job.status)
                                : "UPLOADED"}
                        </strong>
                    </div>

                    <div
                        style={{
                            marginBottom: 10,
                        }}
                    >
                        Step:{" "}
                        <strong>
                            {currentStep}
                        </strong>
                    </div>

                    <div
                        style={{
                            width: "100%",
                            height: 10,
                            background:
                                "#374151",
                            borderRadius: 999,
                            overflow: "hidden",
                        }}
                    >

                        <div
                            style={{
                                width:
                                    `${safeProgress}%`,
                                height: "100%",
                                background:
                                    "#22c55e",
                                transition:
                                    "width 0.4s ease",
                            }}
                        />

                    </div>

                    <div
                        style={{
                            marginTop: 8,
                        }}
                    >
                        {safeProgress}%
                    </div>

                </div>

            )}

            {isFinished && (

                <div
                    style={{
                        marginTop: 20,
                        padding: 20,
                        border:
                            "1px solid #22c55e",
                        borderRadius: 10,
                        background:
                            "#111827",
                    }}
                >

                    <h3>
                        Upload & ETL Selesai
                    </h3>

                    <p>
                        Seluruh file sudah
                        diproses dan warehouse
                        sudah diperbarui.
                    </p>

                    {job?.job_id && (

                        <p>
                            Job:{" "}
                            <strong>
                                {String(job.job_id)}
                            </strong>
                        </p>

                    )}

                </div>

            )}

            {isFailed && (

                <div
                    style={{
                        marginTop: 20,
                        padding: 20,
                        border:
                            "1px solid #ef4444",
                        borderRadius: 10,
                        background:
                            "#111827",
                    }}
                >

                    <h3>
                        ETL Gagal
                    </h3>

                    <p>
                        Proses ETL gagal
                        dijalankan.
                    </p>

                    {job?.job_id && (

                        <p>
                            Job:{" "}
                            <strong>
                                {String(job.job_id)}
                            </strong>
                        </p>

                    )}

                    {jobError && (

                        <p>
                            Error:{" "}
                            <strong>
                                {jobError}
                            </strong>
                        </p>

                    )}

                </div>

            )}

            {uploadResult && (

                <div
                    style={{
                        marginTop: 30,
                        padding: 20,
                        border:
                            "1px solid #2d4f70",
                        borderRadius: 10,
                        background:
                            "#111827",
                    }}
                >

                    <h3>
                        Upload Result
                    </h3>

                    <pre
                        style={{
                            whiteSpace:
                                "pre-wrap",
                            overflowX:
                                "auto",
                        }}
                    >
                        {JSON.stringify(
                            uploadResult,
                            null,
                            2,
                        )}
                    </pre>

                </div>

            )}

        </div>
    );
}