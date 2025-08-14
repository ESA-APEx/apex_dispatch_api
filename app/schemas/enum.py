from enum import Enum


class ProcessTypeEnum(str, Enum):
    OPENEO = "openeo"
    OGC_API_PROCESS = "ogc_api_process"


class ProcessingStatusEnum(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    CANCELED = "canceled"
    FAILED = "failed"
    UNKNOWN = "unknown"
