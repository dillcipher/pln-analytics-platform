# Production bootstrap compatibility hooks. Keep this import first so
# recovery/month-resolution fixes are installed before app.main imports
# the ETL and job-recovery modules.
from app import bootstrap_recovery as _bootstrap_recovery  # noqa: F401
