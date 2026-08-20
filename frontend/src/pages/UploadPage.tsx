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
            throw new Error(
                current.error
                    ? String(current.error)
                    : `ETL gagal dengan status ${status}`,
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

            const jobId =
                result?.job_id;

            if (!jobId) {

                throw new Error(
                    "Upload berhasil tetapi job_id tidak ditemukan.",
                );
            }

            console.log(
                "ETL JOB:",
                jobId,
            );

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

            alert(
                err?.message ||
                "Upload atau proses ETL gagal.",
            );

        }

        finally {

            setLoading(false);

        }
    }

    const progress =
        Number(
            job?.progress ?? 0,
        );

    const status =
        String(
            job?.status || "",
        ).toUpperCase();

    const isFinished =
        status === "FINISHED";

    const currentStep =
        job?.current_step ||
        "Menunggu proses...";

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
                            {job?.status ||
                                "UPLOADED"}
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
                                    `${Math.min(
                                        Math.max(
                                            progress,
                                            0,
                                        ),
                                        100,
                                    )}%`,
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
                        {progress}%
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

                    <p>
                        Job:{" "}
                        <strong>
                            {job?.job_id}
                        </strong>
                    </p>

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