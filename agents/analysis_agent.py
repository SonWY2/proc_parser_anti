"""Analysis agent for Pro*C migration graph."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List

from parsing.header.integrated_parser import IntegratedHeaderParser
from parsing.core.core import ProCParser


_SQL_PATTERN = re.compile(r"EXEC\s+SQL[\s\S]*?;", re.IGNORECASE)
_FUNC_PATTERN = re.compile(
    r"^\s*([A-Za-z_]\w*[\s\*]+)+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{",
    re.MULTILINE,
)
_EXTERN_PATTERN = re.compile(r"\bextern\b\s+[^;]+\b([A-Za-z_]\w*)\s*;", re.IGNORECASE)


def _line_count(text: str) -> int:
    return text.count("\n") + 1 if text else 0


def _extract_sql_blocks(code: str, source_file: str) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    for idx, match in enumerate(_SQL_PATTERN.finditer(code), start=1):
        block = match.group(0)
        sql_type_match = re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|MERGE)\b", block, re.IGNORECASE)
        sql_type = sql_type_match.group(1).lower() if sql_type_match else "unknown"
        blocks.append(
            {
                "id": f"{Path(source_file).stem}_sql_{idx}",
                "name": f"{sql_type}_{idx}",
                "sql_type": sql_type,
                "sql": block.strip(),
                "source_file": source_file,
            }
        )
    return blocks


def _extract_functions(code: str) -> List[str]:
    return [m.group(2) for m in _FUNC_PATTERN.finditer(code)]


def _extract_externs(code: str) -> List[str]:
    return sorted(set(_EXTERN_PATTERN.findall(code)))


def _parse_headers(header_paths: List[str], proc_paths: List[str]) -> Dict[str, Any]:
    # 통합 파서를 우선 시도하고 실패하면 빈 맵으로 대체
    type_map: Dict[str, Any] = {}
    parser = IntegratedHeaderParser(include_paths=[str(Path(p).parent) for p in header_paths])

    for proc_path in proc_paths:
        try:
            result = parser.parse_program(proc_path)
            if result.db_vars_info:
                type_map.update(result.db_vars_info)
        except Exception:
            continue

    # 헤더 원문에서 typedef를 단순 추출해 fallback
    typedef_pattern = re.compile(r"typedef\s+.+?\s+([A-Za-z_]\w+)\s*;", re.MULTILINE)
    for header_path in header_paths:
        try:
            text = Path(header_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for alias in typedef_pattern.findall(text):
            type_map.setdefault(alias, {"source": header_path})

    return type_map


def run_analysis(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze headers/pro*c files and build normalized analysis payload."""
    header_paths = state.get("header_paths", [])
    proc_paths = state.get("proc_paths", [])

    errors: List[str] = []
    files: List[Dict[str, Any]] = []
    sql_blocks: List[Dict[str, Any]] = []
    extern_list: List[str] = []

    try:
        parser = ProCParser()
    except Exception:
        parser = None

    type_map = _parse_headers(header_paths, proc_paths)

    for proc_path in proc_paths:
        try:
            code = Path(proc_path).read_text(encoding="utf-8", errors="replace")
            loc = _line_count(code)
            functions = _extract_functions(code)
            externs = _extract_externs(code)
            file_sql_blocks = _extract_sql_blocks(code, proc_path)

            # 기존 파서 호출은 베스트 에포트(실패해도 fallback 유지)
            if parser is not None:
                try:
                    parser.parse_file(proc_path)
                except Exception:
                    pass

            files.append(
                {
                    "source_file": proc_path,
                    "loc": loc,
                    "chunked": loc > 5000,
                    "functions": functions,
                    "sql_count": len(file_sql_blocks),
                }
            )
            sql_blocks.extend(file_sql_blocks)
            extern_list.extend(externs)
        except Exception as exc:
            errors.append(f"analysis failed for {proc_path}: {exc}")

    extern_list = sorted(set(extern_list))
    analysis_result = {
        "type_map": type_map,
        "files": files,
        "sql_blocks": sql_blocks,
        "extern_list": extern_list,
        "stats": {
            "file_count": len(files),
            "total_loc": sum(file_info["loc"] for file_info in files),
            "sql_count": len(sql_blocks),
        },
    }

    return {
        "analysis_result": analysis_result,
        "errors": state.get("errors", []) + errors,
    }
