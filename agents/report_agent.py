"""Migration report agent."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _ko_bool(value: Any) -> str:
    return "예" if bool(value) else "아니오"


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _one_col_table(header: str, items: list[str]) -> str:
    if not items:
        return f"| {header} |\n|---|\n| 없음 |"
    rows = "\n".join(f"| {_md_cell(item)} |" for item in items)
    return f"| {header} |\n|---|\n{rows}"


def _kv_table(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return "| 항목 | 값 |\n|---|---|\n| 없음 | 없음 |"
    body = "\n".join(f"| {_md_cell(key)} | {_md_cell(value)} |" for key, value in rows)
    return f"| 항목 | 값 |\n|---|---|\n{body}"


def _steps_table(steps: list[str]) -> str:
    if not steps:
        return "| 순번 | 단계 |\n|---:|---|\n| 1 | 없음 |"
    rows = "\n".join(
        f"| {idx} | {_md_cell(step)} |" for idx, step in enumerate(steps, start=1)
    )
    return f"| 순번 | 단계 |\n|---:|---|\n{rows}"


def _translate_line(text: str) -> str:
    mapping = {
        "llm validation skipped: langchain_openai not installed": "LLM 검증 건너뜀: langchain_openai 패키지가 설치되지 않았습니다",
        "llm validation enabled but no candidates": "LLM 검증 활성화 상태지만 검증 대상이 없습니다",
        "parser llm validation skipped: langchain_openai not installed": "파서 LLM 검증 건너뜀: langchain_openai 패키지가 설치되지 않았습니다",
        "parser llm validation disabled": "파서 LLM 검증 비활성화",
        "llm validation required but skipped (langchain_openai missing)": "LLM 검증이 필수인데 langchain_openai가 없어 건너뛰었습니다",
    }
    return mapping.get(text, text)


def run_report(state: Dict[str, Any]) -> Dict[str, Any]:
    analysis_result = state.get("analysis_result") or {}
    conversion_plan = state.get("conversion_plan") or {}
    planning_notes = state.get("planning_notes") or []
    java_result = state.get("java_result") or {}
    mybatis_result = state.get("mybatis_result") or {}
    ast_validation_result = state.get("ast_validation_result") or {}
    parser_validation_result = state.get("parser_validation_result") or {}
    validation_result = state.get("validation_result") or {}
    supplement_result = state.get("supplement_result") or {}
    validation_history = state.get("validation_history") or []
    errors: List[str] = state.get("errors", [])
    strategy = state.get("strategy", "preserve")

    output_dir = Path(state.get("output_dir", "output"))
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "migration-report.md"

    files = analysis_result.get("files", [])
    mappings = (
        "\n".join(
            f"| `{Path(item.get('source_file', '')).name}` | `{Path(item.get('source_file', '')).stem.title()}Service.java` |"
            for item in files
        )
        or "| - | - |"
    )

    plan_steps = [
        str(step) for step in conversion_plan.get("steps", []) if str(step).strip()
    ]
    planning_note_items = [str(item) for item in planning_notes if str(item).strip()]
    extern_items = [f"`{str(name)}`" for name in analysis_result.get("extern_list", [])]
    error_items = [str(err) for err in errors if str(err).strip()]

    summary_table = _kv_table(
        [
            ("Pro*C 파일 수", str(len(files))),
            ("SQL 블록 수", str(len(analysis_result.get("sql_blocks", [])))),
            ("생성된 Java 파일 수", str(len(java_result.get("java_files", [])))),
            ("생성된 XML 파일 수", str(len(mybatis_result.get("xml_files", [])))),
        ]
    )

    meta_table = _kv_table(
        [
            ("생성 시각", datetime.now().isoformat()),
            ("전략", str(strategy)),
            ("계획 모드", str(conversion_plan.get("mode", "N/A"))),
            ("검증 통과", _ko_bool(validation_result.get("passed", False))),
        ]
    )

    knowledge_summary = conversion_plan.get("knowledge", {})
    llm_validation = validation_result.get("llm", {})
    validation_warnings = [
        _translate_line(str(item)) for item in validation_result.get("warnings", [])
    ]
    validation_issues = [str(item) for item in validation_result.get("issues", [])]

    validation_summary = validation_result.get("summary", {})
    validation_summary_table = _kv_table(
        [
            ("예상 서비스 수", str(validation_summary.get("expected_services", 0))),
            ("생성 서비스 수", str(validation_summary.get("generated_services", 0))),
            ("예상 SQL 수", str(validation_summary.get("expected_sql", 0))),
            ("생성 XML 수", str(validation_summary.get("generated_xml", 0))),
        ]
    )

    llm_meta_table = _kv_table(
        [
            ("활성화", _ko_bool(llm_validation.get("enabled", False))),
            ("엄격 모드", _ko_bool(llm_validation.get("strict_mode", False))),
            ("시도 여부", _ko_bool(llm_validation.get("attempted", False))),
            ("성공 여부", _ko_bool(llm_validation.get("success", False))),
            ("후보 수", str(llm_validation.get("candidate_count", 0))),
            ("피드백 요약", str(llm_validation.get("feedback_summary", ""))),
        ]
    )

    parser_meta_table = _kv_table(
        [
            (
                "파서 LLM 활성화",
                _ko_bool(parser_validation_result.get("enabled", False)),
            ),
            (
                "파서 LLM 시도",
                _ko_bool(parser_validation_result.get("attempted", False)),
            ),
            ("파서 LLM 통과", _ko_bool(parser_validation_result.get("passed", True))),
            ("검증 청크 수", str(parser_validation_result.get("chunk_count", 0))),
            ("미분석 이슈 수", str(parser_validation_result.get("missing_count", 0))),
            ("오분석 이슈 수", str(parser_validation_result.get("wrong_count", 0))),
            (
                "재분류 제안 수",
                str(parser_validation_result.get("reclassification_count", 0)),
            ),
        ]
    )

    ast_meta_table = _kv_table(
        [
            ("AST 검증 통과", _ko_bool(ast_validation_result.get("passed", True))),
            ("AST 오류 수", str(ast_validation_result.get("error_count", 0))),
        ]
    )

    loop_meta_table = _kv_table(
        [
            (
                "현재 반복",
                str(validation_result.get("iteration", {}).get("current", 0)),
            ),
            ("최대 반복", str(validation_result.get("iteration", {}).get("max", 0))),
            ("보완 적용", _ko_bool(supplement_result.get("applied", False))),
            (
                "보완 시도 반복",
                str(
                    supplement_result.get(
                        "iteration",
                        validation_result.get("iteration", {}).get("current", 0),
                    )
                ),
            ),
            (
                "Java LLM 보완 적용 수",
                str(supplement_result.get("java_llm_gap_fill_applied", 0)),
            ),
        ]
    )

    validation_history_rows = [
        f"iter={item.get('iteration', 0)}, passed={item.get('passed', False)}, issues={item.get('issue_count', 0)}"
        for item in validation_history
    ]

    parser_issues = [
        _translate_line(str(item))
        for item in parser_validation_result.get("issues", [])
    ]
    parser_warnings = [
        _translate_line(str(item))
        for item in parser_validation_result.get("warnings", [])
    ]
    ast_issues = [str(item) for item in ast_validation_result.get("errors", [])]

    knowledge_table = _kv_table(
        [
            ("로드 여부", _ko_bool(knowledge_summary.get("loaded", False))),
            ("우선순위 항목 수", str(knowledge_summary.get("priority_count", 0))),
            ("금지 항목 수", str(knowledge_summary.get("forbidden_count", 0))),
            ("규칙 항목 수", str(knowledge_summary.get("rule_count", 0))),
        ]
    )

    java_files = java_result.get("java_files", [])
    stub_files = java_result.get("stub_files", [])
    dto_files = mybatis_result.get("dto_files", [])
    dao_files = mybatis_result.get("dao_files", [])
    xml_files = mybatis_result.get("xml_files", [])

    artifact_table = _kv_table(
        [
            (
                "Java 파일",
                f"{len(java_files)}개 / {'<br>'.join(f'`{_md_cell(path)}`' for path in java_files) or '없음'}",
            ),
            (
                "Stub 파일",
                f"{len(stub_files)}개 / {'<br>'.join(f'`{_md_cell(path)}`' for path in stub_files) or '없음'}",
            ),
            (
                "DTO 파일",
                f"{len(dto_files)}개 / {'<br>'.join(f'`{_md_cell(path)}`' for path in dto_files) or '없음'}",
            ),
            (
                "DAO 파일",
                f"{len(dao_files)}개 / {'<br>'.join(f'`{_md_cell(path)}`' for path in dao_files) or '없음'}",
            ),
            (
                "XML 파일",
                f"{len(xml_files)}개 / {'<br>'.join(f'`{_md_cell(path)}`' for path in xml_files) or '없음'}",
            ),
        ]
    )

    content = f"""# 마이그레이션 리포트

{meta_table}

## 요약
{summary_table}

## 전환 계획
{_steps_table(plan_steps)}

### 계획 메모
{_one_col_table("메모", planning_note_items)}

### 지식 문서 요약
{knowledge_table}

## 검증 결과
### 검증 요약
{validation_summary_table}

### 파서 검증 메타
{parser_meta_table}

### AST 검증 메타
{ast_meta_table}

### LLM 메타
{llm_meta_table}

### 보완 루프 메타
{loop_meta_table}

### 보완 루프 이력
{_one_col_table("이력", validation_history_rows)}

### 파서 검증 경고
{_one_col_table("파서 경고", parser_warnings)}

### 파서 검증 이슈
{_one_col_table("파서 이슈", parser_issues)}

### AST 검증 이슈
{_one_col_table("AST 이슈", ast_issues)}

### 경고
{_one_col_table("경고 내용", validation_warnings)}

### 이슈
{_one_col_table("이슈 내용", validation_issues)}

## Pro*C → Java 매핑
| Pro*C | Java 서비스 |
|---|---|
{mappings}

## Extern 스텁 TODO
{_one_col_table("스텁 대상", extern_items)}

## 생성 아티팩트
{artifact_table}

## 오류 및 경고
{_one_col_table("메시지", error_items)}
"""

    report_path.write_text(content, encoding="utf-8")
    return {"report_path": str(report_path)}
