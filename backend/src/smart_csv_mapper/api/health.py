"""Liveness and readiness probes (the names Kubernetes and OpenShift expect)."""

from fastapi import APIRouter, Request, Response

from smart_csv_mapper.llm.base import LLMProvider

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """The process is up. Never checks dependencies: a down model must not restart the API."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request, response: Response) -> dict[str, str]:
    """The app can serve traffic: the model provider answers."""
    llm: LLMProvider = request.app.state.llm
    if not await llm.is_ready():
        response.status_code = 503
        return {"status": "unavailable", "llm": llm.name}
    return {"status": "ok", "llm": llm.name}
