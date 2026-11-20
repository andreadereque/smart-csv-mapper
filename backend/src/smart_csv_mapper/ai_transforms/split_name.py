"""Split full names with the model: distinct values only, cached, batched, and verified.

Verification is the guard rail: the answer is accepted only if first + last rebuilds the
input (ignoring spaces, case and a "Surname, First" comma). The model can choose where to
cut, but it can't invent, drop or "fix" a single letter.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from importlib import resources

from pydantic import BaseModel, ValidationError

from smart_csv_mapper.cache import DEFAULT_TTL_SECONDS, Cache
from smart_csv_mapper.llm.base import LLMError, LLMProvider
from smart_csv_mapper.transforms.result import Err, Ok, Result

logger = logging.getLogger(__name__)

PROMPT_VERSION = "split_name_v1"
TEMPLATE = resources.files("smart_csv_mapper.ai_transforms.prompts").joinpath(
    f"{PROMPT_VERSION}.md"
)
BATCH_SIZE = 20
PARTS = ("first", "last")


class SplitItem(BaseModel):
    input: str
    first_name: str
    last_name: str


class SplitAnswer(BaseModel):
    results: list[SplitItem]


ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                },
                "required": ["input", "first_name", "last_name"],
            },
        }
    },
    "required": ["results"],
}


@dataclass
class TransformStats:
    rows: int = 0
    distinct: int = 0
    cache_hits: int = 0
    llm_calls: int = 0
    failed: int = 0
    ms: int = 0


@dataclass
class SplitOutcome:
    parts: dict[str, dict[str, str]] = field(default_factory=dict)  # value -> {first, last}
    errors: dict[str, str] = field(default_factory=dict)  # value -> reason
    stats: TransformStats = field(default_factory=TransformStats)

    def result(self, value: str, part: str) -> Result:
        key = value.strip()
        if key == "":
            return Ok("")
        if key in self.parts:
            return Ok(self.parts[key][part])
        return Err(self.errors.get(key, "name could not be split"))


def _letters(text: str) -> str:
    return "".join(text.replace(",", " ").lower().split())


def is_faithful(original: str, first: str, last: str) -> bool:
    if first.strip() == "" or last.strip() == "":
        return False
    rebuilt = _letters(first + last)
    return rebuilt in (_letters(original), _letters(_swap_comma(original)))


def _swap_comma(text: str) -> str:
    if "," not in text:
        return text
    surname, _, given = text.partition(",")
    return f"{given} {surname}"


class NameSplitter:
    def __init__(self, llm: LLMProvider, cache: Cache, batch_size: int = BATCH_SIZE) -> None:
        self._llm = llm
        self._cache = cache
        self._batch_size = batch_size

    def cache_key(self, value: str) -> str:
        raw = f"split_name|{PROMPT_VERSION}|{self._llm.model}|{value}"
        return "scm:" + hashlib.sha256(raw.encode()).hexdigest()

    async def split(self, values: list[str]) -> SplitOutcome:
        started = time.perf_counter()
        outcome = SplitOutcome()
        distinct = list(dict.fromkeys(v.strip() for v in values if v.strip()))
        outcome.stats.rows = len(values)
        outcome.stats.distinct = len(distinct)
        cached = await self._cache.get_many([self.cache_key(v) for v in distinct])
        misses = []
        for value in distinct:
            hit = cached.get(self.cache_key(value))
            if hit is None:
                misses.append(value)
            else:
                outcome.parts[value] = json.loads(hit)
        outcome.stats.cache_hits = len(distinct) - len(misses)
        for start in range(0, len(misses), self._batch_size):
            await self._split_batch(misses[start : start + self._batch_size], outcome)
        outcome.stats.failed = len(outcome.errors)
        outcome.stats.ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "ai_transform",
            extra={"extra_fields": {"transform": "split_name", **outcome.stats.__dict__}},
        )
        return outcome

    async def _split_batch(self, batch: list[str], outcome: SplitOutcome) -> None:
        pending = batch
        for _ in range(2):  # one retry, only for the values that failed
            if not pending:
                return
            pending = await self._ask(pending, outcome)
        for value in pending:
            outcome.errors[value] = "the model could not split this name faithfully"

    async def _ask(self, batch: list[str], outcome: SplitOutcome) -> list[str]:
        """Ask once; store good answers; return the values that still need an answer."""
        prompt = TEMPLATE.read_text(encoding="utf-8").format(
            names=json.dumps(batch, ensure_ascii=False)
        )
        outcome.stats.llm_calls += 1
        try:
            response = await self._llm.complete_json(prompt, ANSWER_SCHEMA)
            answer = SplitAnswer.model_validate(response.data)
        except LLMError as error:
            for value in batch:
                outcome.errors[value] = f"model not available ({error.kind})"
            return []
        except ValidationError:
            return batch
        accepted: dict[str, str] = {}
        wanted = set(batch)
        for item in answer.results:
            value = item.input.strip()
            if value in wanted and is_faithful(value, item.first_name, item.last_name):
                parts = {"first": item.first_name.strip(), "last": item.last_name.strip()}
                outcome.parts[value] = parts
                accepted[self.cache_key(value)] = json.dumps(parts, ensure_ascii=False)
                wanted.discard(value)
        if accepted:
            await self._cache.set_many(accepted, DEFAULT_TTL_SECONDS)
        return [v for v in batch if v in wanted]
