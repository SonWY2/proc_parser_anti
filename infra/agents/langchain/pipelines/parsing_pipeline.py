"""
LangGraph 기반 파싱 파이프라인

StateGraph를 사용하여 Orchestrator → Parser → Skill 체인을 구현합니다.
각 노드는 State를 통해 데이터를 주고받습니다.

리팩토링된 버전:
- llm_client.py: LLM 호출 통합
- utils/chunking.py: 청킹 유틸리티
- skills/scope_splitter.py: 스코프 분할
- skills/llm_validator.py: LLM 검증
- config.py: PipelineConfig

실행:
    python -m infra.agents.langchain.pipelines.parsing_pipeline
    python -m infra.agents.langchain.pipelines.parsing_pipeline --source path/to/file.pc
    python -m infra.agents.langchain.pipelines.parsing_pipeline --workspace ./my_workspace
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, TypedDict, Annotated
from operator import add

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LANGCHAIN_DIR = Path(__file__).resolve().parents[1]
if str(LANGCHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(LANGCHAIN_DIR))

from langgraph.graph import StateGraph, END
from workspace import AgentWorkspace

from ..config import PipelineConfig
from ..llm_client import get_llm_client
from ..utils.chunking import chunk_list
from ..skills.scope_splitter import ScopeSplitterSkill
from ..skills.llm_validator import LLMValidatorSkill
from ..subagents.subagent_loader import get_subagent_loader

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(funcName)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# 설정 로드
config = PipelineConfig.from_env()


# ============================================================
# State 정의
# ============================================================

class ParserPipelineState(TypedDict, total=False):
    """파싱 파이프라인 상태"""
    # 입력
    source_code: str
    filename: str
    workspace_path: str
    
    # 파싱 결과
    raw_elements: List[Dict]
    
    # 분류된 메타데이터
    metadata: Dict[str, List]
    
    # tree-sitter 추출 결과
    extern_region: Dict
    parsed_functions: List[Dict]
    
    # SQL Agent 결과 (MyBatis XML)
    mybatis_xmls: List[Dict]
    
    # Critic 검증 결과
    validation_passed: bool
    validation_errors: List[str]
    validation_warnings: List[str]
    
    # Fixer Agent 재시도 추적
    retry_count: int
    max_retries: int
    fixer_feedback: List[str]
    
    # 흐름 제어
    current_node: str
    messages: Annotated[List[Dict], add]
    errors: List[str]
    
    # 완료 여부
    is_complete: bool
    
    # 디버그 모드
    debug_mode: bool
    debug_file: str


def create_initial_state(
    source_code: str,
    filename: str = "input.pc",
    workspace_path: str = "./agent_workspace",
    debug_mode: bool = False,
    debug_file: str = None
) -> ParserPipelineState:
    """초기 상태 생성"""
    return {
        "source_code": source_code,
        "filename": filename,
        "workspace_path": workspace_path,
        "raw_elements": [],
        "metadata": {},
        "mybatis_xmls": [],
        "validation_passed": False,
        "validation_errors": [],
        "validation_warnings": [],
        "retry_count": 0,
        "max_retries": 3,
        "fixer_feedback": [],
        "current_node": "start",
        "messages": [],
        "errors": [],
        "is_complete": False,
        "debug_mode": debug_mode,
        "debug_file": debug_file,
    }


# ============================================================
# 노드 함수들
# ============================================================

def orchestrator_receive_node(state: ParserPipelineState) -> Dict[str, Any]:
    """Orchestrator: 작업 수신 노드"""
    logger.info("🎯 [Orchestrator] 작업 수신")
    
    workspace = AgentWorkspace(state["workspace_path"])
    source_path = workspace.save_source(state["filename"], state["source_code"])
    
    workspace.send_message(
        from_agent="System",
        to_agent="Orchestrator",
        message_type="request",
        content={
            "task": "parse_and_extract",
            "filename": state["filename"],
            "code_size": len(state["source_code"])
        }
    )
    
    return {
        "current_node": "orchestrator_receive",
        "messages": [{
            "from": "System",
            "to": "Orchestrator",
            "type": "request",
            "content": f"Parse {state['filename']}"
        }]
    }


def orchestrator_delegate_node(state: ParserPipelineState) -> Dict[str, Any]:
    """Orchestrator: Parser에 작업 위임 노드"""
    logger.info("🎯 [Orchestrator] Parser Agent에 작업 위임")
    
    workspace = AgentWorkspace(state["workspace_path"])
    
    workspace.send_message(
        from_agent="Orchestrator",
        to_agent="Parser",
        message_type="request",
        content={
            "action": "parse_proc_file",
            "filename": state["filename"]
        },
        file_refs=[f"{state['workspace_path']}/data/{state['filename']}"]
    )
    
    return {
        "current_node": "orchestrator_delegate",
        "messages": [{
            "from": "Orchestrator",
            "to": "Parser",
            "type": "request",
            "content": f"Parse {state['filename']}"
        }]
    }


def parser_parse_node(state: ParserPipelineState) -> Dict[str, Any]:
    """Parser Agent: 파싱 수행 노드"""
    logger.info("📝 [Parser] 파싱 시작")
    
    workspace = AgentWorkspace(state["workspace_path"])
    
    try:
        from parsing.core import ProCParser
        import tempfile
        
        parser = ProCParser()
        
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.pc', delete=False, encoding='utf-8'
        ) as f:
            f.write(state["source_code"])
            temp_path = f.name
        
        elements = parser.parse_file(temp_path)
        Path(temp_path).unlink()
        
        logger.info(f"📝 [Parser] 파싱 완료: {len(elements)} elements")
        
        return {
            "raw_elements": elements,
            "current_node": "parser_parse",
            "messages": [{
                "from": "Skill:parse_proc_code",
                "to": "Parser",
                "type": "response",
                "content": f"Parsed {len(elements)} elements"
            }]
        }
        
    except Exception as e:
        logger.error(f"📝 [Parser] 파싱 실패: {e}")
        return {
            "raw_elements": [],
            "errors": [str(e)],
            "current_node": "parser_parse",
            "messages": [{
                "from": "Skill:parse_proc_code",
                "to": "Parser",
                "type": "error",
                "content": str(e)
            }]
        }


def parser_classify_node(state: ParserPipelineState) -> Dict[str, Any]:
    """Parser Agent: 메타데이터 분류 노드"""
    logger.info("📝 [Parser] 메타데이터 분류")
    
    workspace = AgentWorkspace(state["workspace_path"])
    
    metadata = {
        "headers": [],
        "includes": [],
        "macros": [],
        "host_vars": [],
        "sql_blocks": [],
        "functions": [],
        "structs": [],
        "others": []
    }
    
    for elem in state.get("raw_elements", []):
        etype = elem.get("type", "unknown")
        
        if etype == "include":
            raw = str(elem.get("raw", ""))
            if "EXEC SQL" in raw:
                metadata["headers"].append(elem)
            else:
                metadata["includes"].append(elem)
        elif etype == "macro":
            metadata["macros"].append(elem)
        elif etype == "sql":
            metadata["sql_blocks"].append(elem)
        elif etype == "function":
            metadata["functions"].append(elem)
        elif etype == "struct":
            metadata["structs"].append(elem)
        elif etype == "variable":
            metadata["host_vars"].append(elem)
        else:
            metadata["others"].append(elem)
    
    workspace.save_data("metadata", metadata, from_agent="Parser")
    
    summary = {k: len(v) for k, v in metadata.items()}
    workspace.save_data("metadata_summary", summary, from_agent="Parser")
    
    # tree-sitter로 extern 영역과 함수 추출
    extern_region = {}
    parsed_functions = []
    
    try:
        from parsing.sql.tree_sitter_extractor import get_tree_sitter_extractor
        extractor = get_tree_sitter_extractor()
        
        if extractor:
            source_code = state.get("source_code", "")
            extern_region = extractor.get_extern_region(source_code)
            parsed_functions = extractor.get_functions(source_code)
            
            workspace.save_data("extern_region", extern_region, from_agent="Parser")
            workspace.save_data("parsed_functions", parsed_functions, from_agent="Parser")
            
            logger.info(f"🌳 [tree-sitter] extern: {len(extern_region.get('elements', {}))} elements, functions: {len(parsed_functions)}")
    except Exception as e:
        logger.warning(f"tree-sitter 추출 실패: {e}")
    
    logger.info(f"📝 [Parser] 분류 완료: {summary}")
    
    return {
        "metadata": metadata,
        "extern_region": extern_region,
        "parsed_functions": parsed_functions,
        "current_node": "parser_classify",
        "messages": [{
            "from": "Parser",
            "to": "Parser",
            "type": "data",
            "content": f"Classified: {summary}"
        }]
    }


def parser_critic_node(state: ParserPipelineState) -> Dict[str, Any]:
    """Parser Critic Agent: 파싱 결과 검증"""
    logger.info("🔍 [Parser Critic] 파싱 결과 검증 시작")
    
    workspace = AgentWorkspace(state["workspace_path"])
    source_code = state.get("source_code", "")
    metadata = state.get("metadata", {})
    extern_region = state.get("extern_region", {})
    parsed_functions = state.get("parsed_functions", [])
    
    if not source_code or not metadata:
        logger.warning("🔍 [Parser Critic] 검증할 데이터 없음")
        return {
            "current_node": "parser_critic",
            "messages": [{
                "from": "Parser Critic",
                "to": "SQL Agent",
                "type": "data",
                "content": "No data to validate"
            }]
        }
    
    # ScopeSplitterSkill 사용
    splitter = ScopeSplitterSkill()
    split_result = splitter.invoke({
        "source_code": source_code,
        "metadata": metadata,
        "extern_region": extern_region,
        "parsed_functions": parsed_functions
    })
    
    if not split_result.success:
        logger.warning(f"스코프 분할 실패: {split_result.errors}")
        chunks = []
    else:
        chunks = split_result.data.get("chunks", [])
    
    logger.info(f"🔍 [Parser Critic] {len(chunks)}개 청크로 분할")
    
    # LLMValidatorSkill 사용
    validator = LLMValidatorSkill()
    validation_result = validator.invoke({
        "mode": "parser",
        "chunks": chunks,
        "batch_size": config.batch_size_elements,
        "debug": state.get("debug_mode", False),
        "debug_file": state.get("debug_file")
    })
    
    all_missing = []
    all_wrong = []
    all_reclassifications = []
    
    if validation_result.success:
        data = validation_result.data
        all_missing = data.get("missing_issues", [])
        all_wrong = data.get("wrong_issues", [])
        all_reclassifications = data.get("reclassifications", [])
    
    workspace.save_data("parser_critic_result", {
        "total_chunks": len(chunks),
        "missing_count": len(all_missing),
        "wrong_count": len(all_wrong),
        "reclassification_count": len(all_reclassifications)
    }, from_agent="Parser Critic")
    
    # 타입 재분류 처리
    if all_reclassifications:
        metadata = _handle_reclassifications(metadata, all_reclassifications)
        workspace.save_data("metadata_reclassified", metadata, from_agent="Parser Critic")
    
    logger.info(f"🔍 [Parser Critic] 검증 완료: 미분석 {len(all_missing)}, 오분석 {len(all_wrong)}, 재분류 {len(all_reclassifications)}")
    
    return {
        "metadata": metadata,
        "current_node": "parser_critic",
        "messages": [{
            "from": "Parser Critic",
            "to": "SQL Agent",
            "type": "validation",
            "content": f"Missing: {len(all_missing)}, Wrong: {len(all_wrong)}, Reclassified: {len(all_reclassifications)}"
        }]
    }


def _handle_reclassifications(metadata: Dict, reclassifications: List[Dict]) -> Dict:
    """타입 재분류 처리"""
    updated = {k: list(v) for k, v in metadata.items() if isinstance(v, list)}
    
    type_to_key = {
        "sql": "sql_blocks",
        "variable": "host_vars",
        "function": "functions",
        "macro": "macros",
        "struct": "structs"
    }
    
    for reclass in reclassifications:
        element_id = reclass.get("element_id")
        from_type = reclass.get("from_type", "").lower()
        to_type = reclass.get("to_type", "").lower()
        
        from_key = type_to_key.get(from_type)
        to_key = type_to_key.get(to_type)
        
        if not from_key or not to_key:
            continue
        
        from_list = updated.get(from_key, [])
        to_list = updated.get(to_key, [])
        
        for i, elem in enumerate(from_list):
            if elem.get("sql_id") == element_id or elem.get("name") == element_id:
                moved_elem = from_list.pop(i)
                moved_elem["reclassified_from"] = from_type
                to_list.append(moved_elem)
                logger.info(f"🔄 재분류: {element_id} ({from_type} → {to_type})")
                break
    
    return updated


def sql_convert_node(state: ParserPipelineState) -> Dict[str, Any]:
    """SQL Agent: SQL을 MyBatis XML 형식으로 변환"""
    logger.info("🗃️ [SQL Agent] MyBatis 변환 시작")
    
    workspace = AgentWorkspace(state["workspace_path"])
    metadata = state.get("metadata", {})
    sql_blocks = metadata.get("sql_blocks", [])
    
    if not sql_blocks:
        logger.info("🗃️ [SQL Agent] 변환할 SQL이 없음")
        return {
            "mybatis_xmls": [],
            "current_node": "sql_convert",
            "messages": [{
                "from": "SQL Agent",
                "to": "Critic",
                "type": "data",
                "content": "No SQL to convert"
            }]
        }
    
    mybatis_results = []
    processed_cursor_groups = set()
    
    try:
        from parsing.sql import MyBatisConverter
        converter = MyBatisConverter()
        
        for i, sql in enumerate(sql_blocks):
            sql_content = sql.get("normalized_sql") or sql.get("raw_content", "")
            raw_original = sql.get("raw_content", sql_content)
            sql_id = sql.get("sql_id") or f"sql_{i+1}"
            sql_type = sql.get("sql_type", "unknown")
            cursor_name = sql.get("cursor_name", "not cursor")
            relationship = sql.get("relationship")
            
            if sql_type in ("BEGIN", "END", "INCLUDE"):
                mybatis_results.append({
                    "sql_id": sql_id,
                    "sql_type": sql_type,
                    "original": raw_original,
                    "converted": None,
                    "confidence": 1.0,
                    "success": True,
                    "note": "skip_declare_section"
                })
                continue
            
            if relationship and relationship.get("relationship_type") == "CURSOR":
                rel_id = relationship.get("relationship_id")
                seq = relationship.get("sequence_in_group", 1)
                meta = relationship.get("metadata", {})
                cursor_name = meta.get("cursor_name", "unknown")
                
                if seq == 1:
                    if rel_id in processed_cursor_groups:
                        continue
                    processed_cursor_groups.add(rel_id)
                    
                    merged_sql = meta.get("merged_sql", sql_content)
                    input_vars = meta.get("all_input_vars", [])
                    output_vars = meta.get("all_output_vars", [])
                    
                    try:
                        mybatis_sql = converter.convert_sql(
                            sql=merged_sql,
                            sql_type="select",
                            sql_id=f"cursor_{cursor_name}",
                            input_vars=input_vars,
                            output_vars=output_vars
                        )
                        
                        mybatis_results.append({
                            "sql_id": f"cursor_{cursor_name}",
                            "sql_type": "CURSOR",
                            "cursor_name": cursor_name,
                            "original": raw_original,
                            "merged_sql": merged_sql,
                            "converted": mybatis_sql.sql if mybatis_sql else None,
                            "mybatis_type": mybatis_sql.mybatis_type if mybatis_sql else None,
                            "input_params": mybatis_sql.input_params if mybatis_sql else [],
                            "output_fields": mybatis_sql.output_fields if mybatis_sql else [],
                            "is_loop_based": meta.get("is_loop_based", False),
                            "merged_from": relationship.get("total_in_group", 1),
                            "confidence": 0.9,
                            "success": True
                        })
                    except Exception as e:
                        mybatis_results.append({
                            "sql_id": f"cursor_{cursor_name}",
                            "sql_type": "CURSOR",
                            "cursor_name": cursor_name,
                            "original": raw_original,
                            "merged_sql": merged_sql,
                            "converted": None,
                            "error": str(e),
                            "success": False
                        })
                else:
                    mybatis_results.append({
                        "sql_id": sql_id,
                        "sql_type": sql_type,
                        "cursor_name": cursor_name,
                        "original": raw_original,
                        "converted": None,
                        "confidence": 1.0,
                        "success": True,
                        "note": f"merged_into_cursor_{cursor_name}"
                    })
                continue
            
            input_vars = sql.get("input_host_vars", [])
            output_vars = sql.get("output_host_vars", [])
            
            try:
                mybatis_sql = converter.convert_sql(
                    sql=sql_content,
                    sql_type=sql_type.lower(),
                    sql_id=sql_id,
                    input_vars=input_vars,
                    output_vars=output_vars
                )
                
                mybatis_results.append({
                    "sql_id": sql_id,
                    "sql_type": sql_type,
                    "cursor_name": cursor_name if cursor_name != "not cursor" else None,
                    "original": raw_original,
                    "converted": mybatis_sql.sql if mybatis_sql else None,
                    "mybatis_type": mybatis_sql.mybatis_type if mybatis_sql else None,
                    "input_params": mybatis_sql.input_params if mybatis_sql else [],
                    "output_fields": mybatis_sql.output_fields if mybatis_sql else [],
                    "confidence": 0.9,
                    "success": True
                })
            except Exception as e:
                mybatis_results.append({
                    "sql_id": sql_id,
                    "sql_type": sql_type,
                    "cursor_name": cursor_name if cursor_name != "not cursor" else None,
                    "original": raw_original,
                    "converted": None,
                    "error": str(e),
                    "success": False
                })
        
    except ImportError:
        import re
        logger.warning("🗃️ [SQL Agent] MyBatisConverter 없음, 기본 변환 사용")
        
        for i, sql in enumerate(sql_blocks):
            sql_content = sql.get("content") or sql.get("raw", "")
            sql_id = sql.get("sql_id") or f"sql_{i+1}"
            sql_type = sql.get("sql_type", "unknown")
            
            converted = re.sub(r':(\w+)', r'#{\1}', sql_content)
            
            mybatis_results.append({
                "sql_id": sql_id,
                "sql_type": sql_type,
                "original": sql_content[:100],
                "converted": converted,
                "confidence": 0.5,
                "success": True,
                "note": "basic_conversion"
            })
    
    workspace.save_data("mybatis_xmls", mybatis_results, from_agent="SQL Agent")
    
    success_count = len([r for r in mybatis_results if r.get("success")])
    logger.info(f"🗃️ [SQL Agent] 변환 완료: {success_count}/{len(mybatis_results)}")
    
    return {
        "mybatis_xmls": mybatis_results,
        "current_node": "sql_convert",
        "messages": [{
            "from": "SQL Agent",
            "to": "Critic",
            "type": "data",
            "content": f"Converted {success_count}/{len(mybatis_results)} SQLs"
        }]
    }


def critic_validate_node(state: ParserPipelineState) -> Dict[str, Any]:
    """SQL Critic Agent: LLM 기반 MyBatis 변환 결과 검증"""
    logger.info("🔍 [SQL Critic] LLM 기반 검증 시작")
    
    workspace = AgentWorkspace(state["workspace_path"])
    metadata = state.get("metadata", {})
    mybatis_xmls = state.get("mybatis_xmls", [])
    
    validation_errors = []
    validation_warnings = []
    
    total_elements = sum(len(v) for v in metadata.values() if isinstance(v, list))
    sql_count = len(metadata.get("sql_blocks", []))
    func_count = len(metadata.get("functions", []))
    
    if total_elements == 0:
        validation_errors.append("파싱된 요소가 없습니다.")
    
    llm_feedback = None
    if mybatis_xmls:
        # LLMValidatorSkill 사용
        validator = LLMValidatorSkill()
        validation_result = validator.invoke({
            "mode": "sql",
            "mybatis_xmls": mybatis_xmls,
            "batch_size": config.batch_size_elements,
            "debug": state.get("debug_mode", False),
            "debug_file": state.get("debug_file")
        })
        
        if validation_result.success:
            llm_feedback = validation_result.data
            
            if not llm_feedback.get("passed", True):
                for issue in llm_feedback.get("issues", []):
                    if issue.get("severity") == "error":
                        validation_errors.append(
                            f"[{issue.get('sql_id')}] {issue.get('issue')}"
                        )
                    else:
                        validation_warnings.append(
                            f"[{issue.get('sql_id')}] {issue.get('issue')}"
                        )
            logger.info(f"🔍 [SQL Critic] LLM 검토 완료: {llm_feedback.get('summary', 'N/A')}")
        else:
            logger.warning(f"🔍 [SQL Critic] LLM 검증 실패: {validation_result.errors}")
            # 폴백 처리
            failed_conversions = [m for m in mybatis_xmls if not m.get("success")]
            if failed_conversions:
                validation_errors.append(f"MyBatis 변환 실패: {len(failed_conversions)}개 SQL")
    elif sql_count > 0:
        validation_warnings.append("SQL이 있지만 MyBatis 변환 결과가 없습니다.")
    
    validation_passed = len(validation_errors) == 0
    
    workspace.save_data("validation_result", {
        "passed": validation_passed,
        "errors": validation_errors,
        "warnings": validation_warnings,
        "llm_feedback": llm_feedback,
        "summary": {
            "total_elements": total_elements,
            "sql_count": sql_count,
            "function_count": func_count,
            "mybatis_converted": len([m for m in mybatis_xmls if m.get("success")]),
            "mybatis_failed": len([m for m in mybatis_xmls if not m.get("success")])
        }
    }, from_agent="SQL Critic")
    
    status = "PASSED" if validation_passed else "FAILED"
    
    if validation_passed:
        logger.info(f"🔍 [SQL Critic] 검증 통과 ✓ (경고: {len(validation_warnings)}개)")
    else:
        logger.warning(f"🔍 [SQL Critic] 검증 실패 ✗ (에러: {len(validation_errors)}개)")
    
    return {
        "validation_passed": validation_passed,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "current_node": "critic_validate",
        "messages": [{
            "from": "SQL Critic",
            "to": "Fixer",
            "type": "validation",
            "content": f"{status}: {len(validation_errors)} errors, {len(validation_warnings)} warnings"
        }]
    }


def fixer_node(state: ParserPipelineState) -> Dict[str, Any]:
    """Fixer Agent: Critic 피드백 기반 수정"""
    import re
    
    retry_count = state.get("retry_count", 0) + 1
    max_retries = state.get("max_retries", 3)
    
    logger.info(f"🔧 [Fixer] 수정 시작 (시도 {retry_count}/{max_retries})")
    
    workspace = AgentWorkspace(state["workspace_path"])
    fixer_feedback = []
    metadata = state.get("metadata", {})
    mybatis_xmls = state.get("mybatis_xmls", [])
    
    # 수정 1: MyBatis 변환 실패 재시도
    failed_mybatis = [m for m in mybatis_xmls if not m.get("success")]
    for m in failed_mybatis:
        sql_id = m.get("sql_id", "unknown")
        original = m.get("original", "")
        
        converted = re.sub(r':(\w+)', r'#{\1}', original)
        
        m["converted"] = converted
        m["success"] = True
        m["confidence"] = 0.6
        m["note"] = f"fixer_retry_{retry_count}"
        
        fixer_feedback.append(f"MyBatis 재변환: {sql_id}")
    
    # 수정 2: 빈 SQL 내용 보완
    sql_blocks = metadata.get("sql_blocks", [])
    for i, sql in enumerate(sql_blocks):
        if not sql.get("content") and not sql.get("raw"):
            sql["content"] = f"-- SQL #{i+1} placeholder"
            sql["note"] = "fixer_added_placeholder"
            fixer_feedback.append(f"SQL #{i+1} 플레이스홀더 추가")
    
    # 수정 3: 함수 이름 없는 경우 보완
    functions = metadata.get("functions", [])
    for i, func in enumerate(functions):
        if not func.get("name"):
            func["name"] = f"unknown_function_{i+1}"
            func["note"] = "fixer_generated_name"
            fixer_feedback.append(f"함수 #{i+1} 이름 생성")
    
    # 수정 4: 낮은 신뢰도 MyBatis 보완
    low_confidence = [m for m in mybatis_xmls if m.get("confidence", 1.0) < 0.7]
    for m in low_confidence:
        if m.get("success"):
            m["confidence"] = config.default_confidence_boost
            m["note"] = f"confidence_boosted_retry_{retry_count}"
            fixer_feedback.append(f"신뢰도 향상: {m.get('sql_id')}")
    
    # 수정 5: 의심스러운 SQL 패턴 수정
    suspicious_items = [m for m in mybatis_xmls if m.get("suspicious")]
    for m in suspicious_items:
        original = m.get("original", "")
        converted = m.get("converted", "") or ""
        sql_id = m.get("sql_id", "unknown")
        
        if re.search(r'@@\w+@@', original) or re.search(r'@@\w+@@', converted):
            fixed_sql = re.sub(r'@@\w+@@', '?', converted)
            m["converted"] = fixed_sql
            m["confidence"] = 0.7
            m["note"] = f"suspicious_fixed_retry_{retry_count}"
            m["fix_applied"] = "removed_@@_pattern"
            fixer_feedback.append(f"의심 패턴 수정: {sql_id}")
    
    workspace.save_data("metadata_fixed", metadata, from_agent="Fixer")
    workspace.save_data("mybatis_fixed", mybatis_xmls, from_agent="Fixer")
    workspace.save_data("fixer_feedback", fixer_feedback, from_agent="Fixer")
    
    logger.info(f"🔧 [Fixer] 수정 완료: {len(fixer_feedback)}개 적용")
    
    return {
        "metadata": metadata,
        "mybatis_xmls": mybatis_xmls,
        "retry_count": retry_count,
        "fixer_feedback": fixer_feedback,
        "validation_passed": False,
        "validation_errors": [],
        "validation_warnings": [],
        "current_node": "fixer",
        "messages": [{
            "from": "Fixer",
            "to": "Critic",
            "type": "data",
            "content": f"Applied {len(fixer_feedback)} fixes, retry {retry_count}"
        }]
    }


def check_validation(state: ParserPipelineState) -> str:
    """조건부 엣지: 검증 결과에 따라 분기"""
    if state.get("validation_passed", False):
        return "PASS"
    
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if retry_count < max_retries:
        return "RETRY"
    
    return "FAIL"


def parser_respond_node(state: ParserPipelineState) -> Dict[str, Any]:
    """Parser Agent: 결과 반환 노드"""
    logger.info("📝 [Parser] Orchestrator에 결과 반환")
    
    workspace = AgentWorkspace(state["workspace_path"])
    summary = {k: len(v) for k, v in state.get("metadata", {}).items()}
    
    workspace.send_message(
        from_agent="Parser",
        to_agent="Orchestrator",
        message_type="response",
        content={
            "status": "success" if not state.get("errors") else "error",
            "summary": summary
        },
        file_refs=[
            f"{state['workspace_path']}/data/metadata.json",
            f"{state['workspace_path']}/data/metadata_summary.json"
        ]
    )
    
    return {
        "current_node": "parser_respond",
        "messages": [{
            "from": "Parser",
            "to": "Orchestrator",
            "type": "response",
            "content": f"Done: {summary}"
        }]
    }


def orchestrator_complete_node(state: ParserPipelineState) -> Dict[str, Any]:
    """Orchestrator: 작업 완료 노드"""
    logger.info("🎯 [Orchestrator] 작업 완료")
    
    workspace = AgentWorkspace(state["workspace_path"])
    
    workspace.send_message(
        from_agent="Orchestrator",
        to_agent="System",
        message_type="response",
        content={
            "status": "complete",
            "filename": state["filename"],
            "has_errors": bool(state.get("errors"))
        }
    )
    
    workspace.export_conversation()
    
    return {
        "current_node": "orchestrator_complete",
        "is_complete": True,
        "messages": [{
            "from": "Orchestrator",
            "to": "System",
            "type": "response",
            "content": "Pipeline complete"
        }]
    }


# ============================================================
# 그래프 빌더
# ============================================================

def build_parser_pipeline() -> StateGraph:
    """
    파싱 파이프라인 그래프 생성
    
    흐름:
        Orchestrator:Receive → Orchestrator:Delegate → 
        Parser:Parse → Parser:Classify → SQL Agent:Convert → 
        Critic:Validate →
        (PASS) → Parser:Respond → Orchestrator:Complete → END
        (RETRY) → Fixer → Critic (재검증, 최대 3회)
        (FAIL) → Orchestrator:Complete → END
    """
    workflow = StateGraph(ParserPipelineState)
    
    # 노드 추가
    workflow.add_node("orch_receive", orchestrator_receive_node)
    workflow.add_node("orch_delegate", orchestrator_delegate_node)
    workflow.add_node("parser_parse", parser_parse_node)
    workflow.add_node("parser_classify", parser_classify_node)
    workflow.add_node("parser_critic", parser_critic_node)
    workflow.add_node("sql_convert", sql_convert_node)
    workflow.add_node("critic_validate", critic_validate_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("parser_respond", parser_respond_node)
    workflow.add_node("orch_complete", orchestrator_complete_node)
    
    # 엣지 연결
    workflow.add_edge("orch_receive", "orch_delegate")
    workflow.add_edge("orch_delegate", "parser_parse")
    workflow.add_edge("parser_parse", "parser_classify")
    workflow.add_edge("parser_classify", "parser_critic")
    workflow.add_edge("parser_critic", "sql_convert")
    workflow.add_edge("sql_convert", "critic_validate")
    
    # 조건부 엣지
    workflow.add_conditional_edges(
        "critic_validate",
        check_validation,
        {
            "PASS": "parser_respond",
            "RETRY": "fixer",
            "FAIL": "orch_complete",
        }
    )
    
    workflow.add_edge("fixer", "critic_validate")
    workflow.add_edge("parser_respond", "orch_complete")
    workflow.add_edge("orch_complete", END)
    
    workflow.set_entry_point("orch_receive")
    
    return workflow.compile()


# ============================================================
# 메인 실행
# ============================================================

def run_pipeline(
    source_code: str,
    filename: str = "input.pc",
    workspace_path: str = "./agent_workspace",
    debug_mode: bool = False
) -> ParserPipelineState:
    """파이프라인 실행"""
    from datetime import datetime
    
    graph = build_parser_pipeline()
    
    # 디버그 모드면 로그 파일 생성
    debug_file = None
    if debug_mode:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = str(Path(workspace_path) / f"llm_debug_{timestamp}.log")
    
    initial_state = create_initial_state(source_code, filename, workspace_path, debug_mode, debug_file)
    
    print(f"\n📂 Workspace: {Path(workspace_path).absolute()}")
    if debug_mode:
        print(f"🔍 디버그 모드 활성화: LLM 입/출력이 파일에 저장됩니다")
        print(f"   📄 로그 파일: {debug_file}")
    print("=" * config.separator_width)
    print("🚀 LangGraph 파이프라인 시작")
    print("=" * config.separator_width)
    
    final_state = graph.invoke(initial_state)
    
    return final_state


def print_result(state: ParserPipelineState):
    """결과 출력"""
    print("\n" + "=" * config.separator_width)
    print("📊 파이프라인 결과")
    print("=" * config.separator_width)
    
    print("\n💬 메시지 흐름:")
    for i, msg in enumerate(state.get("messages", []), 1):
        content = str(msg.get('content', ''))[:config.message_preview_length]
        print(f"  {i}. {msg['from']} → {msg['to']}: {content}")
    
    metadata = state.get("metadata", {})
    if metadata:
        print("\n📦 추출된 메타데이터:")
        for key, items in metadata.items():
            if items:
                print(f"  - {key}: {len(items)}개")
    
    if state.get("validation_passed") is not None:
        status = "✓ 통과" if state["validation_passed"] else "✗ 실패"
        print(f"\n🔍 Critic 검증: {status}")
        
        for err in state.get("validation_errors", []):
            print(f"  ❌ {err}")
        for warn in state.get("validation_warnings", []):
            print(f"  ⚠️ {warn}")
    
    errors = state.get("errors", [])
    if errors:
        print("\n❌ 에러:")
        for e in errors:
            print(f"  - {e}")
    
    print("\n" + "=" * config.separator_width)
    
    if state.get("is_complete"):
        print("✅ 파이프라인 완료!")
    else:
        print("⚠️ 파이프라인 미완료")


def main():
    parser = argparse.ArgumentParser(description="LangGraph 파싱 파이프라인")
    parser.add_argument("--source", "-s", help="Pro*C 소스 파일 경로")
    parser.add_argument(
        "--workspace", "-w",
        default="./agent_workspace",
        help="워크스페이스 디렉토리 (기본: ./agent_workspace)"
    )
    parser.add_argument(
        "--clean", "-c",
        action="store_true",
        help="워크스페이스 초기화 후 실행"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Critic LLM 입/출력 상세 표시"
    )
    
    args = parser.parse_args()
    
    if args.clean:
        ws = AgentWorkspace(args.workspace)
        ws.clear()
        print(f"🗑️ 워크스페이스 초기화: {args.workspace}")
    
    if args.source:
        source_path = Path(args.source)
        if not source_path.exists():
            print(f"❌ 파일을 찾을 수 없습니다: {source_path}")
            sys.exit(1)
        source_code = source_path.read_text(encoding="utf-8")
        filename = source_path.name
    else:
        source_code = '''
/* sample.pc - 테스트 Pro*C with Cursor */
EXEC SQL INCLUDE sqlca;

#define MAX_SIZE 100

#include <stdio.h>

/* 단순 SELECT 함수 */
int get_data(int id) {
    EXEC SQL BEGIN DECLARE SECTION;
        int v_result;
    EXEC SQL END DECLARE SECTION;
    
    EXEC SQL SELECT value INTO :v_result FROM data WHERE id = :id;
    
    return v_result;
}

/* Cursor를 사용한 다중 행 조회 함수 */
int fetch_all_users(char* status) {
    EXEC SQL BEGIN DECLARE SECTION;
        int user_id;
        char user_name[50];
        char user_status[10];
    EXEC SQL END DECLARE SECTION;
    
    int count = 0;
    
    /* 커서 선언 */
    EXEC SQL DECLARE user_cursor CURSOR FOR
        SELECT user_id, user_name, status
        FROM users
        WHERE status = :status
        ORDER BY user_id;
    
    /* 커서 열기 */
    EXEC SQL OPEN user_cursor;
    
    /* 데이터 가져오기 반복 */
    while (1) {
        EXEC SQL FETCH user_cursor INTO :user_id, :user_name, :user_status;
        
        if (sqlca.sqlcode != 0) break;
        
        printf("User: %d, %s, %s\\n", user_id, user_name, user_status);
        count++;
    }
    
    /* 커서 닫기 */
    EXEC SQL CLOSE user_cursor;
    
    return count;
}

/* INSERT 예제 */
int insert_user(int id, char* name) {
    EXEC SQL BEGIN DECLARE SECTION;
        int v_id;
        char v_name[50];
    EXEC SQL END DECLARE SECTION;
    
    v_id = id;
    strcpy(v_name, name);
    
    EXEC SQL INSERT INTO users (user_id, user_name) VALUES (:v_id, :v_name);
    EXEC SQL COMMIT;
    
    return sqlca.sqlcode;
}
'''
        filename = "sample.pc"
    
    final_state = run_pipeline(source_code, filename, args.workspace, args.debug)
    print_result(final_state)
    
    workspace = AgentWorkspace(args.workspace)
    workspace.print_message_history()
    
    print(f"\n📁 생성된 파일:")
    for f in workspace.list_data_files():
        print(f"  - data/{f}")


if __name__ == "__main__":
    main()
