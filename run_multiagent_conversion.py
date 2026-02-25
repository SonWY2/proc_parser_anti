#!/usr/bin/env python3
"""Run LangGraph-based Pro*C -> Java conversion pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from infra.agents.langchain.orchestration.conversion_graph import build_conversion_graph
from infra.agents.langchain.state import create_conversion_state


def _validate_inputs(header_paths: List[str], proc_paths: List[str]) -> None:
    missing = [p for p in [*header_paths, *proc_paths] if not Path(p).exists()]
    if missing:
        raise FileNotFoundError(f"입력 파일이 없습니다: {missing}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pro*C -> Java LangGraph conversion")
    parser.add_argument("--headers", required=True, help="comma-separated header paths")
    parser.add_argument("--procs", required=True, help="comma-separated proc paths")
    parser.add_argument("--output", default="output/", help="output directory")
    parser.add_argument("--knowledge", help="knowledge doc path")
    parser.add_argument("--strategy", choices=["preserve", "refactor"], default="preserve")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    header_paths = [p.strip() for p in args.headers.split(",") if p.strip()]
    proc_paths = [p.strip() for p in args.procs.split(",") if p.strip()]

    _validate_inputs(header_paths, proc_paths)

    graph = build_conversion_graph()
    initial_state = create_conversion_state(
        header_paths=header_paths,
        proc_paths=proc_paths,
        output_dir=args.output,
        strategy=args.strategy,
        knowledge_doc=args.knowledge,
    )

    result = graph.invoke(initial_state)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "conversion_result.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"report: {result.get('report_path', 'N/A')}")
    print(f"result json: {result_path}")

    errors = result.get("errors", [])
    if errors:
        for err in errors:
            print(f"WARN: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
