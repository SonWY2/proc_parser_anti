"""Migration report agent."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def run_report(state: Dict[str, Any]) -> Dict[str, Any]:
    analysis_result = state.get("analysis_result") or {}
    java_result = state.get("java_result") or {}
    mybatis_result = state.get("mybatis_result") or {}
    errors: List[str] = state.get("errors", [])
    strategy = state.get("strategy", "preserve")

    output_dir = Path(state.get("output_dir", "output"))
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "migration-report.md"

    files = analysis_result.get("files", [])
    mappings = "\n".join(
        f"| `{Path(item.get('source_file', '')).name}` | `{Path(item.get('source_file', '')).stem.title()}Service.java` |"
        for item in files
    ) or "| - | - |"

    extern_rows = "\n".join(f"- `{name}`" for name in analysis_result.get("extern_list", [])) or "- 없음"
    error_rows = "\n".join(f"- {err}" for err in errors) or "- 없음"

    content = f"""# Migration Report

- generated_at: {datetime.now().isoformat()}
- strategy: {strategy}

## Summary
- proc_files: {len(files)}
- sql_blocks: {len(analysis_result.get("sql_blocks", []))}
- generated_java: {len(java_result.get("java_files", []))}
- generated_xml: {len(mybatis_result.get("xml_files", []))}

## Pro*C → Java Mapping
| Pro*C | Java Service |
|---|---|
{mappings}

## Extern Stub TODO
{extern_rows}

## Generated Artifacts
- java_files: {java_result.get("java_files", [])}
- stub_files: {java_result.get("stub_files", [])}
- dto_files: {mybatis_result.get("dto_files", [])}
- dao_files: {mybatis_result.get("dao_files", [])}
- xml_files: {mybatis_result.get("xml_files", [])}

## Errors & Warnings
{error_rows}
"""

    report_path.write_text(content, encoding="utf-8")
    return {"report_path": str(report_path)}
