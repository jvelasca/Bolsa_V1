"""Cola de jobs de research."""

from bolsa_infrastructure.queue.scan_job_arq import ScanJobArqQueue
from bolsa_infrastructure.queue.scan_job_redis import ScanJobRedisQueue

__all__ = ["ScanJobArqQueue", "ScanJobRedisQueue"]
