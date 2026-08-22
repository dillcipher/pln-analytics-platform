"""Reference implementation contract for asynchronous ETL dispatch."""
from app.application.etl.async_job_runner import start_etl_background

__all__ = ["start_etl_background"]
