"""Run the evals against the configured model and write a Markdown report.

    make eval                                   # Ollama, default thresholds
    cd backend && uv run python ../evals/run.py --min-mapping 0.9

Exits with 1 when a metric is below its threshold, so CI can block the pull request.
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from smart_csv_mapper.config import Settings
from smart_csv_mapper.evaluation import (
    evaluate_mapping,
    evaluate_names,
    failures,
    load_mapping_cases,
    load_name_cases,
    render_markdown,
)
from smart_csv_mapper.llm.factory import build_provider
from smart_csv_mapper.mapping.prompt import PROMPT_VERSION

HERE = Path(__file__).parent


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-mapping", type=float, default=0.90)
    parser.add_argument("--min-names", type=float, default=0.90)
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args()

    llm = build_provider(Settings())
    mapping = await evaluate_mapping(load_mapping_cases(HERE / "datasets"), llm)
    names = await evaluate_names(load_name_cases(HERE / "name_split.jsonl"), llm)
    when = datetime.now(UTC).strftime("%Y-%m-%d")
    report = render_markdown(mapping, names, llm.model, when)
    args.out.mkdir(parents=True, exist_ok=True)
    model = llm.model.replace(":", "-").replace("/", "-")
    path = args.out / f"{when}-{model}-{PROMPT_VERSION}.md"
    path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Report written to {path}")
    problems = failures(mapping, names, args.min_mapping, args.min_names)
    for problem in problems:
        print(f"FAIL: {problem}", file=sys.stderr)
    return int(bool(problems))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
