import json

import pytest

from smart_csv_mapper.ai_transforms.split_name import NameSplitter, is_faithful
from smart_csv_mapper.cache import InMemoryCache
from smart_csv_mapper.llm.base import JsonSchema, LLMError, LLMResponse
from smart_csv_mapper.llm.fake import FakeProvider
from smart_csv_mapper.transforms.result import Err, Ok


def answer(*triples: tuple[str, str, str]) -> dict[str, object]:
    return {"results": [{"input": i, "first_name": f, "last_name": last} for i, f, last in triples]}


def names_in(prompt: str) -> list[str]:
    return list(json.loads(prompt[prompt.rindex("Names:") + len("Names:") :]))


class EchoSplitter(FakeProvider):
    """Splits every name it is asked about at the first space, like a well-behaved model."""

    async def complete_json(self, prompt: str, schema: JsonSchema) -> LLMResponse:
        self.prompts.append(prompt)
        triples = [(n, *n.split(" ", 1)) for n in names_in(prompt)]
        self.answers.append(answer(*triples))  # type: ignore[arg-type]
        return await super().complete_json("", schema)


@pytest.mark.parametrize(
    ("original", "first", "last", "ok"),
    [
        ("María López García", "María", "López García", True),
        ("Juan de la Fuente", "Juan", "de la Fuente", True),
        ("Smith, John", "John", "Smith", True),
        ("ana ruiz", "Ana", "Ruiz", True),
        ("María López", "Maria", "López", False),
        ("María López", "María", "Lopez Gómez", False),
        ("María López", "María López", "", False),
        ("María López", " ", "María López", False),
    ],
)
def test_faithfulness_check(original: str, first: str, last: str, ok: bool) -> None:
    assert is_faithful(original, first, last) is ok


async def test_only_distinct_values_go_to_the_model_and_results_fill_every_row() -> None:
    llm = EchoSplitter()
    values = ["Ana Ruiz", "Ana Ruiz ", "Luis Gil", "", "Ana Ruiz"]
    outcome = await NameSplitter(llm, InMemoryCache()).split(values)
    assert names_in(llm.prompts[0]) == ["Ana Ruiz", "Luis Gil"]
    assert [outcome.result(v, "first") for v in values] == [
        Ok("Ana"),
        Ok("Ana"),
        Ok("Luis"),
        Ok(""),
        Ok("Ana"),
    ]
    assert outcome.result("Luis Gil", "last") == Ok("Gil")
    stats = outcome.stats
    assert (stats.rows, stats.distinct, stats.cache_hits, stats.llm_calls, stats.failed) == (
        5,
        2,
        0,
        1,
        0,
    )


async def test_ten_thousand_rows_with_fifty_names_need_three_calls_then_zero() -> None:
    names = [f"Name{i} Surname{i}" for i in range(50)]
    rows = [names[i % 50] for i in range(10_000)]
    cache = InMemoryCache()
    first_run = await NameSplitter(EchoSplitter(), cache).split(rows)
    assert first_run.stats.llm_calls == 3  # batches of 20, 20 and 10
    second_run = await NameSplitter(EchoSplitter(), cache).split(rows)
    assert second_run.stats.llm_calls == 0
    assert second_run.stats.cache_hits == 50
    assert second_run.result(rows[123], "last") == Ok("Surname23")


async def test_only_the_values_that_failed_are_retried() -> None:
    llm = FakeProvider(
        [
            answer(("Ana Ruiz", "Ana", "Ruiz"), ("Luis Gil", "Luís", "Gil")),
            answer(("Luis Gil", "Luis", "Gil")),
        ]
    )
    outcome = await NameSplitter(llm, InMemoryCache()).split(["Ana Ruiz", "Luis Gil"])
    assert names_in(llm.prompts[1]) == ["Luis Gil"]
    assert outcome.result("Luis Gil", "first") == Ok("Luis")
    assert outcome.stats.llm_calls == 2


async def test_values_still_wrong_after_the_retry_become_errors_and_are_not_cached() -> None:
    bad = answer(("Ana Ruiz", "Anna", "Ruiz"))
    cache = InMemoryCache()
    splitter = NameSplitter(FakeProvider([bad, bad]), cache)
    outcome = await splitter.split(["Ana Ruiz"])
    assert outcome.result("Ana Ruiz", "first") == Err(
        "the model could not split this name faithfully"
    )
    assert outcome.stats.failed == 1
    assert await cache.get_many([splitter.cache_key("Ana Ruiz")]) == {}


async def test_answers_for_names_that_were_not_asked_are_ignored() -> None:
    llm = FakeProvider([answer(("Eva Sanz", "Eva", "Sanz")), answer(("Ana Ruiz", "Ana", "Ruiz"))])
    outcome = await NameSplitter(llm, InMemoryCache()).split(["Ana Ruiz"])
    assert "Eva Sanz" not in outcome.parts
    assert outcome.result("Ana Ruiz", "last") == Ok("Ruiz")


async def test_a_malformed_answer_is_retried() -> None:
    llm = FakeProvider([{"results": "nope"}, answer(("Ana Ruiz", "Ana", "Ruiz"))])
    outcome = await NameSplitter(llm, InMemoryCache()).split(["Ana Ruiz"])
    assert outcome.result("Ana Ruiz", "first") == Ok("Ana")


async def test_model_down_marks_the_batch_as_failed_without_retrying() -> None:
    llm = FakeProvider([LLMError("unavailable", "refused")])
    outcome = await NameSplitter(llm, InMemoryCache()).split(["Ana Ruiz", "Luis Gil"])
    assert outcome.result("Ana Ruiz", "first") == Err("model not available (unavailable)")
    assert outcome.stats.llm_calls == 1
    assert outcome.stats.failed == 2


async def test_cache_key_depends_on_the_model_and_the_value() -> None:
    cache = InMemoryCache()
    a = NameSplitter(FakeProvider(model="m1"), cache)
    b = NameSplitter(FakeProvider(model="m2"), cache)
    assert a.cache_key("Ana Ruiz") != b.cache_key("Ana Ruiz")
    assert a.cache_key("Ana Ruiz") != a.cache_key("Luis Gil")
    assert a.cache_key("Ana Ruiz").startswith("scm:")


async def test_nothing_to_split_makes_no_calls() -> None:
    outcome = await NameSplitter(FakeProvider(), InMemoryCache()).split(["", "  "])
    assert outcome.stats.llm_calls == 0
    assert outcome.result("", "first") == Ok("")
