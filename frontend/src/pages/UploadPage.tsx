import {
    useEffect,
    useRef,
    useState,
} from "react";

import UploadDropzone from "../components/upload/UploadDropzone";
import UploadFileTable from "../components/upload/UploadFileTable";

import { uploadBatchFiles, type BatchUploadResponse } from "../api/upload_batch";
import {
    getJobStatus,
    type JobHistory,
} from "../api/system";

const POLL_INTERVAL = 3000;

type JobMap = Record<string, JobHistory>;

function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => {
        window.setTimeout(resolve, ms);
    });
}

function statusOf(job: JobHistory | undefined): string {
    return String(job?.status || "UPLOADED").toUpperCase();
}

function isTerminal(job: JobHistory | undefined): boolean {
    const status = statusOf(job);
    return status === "FINISHED" || status === "FAILED" || status === "ERROR";
}

export default function UploadPage() {
    const [files, setFiles] = useState<File[]>([]);
    const [uploadResult, setUploadResult] = useState<BatchUploadResponse | null>(null);
    const [jobs, setJobs] = useState<JobMap>({});
    const [loading, setLoading] = useState(false);
    const pollingRef = useRef(false);

    useEffect(() => {
        return () => {
            pollingRef.current = false;
        };
    }, []);

    async function pollJobs(jobIds: string[]): Promise<JobMap> {
        const pending = new Set(jobIds);
        const latest: JobMap = {};
        const transientFailures: Record<string, number> = {};

        while (pollingRef.current && pending.size > 0) {
            const ids = Array.from(pending);

            const responses = await Promise.allSettled(
                ids.map(async (jobId) => ({
                    jobId,
                    value: await getJobStatus(jobId),
                })),
            );

            for (let index = 0; index < responses.length; index += 1) {
                const response = responses[index];
                const jobId = ids[index];

                if (response.status === "fulfilled") {
                    latest[jobId] = response.value.value;
                    transientFailures[jobId] = 0;

                    if (isTerminal(response.value.value)) {
                        pending.delete(jobId);
                    }
                    continue;
                }

                const error: any = response.reason;
                const httpStatus = Number(error?.response?.status || 0);
                transientFailures[jobId] = (transientFailures[jobId] || 0) + 1;

                // A temporary network/proxy failure must not stop a long ETL.
                // A real 404 means the durable job cannot be found anymore.
                if (httpStatus === 404) {
                    latest[jobId] = {
                        job_id: jobId,
                        status: "FAILED",
                        progress: 100,
                        current_step: "JOB TIDAK DITEMUKAN",
                        error: "Job tidak ditemukan pada backend durable storage.",
                    };
                    pending.delete(jobId);
                }
            }

            setJobs({ ...latest });

            if (pending.size > 0) {
                await sleep(POLL_INTERVAL);
            }
        }

        return latest;
    }

    async function handleUpload() {
        if (files.length === 0) {
            alert("Pilih file terlebih dahulu.");
            return;
        }

        pollingRef.current = true;
        setLoading(true);
        setUploadResult(null);
        setJobs({});

        try {
            console.log("==============================");
            console.log("MULTI-FILE UPLOAD START");
            console.log("Total Files:", files.length);
            console.log("==============================");

            // Files are uploaded one-by-one intentionally. The backend durable
            // worker then processes them one-by-one as well.
            const result = await uploadBatchFiles(files);
            setUploadResult(result);

            const jobIds = result.jobs
                .map((item) => String(item.job_id || "").trim())
                .filter(Boolean);

            if (!jobIds.length) {
                throw new Error(
                    "Tidak ada job yang berhasil dibuat. Periksa daftar file gagal.",
                );
            }

            const finished = await pollJobs(jobIds);
            setJobs(finished);

            const failed = Object.values(finished).filter((job) => {
                const status = statusOf(job);
                return status === "FAILED" || status === "ERROR";
            });

            if (failed.length > 0) {
                throw new Error(
                    `${failed.length} job gagal. Lihat status per file di bawah.`,
                );
            }
        } catch (error: any) {
            console.error("UPLOAD / ETL FAILED", error);
            alert(
                error?.message
                    ? String(error.message)
                    : "Upload atau proses ETL gagal.",
            );
        } finally {
            pollingRef.current = false;
            setLoading(false);
        }
    }

    const jobList = Object.entries(jobs);
    const totalJobs = uploadResult?.jobs.length || 0;
    const finishedJobs = jobList.filter(([, job]) => statusOf(job) === "FINISHED").length;
    const failedJobs = jobList.filter(([, job]) => {
        const status = statusOf(job);
        return status === "FAILED" || status === "ERROR";
    }).length;

    const averageProgress = totalJobs > 0
        ? Math.round(
            uploadResult.jobs.reduce((sum, item) => {
                const current = jobs[String(item.job_id)]?.progress;
                return sum + Math.min(Math.max(Number(current ?? 0), 0), 100);
            }, 0) / totalJobs,
        )
        : 0;

    const allFinished = totalJobs > 0 && finishedJobs === totalJobs;
    const anyFailed = failedJobs > 0;

    return (
        <div>
            <h1>Upload Center</h1>

            <UploadDropzone
                files={files}
                setFiles={setFiles}
            />

            <UploadFileTable files={files} />

            <button
                onClick={handleUpload}
                disabled={loading}
                style={{
                    marginTop: 20,
                    padding: "12px 24px",
                    cursor: loading ? "not-allowed" : "pointer",
                }}
            >
                {loading ? "Uploading & Processing..." : "Upload Files"}
            </button>

            {uploadResult && (
                <div
                    style={{
                        marginTop: 20,
                        padding: 20,
                        border: "1px solid #2d4f70",
                        borderRadius: 10,
                        background: "#111827",
                    }}
                >
                    <h3>Batch Status</h3>
                    <p>
                        Upload: <strong>{uploadResult.uploaded_files}/{uploadResult.total_files}</strong>
                    </p>
                    <p>
                        ETL: <strong>{finishedJobs}/{totalJobs} selesai</strong>
                        {failedJobs > 0 ? ` • ${failedJobs} gagal` : ""}
                    </p>

                    <div
                        style={{
                            width: "100%",
                            height: 10,
                            background: "#374151",
                            borderRadius: 999,
                            overflow: "hidden",
                        }}
                    >
                        <div
                            style={{
                                width: `${averageProgress}%`,
                                height: "100%",
                                background: "#22c55e",
                                transition: "width 0.4s ease",
                            }}
                        />
                    </div>
                    <div style={{ marginTop: 8 }}>
                        {averageProgress}% overall
                    </div>

                    {uploadResult.failures.length > 0 && (
                        <div style={{ marginTop: 16 }}>
                            <strong>File yang gagal upload:</strong>
                            {uploadResult.failures.map((failure) => (
                                <div key={failure.filename}>
                                    {failure.filename}: {failure.error}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {jobList.length > 0 && (
                <div
                    style={{
                        marginTop: 20,
                        padding: 20,
                        border: "1px solid #2d4f70",
                        borderRadius: 10,
                        background: "#111827",
                    }}
                >
                    <h3>ETL Per File</h3>

                    {jobList.map(([jobId, job]) => {
                        const progress = Math.min(
                            Math.max(Number(job.progress ?? 0), 0),
                            100,
                        );
                        const status = statusOf(job);

                        return (
                            <div
                                key={jobId}
                                style={{
                                    marginBottom: 16,
                                    paddingBottom: 12,
                                    borderBottom: "1px solid #263244",
                                }}
                            >
                                <div>
                                    <strong>{job.files?.[0] ? String((job.files[0] as any)?.filename || jobId) : jobId}</strong>
                                </div>
                                <div style={{ marginTop: 4 }}>
                                    Status: <strong>{status}</strong>
                                    {job.current_step ? ` • ${String(job.current_step)}` : ""}
                                </div>
                                <div
                                    style={{
                                        marginTop: 8,
                                        width: "100%",
                                        height: 8,
                                        background: "#374151",
                                        borderRadius: 999,
                                        overflow: "hidden",
                                    }}
                                >
                                    <div
                                        style={{
                                            width: `${progress}%`,
                                            height: "100%",
                                            background: status === "FAILED" || status === "ERROR"
                                                ? "#ef4444"
                                                : "#22c55e",
                                        }}
                                    />
                                </div>
                                <div style={{ marginTop: 4 }}>
                                    {progress}% • Job {jobId}
                                </div>
                                {job.error && (
                                    <div style={{ marginTop: 4 }}>
                                        Error: {String(job.error)}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {allFinished && !anyFailed && (
                <div
                    style={{
                        marginTop: 20,
                        padding: 20,
                        border: "1px solid #22c55e",
                        borderRadius: 10,
                        background: "#111827",
                    }}
                >
                    <h3>Upload & ETL Selesai</h3>
                    <p>
                        Semua job yang berhasil di-upload sudah FINISHED dan
                        warehouse sudah diperbarui.
                    </p>
                </div>
            )}

            {anyFailed && (
                <div
                    style={{
                        marginTop: 20,
                        padding: 20,
                        border: "1px solid #ef4444",
                        borderRadius: 10,
                        background: "#111827",
                    }}
                >
                    <h3>Ada Job yang Gagal</h3>
                    <p>
                        Job gagal tidak menghentikan file lain. Durable worker
                        tetap akan melanjutkan job berikutnya.
                    </p>
                </div>
            )}
        </div>
    );
}
