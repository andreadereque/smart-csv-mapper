"""POST /files/{id}/suggest: the model's mapping proposal for an uploaded file."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from smart_csv_mapper.api.files import get_store, get_stored
from smart_csv_mapper.ingest.profile import profile_columns
from smart_csv_mapper.ingest.store import FileStore
from smart_csv_mapper.llm.base import LLMProvider
from smart_csv_mapper.mapping.models import MappingProposal
from smart_csv_mapper.mapping.suggest import suggest_mapping

router = APIRouter(prefix="/files", tags=["mapping"])


def get_llm(request: Request) -> LLMProvider:
    llm: LLMProvider = request.app.state.llm
    return llm


@router.post("/{file_id}/suggest")
async def suggest(
    file_id: str,
    store: Annotated[FileStore, Depends(get_store)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
) -> MappingProposal:
    stored = get_stored(file_id, store)
    return await suggest_mapping(file_id, profile_columns(stored.parsed), llm)
