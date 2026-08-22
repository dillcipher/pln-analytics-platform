# Process endpoint contract

POST /api/v1/process/{job_id} must be non-blocking. It recovers the durable job folder, validates readiness, schedules ETL, and returns a job acknowledgement immediately. ETL completion is observed through the existing durable job status endpoint. A proxy timeout must never be able to turn a running ETL into HTTP 502.
