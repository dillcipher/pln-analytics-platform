from app.application.etl.startup_recovery_once import _is_eligible


def test_exhausted_job_is_never_auto_retried_after_policy_change():
    assert not _is_eligible(
        {
            "status": "MERGING",
            "recovery_attempts": 139,
            "recovery_policy_version": "old-policy",
        }
    )


def test_failed_job_is_not_auto_retried():
    assert not _is_eligible(
        {
            "status": "FAILED",
            "recovery_attempts": 0,
        }
    )


def test_unfinished_job_with_retry_budget_remains_eligible():
    assert _is_eligible(
        {
            "status": "MERGING",
            "recovery_attempts": 0,
        }
    )


def test_exhausted_uploaded_job_is_not_eligible():
    assert not _is_eligible(
        {
            "status": "UPLOADED",
            "recovery_attempts": 3,
        }
    )
