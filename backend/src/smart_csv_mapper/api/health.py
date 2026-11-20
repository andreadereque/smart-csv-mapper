"""Liveness and readiness probes (the names Kubernetes and OpenShift expect)."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """The process is up."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz() -> dict[str, str]:
    """The app can serve traffic. Checks Ollama and the cache from PR 4 on."""
    return {"status": "ok"}
