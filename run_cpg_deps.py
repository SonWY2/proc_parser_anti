#!/usr/bin/env python3
"""Hardcoded runner for CPG include dependency analysis.

This script intentionally does not accept command-line arguments.
Edit the HARDCODED_* constants below to change runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from analysis.cpg.header_analyzer import HeaderAnalyzer, IncludeInfo


BASE_DIR = Path(__file__).resolve().parent

HARDCODED_ROOT_DIR = BASE_DIR / "tests/fixtures/sample_input_data"
HARDCODED_SINGLE_PROGRAM = HARDCODED_ROOT_DIR / "original_source.sqc"
HARDCODED_INCLUDE_PATHS = [
    HARDCODED_ROOT_DIR,
    BASE_DIR / "tests/fixtures/samples",
    BASE_DIR,
]
HARDCODED_OUTPUT_DIR = BASE_DIR / "output/cpg_deps_hardcoded"

RUN_DIRECTORY_MODE = True
RUN_SINGLE_PROGRAM_MODE = True
MAX_DEPTH = 50

PROGRAM_EXTENSIONS = {".pc", ".sqc"}


@dataclass(frozen=True)
class EdgeRecord:
    source_file: Path
    header_name: str
    line_number: int
    is_system_header: bool
    is_sql_include: bool
    resolved_file: Path | None


def _resolve(path: Path) -> Path:
    return path.resolve()


def _norm_path(path: Path, root: Path) -> str:
    resolved = _resolve(path)
    try:
        return resolved.relative_to(_resolve(root)).as_posix()
    except ValueError:
        return resolved.as_posix()


def _collect_programs(root_dir: Path) -> list[Path]:
    root_abs = _resolve(root_dir)
    programs = [
        p
        for p in root_abs.rglob("*")
        if p.is_file() and p.suffix.lower() in PROGRAM_EXTENSIONS
    ]
    return sorted(
        programs,
        key=lambda p: (_norm_path(p, root_abs).casefold(), _norm_path(p, root_abs)),
    )


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _sorted_includes(includes: list[IncludeInfo]) -> list[IncludeInfo]:
    return sorted(
        includes,
        key=lambda inc: (
            inc.is_system_header,
            inc.header_name.casefold(),
            inc.header_name,
            inc.line_number,
        ),
    )


def _step_text(step: dict[str, str]) -> str:
    kind = step["kind"]
    if kind == "file":
        return step["path"]
    if step.get("is_system") == "true":
        return f"<{step['name']}>"
    return f'"{step["name"]}"'


def _chain_key(chain: dict[str, Any]) -> tuple[Any, ...]:
    steps = chain["steps"]
    rendered = " -> ".join(_step_text(step) for step in steps)
    return (len(steps), rendered.casefold(), rendered, chain["terminated_reason"])


def _analyze_program(
    program_path: Path, root_dir: Path, include_paths: list[Path]
) -> dict[str, Any]:
    program_abs = _resolve(program_path)
    root_abs = _resolve(root_dir)
    analyzer = HeaderAnalyzer(
        include_paths=[str(_resolve(p)) for p in include_paths], verbose=False
    )

    file_cache: dict[Path, list[IncludeInfo]] = {}
    visited_files: set[Path] = set()
    header_meta: dict[str, dict[str, Any]] = {}
    edges: list[EdgeRecord] = []
    chains: list[dict[str, Any]] = []

    def get_includes(file_path: Path) -> list[IncludeInfo]:
        if file_path in file_cache:
            return file_cache[file_path]
        try:
            source = _read_file(file_path)
        except OSError:
            file_cache[file_path] = []
            return file_cache[file_path]
        includes = _sorted_includes(analyzer.extract_includes(source, str(file_path)))
        file_cache[file_path] = includes
        return includes

    def walk(
        current_file: Path, steps: list[dict[str, str]], stack: set[Path], depth: int
    ) -> None:
        visited_files.add(current_file)
        includes = get_includes(current_file)

        for inc in includes:
            resolved_file: Path | None = None
            if not inc.is_system_header:
                resolved = analyzer.resolve_header_path(
                    inc.header_name, str(current_file.parent)
                )
                if resolved:
                    resolved_file = _resolve(Path(resolved))

            edges.append(
                EdgeRecord(
                    source_file=current_file,
                    header_name=inc.header_name,
                    line_number=inc.line_number,
                    is_system_header=inc.is_system_header,
                    is_sql_include=inc.is_sql_include,
                    resolved_file=resolved_file,
                )
            )

            meta = header_meta.setdefault(
                inc.header_name,
                {
                    "name": inc.header_name,
                    "is_system_header": inc.is_system_header,
                    "is_sql_include": inc.is_sql_include,
                    "resolved_files": set(),
                },
            )
            meta["is_system_header"] = bool(
                meta["is_system_header"] and inc.is_system_header
            )
            meta["is_sql_include"] = bool(meta["is_sql_include"] or inc.is_sql_include)
            if resolved_file is not None:
                meta["resolved_files"].add(resolved_file)

            new_steps = list(steps)
            new_steps.append(
                {
                    "kind": "header",
                    "name": inc.header_name,
                    "is_system": "true" if inc.is_system_header else "false",
                }
            )

            if inc.is_system_header:
                chains.append(
                    {"steps": new_steps, "terminated_reason": "system_header"}
                )
                continue

            if resolved_file is None:
                chains.append({"steps": new_steps, "terminated_reason": "unresolved"})
                continue

            new_steps.append(
                {"kind": "file", "path": _norm_path(resolved_file, root_abs)}
            )

            if depth + 1 > MAX_DEPTH:
                chains.append({"steps": new_steps, "terminated_reason": "max_depth"})
                continue

            if resolved_file in stack:
                chains.append({"steps": new_steps, "terminated_reason": "cycle"})
                continue

            walk(resolved_file, new_steps, stack | {resolved_file}, depth + 1)

    start_steps = [{"kind": "file", "path": _norm_path(program_abs, root_abs)}]
    walk(program_abs, start_steps, {program_abs}, depth=0)

    dedup_edge_keys: set[tuple[Any, ...]] = set()
    sorted_edges: list[dict[str, Any]] = []
    for edge in sorted(
        edges,
        key=lambda e: (
            _norm_path(e.source_file, root_abs).casefold(),
            _norm_path(e.source_file, root_abs),
            e.header_name.casefold(),
            e.header_name,
            e.line_number,
            e.is_system_header,
            e.is_sql_include,
            "" if e.resolved_file is None else _norm_path(e.resolved_file, root_abs),
        ),
    ):
        key = (
            _resolve(edge.source_file).as_posix(),
            edge.header_name,
            edge.line_number,
            edge.is_system_header,
            edge.is_sql_include,
            ""
            if edge.resolved_file is None
            else _resolve(edge.resolved_file).as_posix(),
        )
        if key in dedup_edge_keys:
            continue
        dedup_edge_keys.add(key)
        sorted_edges.append(
            {
                "source_file": _norm_path(edge.source_file, root_abs),
                "source_abs": _resolve(edge.source_file).as_posix(),
                "header": edge.header_name,
                "line": edge.line_number,
                "is_system_header": edge.is_system_header,
                "is_sql_include": edge.is_sql_include,
                "resolved_file": None
                if edge.resolved_file is None
                else _norm_path(edge.resolved_file, root_abs),
                "resolved_abs": None
                if edge.resolved_file is None
                else _resolve(edge.resolved_file).as_posix(),
            }
        )

    dedup_chains: dict[tuple[Any, ...], dict[str, Any]] = {}
    for chain in chains:
        chain_id = (
            tuple(
                (
                    step.get("kind", ""),
                    step.get("path", ""),
                    step.get("name", ""),
                    step.get("is_system", ""),
                )
                for step in chain["steps"]
            ),
            chain["terminated_reason"],
        )
        dedup_chains.setdefault(chain_id, chain)
    sorted_chains = sorted(dedup_chains.values(), key=_chain_key)

    file_nodes = sorted(
        visited_files,
        key=lambda p: (_norm_path(p, root_abs).casefold(), _norm_path(p, root_abs)),
    )
    header_nodes = sorted(
        header_meta.values(),
        key=lambda m: (str(m["name"]).casefold(), str(m["name"])),
    )

    nodes: list[dict[str, Any]] = []
    for file_node in file_nodes:
        nodes.append(
            {
                "id": f"file::{_resolve(file_node).as_posix()}",
                "kind": "file",
                "name": file_node.name,
                "path": _norm_path(file_node, root_abs),
                "abs_path": _resolve(file_node).as_posix(),
            }
        )
    for header in header_nodes:
        resolved_list = sorted(
            (_norm_path(path, root_abs) for path in header["resolved_files"]),
            key=lambda p: (p.casefold(), p),
        )
        resolved_abs = sorted(
            (_resolve(path).as_posix() for path in header["resolved_files"]),
            key=lambda p: (p.casefold(), p),
        )
        nodes.append(
            {
                "id": f"header::{header['name']}",
                "kind": "header",
                "name": header["name"],
                "is_system_header": bool(header["is_system_header"]),
                "is_sql_include": bool(header["is_sql_include"]),
                "resolved_files": resolved_list,
                "resolved_abs": resolved_abs,
            }
        )

    return {
        "program_path": _norm_path(program_abs, root_abs),
        "program_abs_path": program_abs.as_posix(),
        "stats": {
            "files": len(file_nodes),
            "headers": len(header_nodes),
            "include_edges": len(sorted_edges),
            "chains": len(sorted_chains),
        },
        "nodes": nodes,
        "edges": sorted_edges,
        "chains": sorted_chains,
    }


def _format_tree_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"root_dir: {report['root_dir']}")
    lines.append(f"program_count: {len(report['programs'])}")
    lines.append("")

    for index, program in enumerate(report["programs"], start=1):
        stats = program["stats"]
        lines.append(f"[{index}] program: {program['program_path']}")
        lines.append(
            "  stats: "
            f"files={stats['files']}, headers={stats['headers']}, "
            f"include_edges={stats['include_edges']}, chains={stats['chains']}"
        )

        if not program["chains"]:
            lines.append("  chains: (none)")
        else:
            lines.append("  chains:")
            for chain in program["chains"]:
                rendered = " -> ".join(_step_text(step) for step in chain["steps"])
                lines.append(f"    - {rendered} [{chain['terminated_reason']}]")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_visual_graph(
    report: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    node_map: dict[str, dict[str, str]] = {}
    edges: set[tuple[str, str, str, str]] = set()

    for program in report["programs"]:
        for node in program["nodes"]:
            if node["kind"] == "file":
                key = f"file::{node['abs_path']}"
                node_map[key] = {"key": key, "kind": "file", "label": node["path"]}
            else:
                key = f"header::{node['name']}"
                if node.get("is_system_header"):
                    label = f"<{node['name']}>"
                else:
                    label = node["name"]
                node_map[key] = {"key": key, "kind": "header", "label": label}

        for edge in program["edges"]:
            src_key = f"file::{edge['source_abs']}"
            header_key = f"header::{edge['header']}"
            include_label = f"include:{edge['line']}"
            style = "include"
            edges.add((src_key, header_key, include_label, style))

            if edge["resolved_abs"] is not None:
                resolved_key = f"file::{edge['resolved_abs']}"
                edges.add((header_key, resolved_key, "resolves", "resolve"))

    nodes = sorted(
        node_map.values(), key=lambda n: (n["kind"], n["label"].casefold(), n["label"])
    )
    edge_dicts = sorted(
        (
            {"src": src, "dst": dst, "label": label, "style": style}
            for src, dst, label, style in edges
        ),
        key=lambda e: (
            e["src"].casefold(),
            e["dst"].casefold(),
            e["label"].casefold(),
            e["style"],
        ),
    )
    return nodes, edge_dicts


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _to_dot(report: dict[str, Any], title: str) -> str:
    nodes, edges = _build_visual_graph(report)
    node_id_map = {node["key"]: f"n{idx}" for idx, node in enumerate(nodes, start=1)}

    lines = [f'digraph "{_dot_escape(title)}" {{']
    lines.append("  rankdir=LR;")
    lines.append("  node [fontsize=10];")

    for node in nodes:
        node_id = node_id_map[node["key"]]
        label = _dot_escape(node["label"])
        if node["kind"] == "file":
            style = "shape=folder,style=filled,fillcolor=lightgray"
        else:
            style = "shape=note,style=filled,fillcolor=wheat"
        lines.append(f'  {node_id} [label="{label}",{style}];')

    for edge in edges:
        src_id = node_id_map[edge["src"]]
        dst_id = node_id_map[edge["dst"]]
        label = _dot_escape(edge["label"])
        if edge["style"] == "include":
            style = "color=gray,style=dashed"
        else:
            style = "color=darkgreen,style=solid"
        lines.append(f'  {src_id} -> {dst_id} [label="{label}",{style}];')

    lines.append("}")
    return "\n".join(lines) + "\n"


def _to_mermaid(report: dict[str, Any]) -> str:
    nodes, edges = _build_visual_graph(report)
    node_id_map = {node["key"]: f"N{idx}" for idx, node in enumerate(nodes, start=1)}

    lines = ["flowchart LR"]
    for node in nodes:
        node_id = node_id_map[node["key"]]
        label = node["label"].replace('"', "'")
        if node["kind"] == "file":
            lines.append(f'  {node_id}["{label}"]')
        else:
            lines.append(f'  {node_id}{{"{label}"}}')

    for edge in edges:
        src_id = node_id_map[edge["src"]]
        dst_id = node_id_map[edge["dst"]]
        label = edge["label"].replace('"', "'")
        if edge["style"] == "include":
            lines.append(f"  {src_id} -. {label} .-> {dst_id}")
        else:
            lines.append(f"  {src_id} -- {label} --> {dst_id}")

    return "\n".join(lines) + "\n"


def main() -> int:
    root_dir = _resolve(HARDCODED_ROOT_DIR)
    include_paths = [_resolve(path) for path in HARDCODED_INCLUDE_PATHS]
    output_dir = _resolve(HARDCODED_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not root_dir.exists() or not root_dir.is_dir():
        print(f"ERROR: root directory not found: {root_dir}")
        return 1

    reports: list[dict[str, Any]] = []

    if RUN_DIRECTORY_MODE:
        programs = _collect_programs(root_dir)
        for program in programs:
            reports.append(_analyze_program(program, root_dir, include_paths))

    if RUN_SINGLE_PROGRAM_MODE:
        single_program = _resolve(HARDCODED_SINGLE_PROGRAM)
        if (
            single_program.exists()
            and single_program.suffix.lower() in PROGRAM_EXTENSIONS
        ):
            already_added = any(
                rep["program_abs_path"] == single_program.as_posix() for rep in reports
            )
            if not already_added:
                reports.append(
                    _analyze_program(single_program, root_dir, include_paths)
                )
        else:
            print(f"WARN: single program is invalid or missing: {single_program}")

    reports = sorted(
        reports, key=lambda rep: (rep["program_path"].casefold(), rep["program_path"])
    )

    report = {
        "schema_version": "cpg_deps_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root_dir": root_dir.as_posix(),
        "include_paths": [path.as_posix() for path in include_paths],
        "programs": reports,
    }

    json_path = output_dir / "dependency_report.json"
    txt_path = output_dir / "dependency_report.txt"
    dot_path = output_dir / "dependency_report.dot"
    mermaid_path = output_dir / "dependency_report.mmd"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    txt_path.write_text(_format_tree_report(report), encoding="utf-8")
    dot_path.write_text(
        _to_dot(report, title="CPG Include Dependency"), encoding="utf-8"
    )
    mermaid_path.write_text(_to_mermaid(report), encoding="utf-8")

    print(f"Report JSON: {json_path}")
    print(f"Report TXT : {txt_path}")
    print(f"Report DOT : {dot_path}")
    print(f"Report MMD : {mermaid_path}")
    print(
        "If Graphviz is installed: dot -Tpng dependency_report.dot -o dependency_report.png"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
