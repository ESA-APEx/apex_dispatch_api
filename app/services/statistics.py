from datetime import date, datetime, time
import json
from threading import Lock
from typing import Any, Dict, Iterable, Sequence, Tuple, cast
from urllib.parse import unquote, urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.models.processing_job import ProcessingJobRecord
from app.database.models.upscaling_task import UpscalingTaskRecord
from app.schemas.statistics import (
    EntityStatistics,
    PublicStatisticsResponse,
    UpscalingStatistics,
)

STATISTICS_CACHE_TTL_SECONDS = 60 * 15
_STATISTICS_CACHE: Dict[tuple[str, str], tuple[datetime, dict]] = {}
_STATISTICS_CACHE_LOCK = Lock()


def _normalize_grouped_counts(rows: Iterable[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        key, count = cast(Sequence[Any], row)
        normalized_key = key.value if hasattr(key, "value") else str(key)
        counts[normalized_key] = int(count)
    return counts


def _extract_service_key(raw_service: str | None) -> str:
    if not raw_service:
        return "unknown"
    try:
        service = json.loads(raw_service)
    except (TypeError, ValueError):
        return "unknown"

    application = service.get("application")
    if not isinstance(application, str) or not application.strip():
        return "unknown"

    parsed = urlparse(application)
    process_id = parsed.path.strip("/").split("/")[-1] if parsed.path else ""
    if not process_id:
        process_id = application.strip()

    process_id = unquote(process_id)
    if process_id.endswith(".json"):
        process_id = process_id[:-5]

    return process_id or "unknown"


def _count_services(service_rows: Iterable[Tuple[str | None]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for (raw_service,) in service_rows:
        key = _extract_service_key(raw_service)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _get_date_bounds(
    date_from: date | None,
    date_to: date | None,
) -> tuple[datetime | None, datetime | None]:
    start_datetime = datetime.combine(date_from, time.min) if date_from else None
    end_datetime = datetime.combine(date_to, time.max) if date_to else None
    return start_datetime, end_datetime


def _make_cache_key(
    date_from: date | None,
    date_to: date | None,
) -> tuple[str, str]:
    return (
        date_from.isoformat() if date_from else "",
        date_to.isoformat() if date_to else "",
    )


def _get_cached_statistics(
    cache_key: tuple[str, str], now: datetime
) -> PublicStatisticsResponse | None:
    with _STATISTICS_CACHE_LOCK:
        entry = _STATISTICS_CACHE.get(cache_key)
        if not entry:
            return None

        expiry, payload = entry
        if expiry <= now:
            _STATISTICS_CACHE.pop(cache_key, None)
            return None

        return PublicStatisticsResponse.model_validate(payload)


def _set_cached_statistics(
    cache_key: tuple[str, str],
    now: datetime,
    statistics: PublicStatisticsResponse,
) -> None:
    expires_at = now.replace(microsecond=0)
    expires_at = datetime.fromtimestamp(
        expires_at.timestamp() + STATISTICS_CACHE_TTL_SECONDS
    )

    with _STATISTICS_CACHE_LOCK:
        _STATISTICS_CACHE[cache_key] = (
            expires_at,
            statistics.model_dump(mode="json"),
        )


def get_public_statistics(
    database: Session,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PublicStatisticsResponse:
    now = datetime.utcnow()
    cache_key = _make_cache_key(date_from, date_to)
    cached_statistics = _get_cached_statistics(cache_key=cache_key, now=now)
    if cached_statistics is not None:
        return cached_statistics

    start_datetime, end_datetime = _get_date_bounds(date_from, date_to)

    processing_jobs_query = database.query(ProcessingJobRecord)
    upscaling_tasks_query = database.query(UpscalingTaskRecord)

    if start_datetime is not None:
        processing_jobs_query = processing_jobs_query.filter(
            ProcessingJobRecord.created >= start_datetime
        )
        upscaling_tasks_query = upscaling_tasks_query.filter(
            UpscalingTaskRecord.created >= start_datetime
        )

    if end_datetime is not None:
        processing_jobs_query = processing_jobs_query.filter(
            ProcessingJobRecord.created <= end_datetime
        )
        upscaling_tasks_query = upscaling_tasks_query.filter(
            UpscalingTaskRecord.created <= end_datetime
        )

    processing_jobs_total = (
        processing_jobs_query.with_entities(func.count(ProcessingJobRecord.id)).scalar()
        or 0
    )
    upscaling_tasks_total = (
        upscaling_tasks_query.with_entities(func.count(UpscalingTaskRecord.id)).scalar()
        or 0
    )

    processing_jobs_by_status = _normalize_grouped_counts(
        processing_jobs_query.with_entities(
            ProcessingJobRecord.status, func.count(ProcessingJobRecord.id)
        )
        .group_by(ProcessingJobRecord.status)
        .all()
    )
    processing_jobs_by_platform = _normalize_grouped_counts(
        processing_jobs_query.with_entities(
            ProcessingJobRecord.label, func.count(ProcessingJobRecord.id)
        )
        .group_by(ProcessingJobRecord.label)
        .all()
    )
    processing_jobs_by_service = _count_services(
        processing_jobs_query.with_entities(ProcessingJobRecord.service).all()
    )
    upscaling_tasks_by_status = _normalize_grouped_counts(
        upscaling_tasks_query.with_entities(
            UpscalingTaskRecord.status, func.count(UpscalingTaskRecord.id)
        )
        .group_by(UpscalingTaskRecord.status)
        .all()
    )
    upscaling_tasks_by_platform = _normalize_grouped_counts(
        upscaling_tasks_query.with_entities(
            UpscalingTaskRecord.label, func.count(UpscalingTaskRecord.id)
        )
        .group_by(UpscalingTaskRecord.label)
        .all()
    )
    upscaling_tasks_by_service = _count_services(
        upscaling_tasks_query.with_entities(UpscalingTaskRecord.service).all()
    )

    processing_jobs_linked_to_upscaling_tasks = (
        processing_jobs_query.with_entities(func.count(ProcessingJobRecord.id))
        .filter(ProcessingJobRecord.upscaling_task_id.isnot(None))
        .scalar()
        or 0
    )

    average_jobs_per_upscaling_task = (
        round(processing_jobs_linked_to_upscaling_tasks / upscaling_tasks_total, 2)
        if upscaling_tasks_total
        else 0.0
    )

    statistics = PublicStatisticsResponse(
        generated_at=now,
        processing_jobs=EntityStatistics(
            total=processing_jobs_total,
            by_status=processing_jobs_by_status,
            by_platform=processing_jobs_by_platform,
            by_service=processing_jobs_by_service,
        ),
        upscaling_tasks=UpscalingStatistics(
            total=upscaling_tasks_total,
            by_status=upscaling_tasks_by_status,
            by_platform=upscaling_tasks_by_platform,
            by_service=upscaling_tasks_by_service,
            average_processing_jobs_per_upscaling_task=average_jobs_per_upscaling_task,
        ),
    )
    _set_cached_statistics(cache_key=cache_key, now=now, statistics=statistics)
    return statistics
