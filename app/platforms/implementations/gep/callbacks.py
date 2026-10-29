"""GEP event interpretation and exact platform-job correlation."""

from sqlalchemy.orm import Session
from stage_events_client.models import BaseCloudEvent

from app.database.models.processing_job import ProcessingJobRecord
from app.schemas.enum import ProcessTypeEnum, ProcessingStatusEnum

STAGE_TO_APEX_STATUS: dict[str, ProcessingStatusEnum] = {
    "submitted": ProcessingStatusEnum.QUEUED,
    "prepared": ProcessingStatusEnum.RUNNING,
    "staged": ProcessingStatusEnum.RUNNING,
    "piped": ProcessingStatusEnum.FINISHED,
    "completed": ProcessingStatusEnum.FINISHED,
    "failed": ProcessingStatusEnum.FAILED,
    "dismissed": ProcessingStatusEnum.CANCELED,
}


def extract_job_identifier(cloud_event: BaseCloudEvent) -> str | None:
    """Extract job_identifier strictly from CloudEvent subject metadata."""
    # CloudEvent subject pattern: "<namespace>:<workflow_uid>:<workflow_name>"
    subject = getattr(cloud_event, "subject", None)
    if not subject:
        return None

    parts = subject.split(":")
    if len(parts) == 3:
        return f"{parts[0]}:{parts[2]}"
    return subject


def get_gep_job(database: Session, job_identifier: str) -> ProcessingJobRecord | None:
    """Never interpret a GEP identifier as an APEx ID or use suffix matching.

    Subjects carry no trusted backend identity. If multiple OGC jobs have
    overlapping identifiers, reject the event instead of picking the first job.
    """
    matches = (
        database.query(ProcessingJobRecord)
        .filter(
            ProcessingJobRecord.label == ProcessTypeEnum.OGC_API_PROCESS,
            ProcessingJobRecord.platform_job_id == job_identifier,
        )
        .all()
    )
    if len(matches) > 1:
        raise ValueError("Ambiguous GEP job identifier")
    return matches[0] if matches else None
