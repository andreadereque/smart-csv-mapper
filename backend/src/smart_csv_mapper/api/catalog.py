"""Read-only endpoints for the UI (and the prompt): target schema and transform catalog."""

from fastapi import APIRouter
from pydantic import BaseModel

from smart_csv_mapper.schema import TARGET_SCHEMA
from smart_csv_mapper.transforms.catalog import CATALOG

router = APIRouter(tags=["catalog"])


class FieldOut(BaseModel):
    name: str
    type: str
    required: bool
    description: str


class TransformOut(BaseModel):
    name: str
    description: str
    required_params: list[str]
    optional_params: list[str]
    free_params: bool


@router.get("/schema")
def get_schema() -> list[FieldOut]:
    return [
        FieldOut(name=f.name, type=f.type, required=f.required, description=f.description)
        for f in TARGET_SCHEMA
    ]


@router.get("/transforms")
def get_transforms() -> list[TransformOut]:
    return [
        TransformOut(
            name=s.name,
            description=s.description,
            required_params=list(s.required_params),
            optional_params=list(s.optional_params),
            free_params=s.free_params,
        )
        for s in CATALOG.values()
    ]
