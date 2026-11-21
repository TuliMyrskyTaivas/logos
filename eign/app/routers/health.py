from __future__ import annotations

from fastapi import APIRouter

from ..schemas import HealthStatus

router = APIRouter(tags=["service"])


@router.get("/health", response_model=HealthStatus, summary="Liveness probe")
def health() -> HealthStatus:
    """Report that the service process is running (used by healthchecks)."""
    return HealthStatus(status="ok")
