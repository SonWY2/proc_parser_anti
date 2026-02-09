"""
LangGraph 기반 파싱 파이프라인

StateGraph를 사용하여 Orchestrator → Parser → Skill 체인을 구현합니다.
각 노드는 State를 통해 데이터를 주고받습니다.

실행:
    python infra/agents/langchain/tests/test_langgraph_chain.py
    python infra/agents/langchain/tests/test_langgraph_chain.py --source path/to/file.pc
    python infra/agents/langchain/tests/test_langgraph_chain.py --workspace ./my_workspace
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, TypedDict, Annotated
from operator import add

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LANGCHAIN_DIR = Path(__file__).resolve().parents[1]
if str(LANGCHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(LANGCHAIN_DIR))

from langgraph.graph import StateGraph, END
from workspace import AgentWorkspace

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(funcName)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


# ============================================================
# 상수 정의 (Magic Numbers 제거)
# ============================================================

class Config:
    """파이프라인 설정 상수"""
    
    # 타임아웃 (초)
    LLM_REQUEST_TIMEOUT = 360       # LLM API 요청 타임아웃
    THREADPOOL_TOTAL_TIMEOUT = 400  # ThreadPool 전체 작업 타임아웃
    FUTURE_RESULT_TIMEOUT = 10      # 개별 Future 결과 대기 타임아웃
    
    # 배치 처리 (청킹용 - 반복 처리를 위한 단위)
    BATCH_SIZE_ELEMENTS = 20        # 요소 배치 크기 (반복 처리)
    BATCH_SIZE_CODE_CHARS = 3000    # 코드 배치 크기 (chars, 반복 처리)
    
    # 로깅/표시 전용 (데이터 손실 없음)
    LOG_PREVIEW_LENGTH = 200        # 로그 출력 미리보기 길이
    PROMPT_PREVIEW_LENGTH = 100     # 프롬프트 미리보기 길이
    MESSAGE_PREVIEW_LENGTH = 50     # 메시지 미리보기 길이
    
    # 기본값
    DEFAULT_FUNC_LINE_RANGE = 50    # 함수 라인 범위 기본값
    DEFAULT_CONFIDENCE_BOOST = 0.75 # Fixer 후 신뢰도 향상값
    
    # 병렬 처리
    MAX_WORKERS = 3                 # ThreadPoolExecutor 워커 수
    
    # 출력 포맷
    SEPARATOR_WIDTH = 60            # 구분선 너비


# ============================================================
# 유틸리티: 청킹 함수
# ============================================================

def chunk_list(items: list, batch_size: int):
    """리스트를 배치 크기로 분할 (제너레이터)"""
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def chunk_text(text: str, batch_size: int):
    """텍스트를 배치 크기로 분할 (줄 단위 유지)"""
    lines = text.split('\n')
    current_chunk = []
    current_size = 0
    
    for line in lines:
        line_size = len(line) + 1  # +1 for newline
        if current_size + line_size > batch_size and current_chunk:
            yield '\n'.join(current_chunk)
            current_chunk = [line]
            current_size = line_size
        else:
            current_chunk.append(line)
            current_size += line_size
    
    if current_chunk:
        yield '\n'.join(current_chunk)


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
    extern_region: Dict  # {"code": str, "line_ranges": [...], "elements": {...}}
    parsed_functions: List[Dict]  # [{"name": str, "line_start": int, "line_end": int}]
    
    # SQL Agent 결과 (MyBatis XML)
    mybatis_xmls: List[Dict]  # [{sql_id, original, converted, confidence}]
    
    # Critic 검증 결과
    validation_passed: bool
    validation_errors: List[str]
    validation_warnings: List[str]
    
    # Fixer Agent 재시도 추적
    retry_count: int
    max_retries: int
    fixer_feedback: List[str]  # Fixer가 적용한 수정 내역
    
    # 흐름 제어
    current_node: str
    messages: Annotated[List[Dict], add]  # 메시지 누적
    errors: List[str]
    
    # 완료 여부
    is_complete: bool


def create_initial_state(
    source_code: str,
    filename: str = "input.pc",
    workspace_path: str = "./agent_workspace"
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
    }


# ============================================================
# 노드 함수들
# ============================================================

def orchestrator_receive_node(state: ParserPipelineState) -> Dict[str, Any]:
    """
    Orchestrator: 작업 수신 노드
    """
    logger.info("🎯 [Orchestrator] 작업 수신")
    
    workspace = AgentWorkspace(state["workspace_path"])
    
    # 소스 파일 저장
    source_path = workspace.save_source(state["filename"], state["source_code"])
    
    # 메시지 기록
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
    """
    Orchestrator: Parser에 작업 위임 노드
    """
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
    """
    Parser Agent: 파싱 수행 노드
    
    parsing.core.ProCParser를 사용하여 실제 파싱
    """
    logger.info("📝 [Parser] 파싱 시작")
    
    workspace = AgentWorkspace(state["workspace_path"])
    
    workspace.send_message(
        from_agent="Parser",
        to_agent="Skill:parse_proc_code",
        message_type="request",
        content={"source_code_length": len(state["source_code"])}
    )
    
    try:
        from parsing.core import ProCParser
        import tempfile
        
        parser = ProCParser()
        
        # 임시 파일로 파싱
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.pc', delete=False, encoding='utf-8'
        ) as f:
            f.write(state["source_code"])
            temp_path = f.name
        
        elements = parser.parse_file(temp_path)
        Path(temp_path).unlink()
        
        workspace.send_message(
            from_agent="Skill:parse_proc_code",
            to_agent="Parser",
            message_type="response",
            content={
                "status": "success",
                "element_count": len(elements)
            }
        )
        
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
        
        workspace.send_message(
            from_agent="Skill:parse_proc_code",
            to_agent="Parser",
            message_type="error",
            content={"error": str(e)}
        )
        
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
    """
    Parser Agent: 메타데이터 분류 노드
    """
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
    
    # 메타데이터 저장
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


# ============================================================
# Parser Critic Agent (asyncio 병렬 검증)
# ============================================================

def parser_critic_node(state: ParserPipelineState) -> Dict[str, Any]:
    """
    Parser Critic Agent: 파싱 결과 검증 (ThreadPool 병렬 처리)
    
    - 미분석 검증: 추출 안 된 요소 탐지
    - 오분석 검증: 잘못 추출된 결과 탐지
    - 타입 오분류 시 재분류 요청
    """
    logger.info("🔍 [Parser Critic] 파싱 결과 검증 시작")
    
    workspace = AgentWorkspace(state["workspace_path"])
    source_code = state.get("source_code", "")
    metadata = state.get("metadata", {})
    
    # State에서 tree-sitter 추출 결과 사용
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
    
    # 1. 청킹: State의 extern_region, parsed_functions 활용
    chunks = _split_by_scope_from_state(source_code, metadata, extern_region, parsed_functions)
    logger.info(f"🔍 [Parser Critic] {len(chunks)}개 청크로 분할")
    
    # 2. ThreadPool 병렬 검증
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    max_workers = 1
    results = _validate_all_chunks_threaded(chunks, workspace, max_workers)
    
    # 3. 결과 집계
    all_missing = []
    all_wrong = []
    all_reclassifications = []
    
    for result in results:
        all_missing.extend(result.get("missing_issues", []))
        all_wrong.extend(result.get("wrong_issues", []))
        all_reclassifications.extend(result.get("reclassifications", []))
    
    # 4. 검증 결과 저장
    validation_result = {
        "total_chunks": len(chunks),
        "missing_count": len(all_missing),
        "wrong_count": len(all_wrong),
        "reclassification_count": len(all_reclassifications),
        "missing_issues": all_missing,
        "wrong_issues": all_wrong,
        "reclassifications": all_reclassifications
    }
    
    workspace.save_data("parser_critic_result", validation_result, from_agent="Parser Critic")
    
    # 5. 타입 재분류 처리
    if all_reclassifications:
        updated_metadata = _handle_reclassifications(metadata, all_reclassifications)
        workspace.save_data("metadata_reclassified", updated_metadata, from_agent="Parser Critic")
        metadata = updated_metadata
    
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


def _split_by_scope_from_state(
    source_code: str, 
    metadata: Dict, 
    extern_region: Dict, 
    parsed_functions: List[Dict]
) -> List[Dict]:
    """
    State에서 미리 추출된 extern_region, parsed_functions를 활용한 청킹
    
    Args:
        source_code: 원본 소스 코드
        metadata: 분류된 메타데이터
        extern_region: tree-sitter로 추출된 extern 영역 (parser_classify_node에서)
        parsed_functions: tree-sitter로 추출된 함수 목록
    
    Returns:
        [{"scope": "extern"|"function_xxx", "code": "...", "elements": [...]}]
    """
    chunks = []
    
    # State에서 이미 추출된 데이터가 있으면 사용
    if extern_region.get("code") or parsed_functions:
        # extern 청크
        if extern_region.get("code"):
            extern_elements = extern_region.get("elements", {})
            all_extern_elements = []
            for category, items in extern_elements.items():
                if isinstance(items, list):
                    for item in items:
                        all_extern_elements.append({**item, "category": category})
            
            chunks.append({
                "scope": "extern",
                "code": extern_region["code"],
                "elements": all_extern_elements,
                "line_ranges": extern_region.get("line_ranges", [])
            })
        
        # 함수별 청크
        lines = source_code.split("\n")
        for func in parsed_functions:
            start_idx = max(0, func["line_start"] - 1)
            end_idx = min(len(lines), func["line_end"])
            func_code = "\n".join(lines[start_idx:end_idx])
            func_elements = _get_elements_in_range(metadata, func["line_start"], func["line_end"])
            
            chunks.append({
                "scope": f"function_{func['name']}",
                "code": func_code,
                "elements": func_elements,
                "line_range": (func["line_start"], func["line_end"])
            })
        
        logger.info(f"📦 [State] extern + {len(parsed_functions)}개 함수로 분할 (캐시 사용)")
        return chunks
    
    # State에 데이터가 없으면 fallback (tree-sitter 직접 호출)
    return _split_by_scope(source_code, metadata)


def _split_by_scope(source_code: str, metadata: Dict) -> List[Dict]:
    """
    소스 코드를 extern 영역과 함수 단위로 분할 (tree-sitter 사용)
    
    Returns:
        [{"scope": "extern"|"function_xxx", "code": "...", "elements": [...]}]
    """
    chunks = []
    
    # tree-sitter 사용 시도
    try:
        from parsing.sql.tree_sitter_extractor import get_tree_sitter_extractor
        extractor = get_tree_sitter_extractor()
        
        if extractor:
            # tree-sitter로 정확한 extern 영역 추출
            extern_data = extractor.get_extern_region(source_code)
            functions = extractor.get_functions(source_code)
            
            # extern 청크
            if extern_data.get("code"):
                extern_elements = extern_data.get("elements", {})
                all_extern_elements = []
                for category, items in extern_elements.items():
                    for item in items:
                        all_extern_elements.append({**item, "category": category})
                
                chunks.append({
                    "scope": "extern",
                    "code": extern_data["code"],
                    "elements": all_extern_elements,
                    "line_ranges": extern_data.get("line_ranges", [])
                })
            
            # 함수별 청크
            lines = source_code.split("\n")
            for func in functions:
                start_idx = max(0, func["line_start"] - 1)
                end_idx = min(len(lines), func["line_end"])
                func_code = "\n".join(lines[start_idx:end_idx])
                func_elements = _get_elements_in_range(metadata, func["line_start"], func["line_end"])
                
                chunks.append({
                    "scope": f"function_{func['name']}",
                    "code": func_code,
                    "elements": func_elements,
                    "line_range": (func["line_start"], func["line_end"])
                })
            
            logger.info(f"🌳 [tree-sitter] extern + {len(functions)}개 함수로 분할")
            return chunks
    
    except Exception as e:
        logger.warning(f"tree-sitter 분할 실패, 폴백 사용: {e}")
    
    # 폴백: metadata 기반 분할
    return _split_by_scope_fallback(source_code, metadata)


def _split_by_scope_fallback(source_code: str, metadata: Dict) -> List[Dict]:
    """tree-sitter 없을 때 폴백 분할"""
    chunks = []
    functions = metadata.get("functions", [])
    lines = source_code.split("\n")
    
    # 함수 위치 수집
    func_ranges = []
    covered_lines = set()
    
    for func in functions:
        start = func.get("line_start", 0)
        end = func.get("line_end", start + Config.DEFAULT_FUNC_LINE_RANGE)  # 기본 라인 범위
        func_ranges.append({"name": func.get("name", "unknown"), "start": start, "end": end})
        for i in range(start - 1, min(end, len(lines))):
            covered_lines.add(i)
    
    # extern 영역
    extern_lines = [(i + 1, line) for i, line in enumerate(lines) if i not in covered_lines]
    
    if extern_lines:
        extern_code = "\n".join([line for _, line in extern_lines])
        extern_elements = _get_elements_in_range(metadata, 0, max(i for i, _ in extern_lines) + 1)
        chunks.append({
            "scope": "extern",
            "code": extern_code,
            "elements": extern_elements,
            "line_range": (1, max(i for i, _ in extern_lines) + 1)
        })
    
    # 함수별 청크
    for fr in func_ranges:
        start_idx = max(0, fr["start"] - 1)
        end_idx = min(len(lines), fr["end"])
        func_code = "\n".join(lines[start_idx:end_idx])
        func_elements = _get_elements_in_range(metadata, fr["start"], fr["end"])
        
        chunks.append({
            "scope": f"function_{fr['name']}",
            "code": func_code,
            "elements": func_elements,
            "line_range": (fr["start"], fr["end"])
        })
    
    return chunks


def _get_elements_in_range(metadata: Dict, start: int, end: int) -> List[Dict]:
    """특정 라인 범위 내의 요소들 수집"""
    elements = []
    
    for category, items in metadata.items():
        if isinstance(items, list):
            for item in items:
                item_start = item.get("line_start", 0)
                item_end = item.get("line_end", item_start)
                if start <= item_start <= end or start <= item_end <= end:
                    elements.append({**item, "category": category})
    
    return elements


def _validate_all_chunks_threaded(chunks: List[Dict], workspace: 'AgentWorkspace', max_workers: int = 3) -> List[Dict]:
    """모든 청크 병렬 검증 (ThreadPoolExecutor)"""
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
    import signal
    
    results = []
    cancelled = False
    
    def signal_handler(signum, frame):
        nonlocal cancelled
        cancelled = True
        logger.warning("⚠️ Ctrl+C 감지, 작업 취소 중...")
        raise KeyboardInterrupt()
    
    # Windows에서는 SIGINT만 지원
    original_handler = signal.signal(signal.SIGINT, signal_handler)
    
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {
                executor.submit(_validate_chunk_sync, chunk, workspace): chunk
                for chunk in chunks
            }
            
            for future in as_completed(future_to_chunk, timeout=Config.THREADPOOL_TOTAL_TIMEOUT):
                if cancelled:
                    break
                    
                chunk = future_to_chunk[future]
                try:
                    result = future.result(timeout=Config.FUTURE_RESULT_TIMEOUT)
                    results.append(result)
                except FuturesTimeoutError:
                    logger.warning(f"⏰ 청크 {chunk['scope']} 결과 대기 타임아웃")
                    results.append({
                        "chunk_id": chunk["scope"],
                        "missing_issues": [],
                        "wrong_issues": [],
                        "reclassifications": [],
                        "error": "timeout"
                    })
                except Exception as e:
                    logger.error(f"청크 {chunk['scope']} 검증 실패: {e}")
                    results.append({
                        "chunk_id": chunk["scope"],
                        "missing_issues": [],
                        "wrong_issues": [],
                        "reclassifications": [],
                        "error": str(e)
                    })
    except KeyboardInterrupt:
        logger.warning("🛑 사용자가 작업을 취소했습니다")
    except FuturesTimeoutError:
        logger.error("⏰ 전체 작업 타임아웃")
    finally:
        signal.signal(signal.SIGINT, original_handler)
    
    return results


def _validate_chunk_sync(chunk: Dict, workspace: 'AgentWorkspace') -> Dict:
    """단일 청크 동기 검증 (requests 사용) - 배치 반복 처리"""
    import requests
    import os
    import json
    from dotenv import load_dotenv
    
    load_dotenv()
    
    endpoint = os.getenv("LLM_API_ENDPOINT")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "gpt-4")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    
    if not endpoint or not api_key:
        # LLM 설정 없으면 룰 기반 폴백
        return _rule_based_parser_validation(chunk)
    
    result = {
        "chunk_id": chunk["scope"],
        "missing_issues": [],
        "wrong_issues": [],
        "reclassifications": []
    }
    
    # 오분석 검증 (추출된 요소가 있는 경우만)
    elements = chunk.get("elements", [])
    if not elements:
        return result
    
    # 전체 코드는 그대로 전달 (함수 단위 청킹은 이미 되어 있음)
    code = chunk.get("code", "")
    
    # 요소가 많으면 배치 단위로 반복 처리
    all_wrong_issues = []
    all_reclassifications = []
    
    for batch_idx, element_batch in enumerate(chunk_list(elements, Config.BATCH_SIZE_ELEMENTS)):
        logger.info(f"📦 [{chunk['scope']}] 요소 배치 {batch_idx + 1} 검증 ({len(element_batch)}개)")
        
        wrong_prompt = _load_parser_critic_prompt("wrong")
        wrong_prompt = wrong_prompt.replace("{chunk_code}", code)
        wrong_prompt = wrong_prompt.replace("{extracted_json}", json.dumps(element_batch, ensure_ascii=False, indent=2))
        
        try:
            wrong_result = _call_llm_sync(endpoint, api_key, model, temperature, wrong_prompt)
            if wrong_result:
                all_wrong_issues.extend(wrong_result.get("issues", []))
                all_reclassifications.extend(wrong_result.get("reclassifications", []))
        except Exception as e:
            logger.warning(f"오분석 검증 실패 (배치 {batch_idx + 1}): {e}")
    
    result["wrong_issues"] = all_wrong_issues
    result["reclassifications"] = all_reclassifications
    
    logger.info(f"✅ [{chunk['scope']}] 총 {len(elements)}개 요소 검증 완료")
    return result


def _call_llm_sync(endpoint: str, api_key: str, model: str, temperature: float, prompt: str) -> Dict:
    """동기 LLM 호출 (requests)"""
    import requests
    import json
    import re
    import time
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature
    }
    
    prompt_preview = prompt[:Config.PROMPT_PREVIEW_LENGTH].replace('\n', ' ')
    logger.info(f"🌐 LLM 요청 시작 (모델: {model}, 프롬프트: {len(prompt)} chars) - {prompt_preview}...")
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{endpoint}/chat/completions",
            headers=headers,
            json=payload,
            timeout=Config.LLM_REQUEST_TIMEOUT
        )
        elapsed = time.time() - start_time
        logger.info(f"✅ LLM 응답 수신 ({elapsed:.1f}초, 상태: {response.status_code})")
        
        response.raise_for_status()
        result = response.json()
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        logger.error(f"⏰ LLM 타임아웃 ({elapsed:.1f}초 경과)")
        raise
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ LLM 요청 실패 ({elapsed:.1f}초): {e}")
        raise
    
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    logger.info(f"📝 LLM 응답 길이: {len(content)} chars")
    
    # JSON 파싱
    try:
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            content = json_match.group(1)
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"⚠️ JSON 파싱 실패, 원본: {content[:Config.LOG_PREVIEW_LENGTH]}...")
        return {}


def _load_parser_critic_prompt(prompt_type: str) -> str:
    """Parser Critic MD 파일에서 프롬프트 로드"""
    import re
    
    md_path = LANGCHAIN_DIR / "subagents" / "definitions" / "parser_critic_agent.md"
    
    if not md_path.exists():
        # 폴백 프롬프트
        if prompt_type == "missing":
            return "분석되지 않은 코드를 확인하세요.\n{remaining_code}"
        else:
            return "추출 결과를 검증하세요.\n원본:\n{chunk_code}\n추출:\n{extracted_json}"
    
    content = md_path.read_text(encoding="utf-8")
    
    # 해당 타입의 System Prompt 추출
    if prompt_type == "missing":
        pattern = r'## System Prompt - 미분석 검증\s+```\n?([\s\S]*?)```'
    else:  # wrong
        pattern = r'## System Prompt - 오분석 검증\s+```\n?([\s\S]*?)```'
    
    match = re.search(pattern, content)
    if match:
        return match.group(1).strip()
    
    return ""


def _rule_based_parser_validation(chunk: Dict) -> Dict:
    """룰 기반 파서 검증 (폴백)"""
    import re
    
    result = {
        "chunk_id": chunk["scope"],
        "missing_issues": [],
        "wrong_issues": [],
        "reclassifications": []
    }
    
    code = chunk.get("code", "")
    elements = chunk.get("elements", [])
    
    # 간단한 미분석 체크: EXEC SQL이 추출되지 않은 경우
    exec_sql_count = len(re.findall(r'EXEC\s+SQL', code, re.IGNORECASE))
    sql_elements = [e for e in elements if e.get("category") == "sql_blocks"]
    
    if exec_sql_count > len(sql_elements):
        result["missing_issues"].append({
            "type": "SQL",
            "content": f"EXEC SQL {exec_sql_count}개 중 {len(sql_elements)}개만 추출됨",
            "line": 0
        })
    
    return result


def _handle_reclassifications(metadata: Dict, reclassifications: List[Dict]) -> Dict:
    """타입 재분류 처리"""
    updated = {k: list(v) for k, v in metadata.items() if isinstance(v, list)}
    
    for reclass in reclassifications:
        element_id = reclass.get("element_id")
        from_type = reclass.get("from_type", "").lower()
        to_type = reclass.get("to_type", "").lower()
        
        # 타입 매핑
        type_to_key = {
            "sql": "sql_blocks",
            "variable": "host_vars",
            "function": "functions",
            "macro": "macros",
            "struct": "structs"
        }
        
        from_key = type_to_key.get(from_type)
        to_key = type_to_key.get(to_type)
        
        if not from_key or not to_key:
            continue
        
        # 해당 요소 찾기 및 이동
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
    """
    SQL Agent: SQL을 MyBatis XML 형식으로 변환
    
    parsing.sql.MyBatisConverter를 사용하여 Pro*C SQL을 
    MyBatis XML 형식으로 변환합니다.
    """
    logger.info("🗃️ [SQL Agent] MyBatis 변환 시작")
    
    workspace = AgentWorkspace(state["workspace_path"])
    metadata = state.get("metadata", {})
    sql_blocks = metadata.get("sql_blocks", [])
    
    if not sql_blocks:
        logger.info("🗃️ [SQL Agent] 변환할 SQL이 없음")
        workspace.send_message(
            from_agent="SQL Agent",
            to_agent="Critic",
            message_type="response",
            content={"status": "skip", "reason": "No SQL blocks"}
        )
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
    
    # MyBatis 변환 시도
    mybatis_results = []
    
    # Cursor 그룹 중 이미 처리된 relationship_id 추적
    processed_cursor_groups = set()
    
    try:
        from parsing.sql import MyBatisConverter
        converter = MyBatisConverter()
        
        for i, sql in enumerate(sql_blocks):
            # 변환용: normalized_sql, 저장용: raw_content
            sql_content = sql.get("normalized_sql") or sql.get("raw_content", "")
            raw_original = sql.get("raw_content", sql_content)  # original에는 raw_content 저장
            sql_id = sql.get("sql_id") or f"sql_{i+1}"
            sql_type = sql.get("sql_type", "unknown")
            cursor_name = sql.get("cursor_name", "not cursor")
            
            # Relationship 정보 확인 (Cursor 병합용)
            relationship = sql.get("relationship")
            
            # DECLARE SECTION은 변환 불필요
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
            
            # Cursor 관계가 있는 경우 병합 처리
            if relationship and relationship.get("relationship_type") == "CURSOR":
                rel_id = relationship.get("relationship_id")
                seq = relationship.get("sequence_in_group", 1)
                meta = relationship.get("metadata", {})
                cursor_name = meta.get("cursor_name", "unknown")
                
                # 첫 번째 요소 (DECLARE)만 변환, 나머지는 스킵
                if seq == 1:
                    # 이미 처리된 그룹이면 스킵
                    if rel_id in processed_cursor_groups:
                        continue
                    processed_cursor_groups.add(rel_id)
                    
                    # merged_sql을 사용하여 변환
                    merged_sql = meta.get("merged_sql", sql_content)
                    input_vars = meta.get("all_input_vars", [])
                    output_vars = meta.get("all_output_vars", [])
                    
                    # 원본 SQL들을 수집
                    original_sqls = [raw_original]
                    
                    logger.info(f"🗃️ [SQL Agent] Cursor '{cursor_name}' 병합 변환")
                    
                    try:
                        mybatis_sql = converter.convert_sql(
                            sql=merged_sql,
                            sql_type="select",  # Cursor는 SELECT
                            sql_id=f"cursor_{cursor_name}",
                            input_vars=input_vars,
                            output_vars=output_vars
                        )
                        
                        result = {
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
                        }
                    except Exception as e:
                        result = {
                            "sql_id": f"cursor_{cursor_name}",
                            "sql_type": "CURSOR",
                            "cursor_name": cursor_name,
                            "original": raw_original,
                            "merged_sql": merged_sql,
                            "converted": None,
                            "error": str(e),
                            "success": False
                        }
                    
                    mybatis_results.append(result)
                else:
                    # Cursor 그룹의 후속 요소들 (OPEN, FETCH, CLOSE)은 스킵
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
            
            # 입력/출력 호스트 변수
            input_vars = sql.get("input_host_vars", [])
            output_vars = sql.get("output_host_vars", [])
            
            try:
                # MyBatisConverter.convert_sql 사용
                mybatis_sql = converter.convert_sql(
                    sql=sql_content,
                    sql_type=sql_type.lower(),
                    sql_id=sql_id,
                    input_vars=input_vars,
                    output_vars=output_vars
                )
                
                result = {
                    "sql_id": sql_id,
                    "sql_type": sql_type,
                    "cursor_name": cursor_name if cursor_name != "not cursor" else None,
                    "original": raw_original,  # raw_content 저장
                    "converted": mybatis_sql.sql if mybatis_sql else None,
                    "mybatis_type": mybatis_sql.mybatis_type if mybatis_sql else None,
                    "input_params": mybatis_sql.input_params if mybatis_sql else [],
                    "output_fields": mybatis_sql.output_fields if mybatis_sql else [],
                    "confidence": 0.9,
                    "success": True
                }
            except Exception as e:
                result = {
                    "sql_id": sql_id,
                    "sql_type": sql_type,
                    "cursor_name": cursor_name if cursor_name != "not cursor" else None,
                    "original": raw_original,  # raw_content 저장
                    "converted": None,
                    "error": str(e),
                    "success": False
                }
            
            mybatis_results.append(result)
        
        workspace.send_message(
            from_agent="SQL Agent",
            to_agent="Critic",
            message_type="response",
            content={
                "status": "success",
                "converted_count": len([r for r in mybatis_results if r["success"]]),
                "failed_count": len([r for r in mybatis_results if not r["success"]]),
                "total": len(mybatis_results)
            }
        )
        
    except ImportError:
        # MyBatisConverter를 찾을 수 없는 경우 간단한 변환
        logger.warning("🗃️ [SQL Agent] MyBatisConverter 없음, 기본 변환 사용")
        
        for i, sql in enumerate(sql_blocks):
            sql_content = sql.get("content") or sql.get("raw", "")
            sql_id = sql.get("sql_id") or f"sql_{i+1}"
            sql_type = sql.get("sql_type", "unknown")
            
            # 간단한 호스트 변수 변환 (:var -> #{var})
            import re
            converted = re.sub(r':(\w+)', r'#{\\1}', sql_content)
            
            mybatis_results.append({
                "sql_id": sql_id,
                "sql_type": sql_type,
                "original": sql_content[:100],
                "converted": converted,
                "confidence": 0.5,
                "success": True,
                "note": "basic_conversion"
            })
        
        workspace.send_message(
            from_agent="SQL Agent",
            to_agent="Critic",
            message_type="response",
            content={
                "status": "basic_conversion",
                "converted_count": len(mybatis_results),
                "note": "MyBatisConverter not available"
            }
        )
    
    # 결과 저장
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
    """
    SQL Critic Agent: LLM 기반 MyBatis 변환 결과 검증
    
    LLM이 변환 결과를 직접 검토하고 구조화된 피드백을 제공합니다.
    .env의 LLM 설정을 사용합니다.
    """
    logger.info("🔍 [SQL Critic] LLM 기반 검증 시작")
    
    workspace = AgentWorkspace(state["workspace_path"])
    metadata = state.get("metadata", {})
    mybatis_xmls = state.get("mybatis_xmls", [])
    
    # 기본 검증 (LLM 호출 전 빠른 체크)
    validation_errors = []
    validation_warnings = []
    
    total_elements = sum(len(v) for v in metadata.values() if isinstance(v, list))
    sql_count = len(metadata.get("sql_blocks", []))
    func_count = len(metadata.get("functions", []))
    
    if total_elements == 0:
        validation_errors.append("파싱된 요소가 없습니다.")
    
    # MyBatis 변환 결과가 있으면 LLM으로 검토
    llm_feedback = None
    if mybatis_xmls:
        try:
            llm_feedback = _call_llm_critic(mybatis_xmls, workspace)
            
            if llm_feedback:
                if not llm_feedback.get("passed", True):
                    issues = llm_feedback.get("issues", [])
                    for issue in issues:
                        if issue.get("severity") == "error":
                            validation_errors.append(
                                f"[{issue.get('sql_id')}] {issue.get('issue')}"
                            )
                        else:
                            validation_warnings.append(
                                f"[{issue.get('sql_id')}] {issue.get('issue')}"
                            )
                logger.info(f"🔍 [SQL Critic] LLM 검토 완료: {llm_feedback.get('summary', 'N/A')}")
        except Exception as e:
            logger.warning(f"🔍 [SQL Critic] LLM 호출 실패, 룰 기반 검증으로 폴백: {e}")
            llm_feedback = None
            # 폴백: 기본 룰 기반 검증
            validation_errors, validation_warnings = _rule_based_validation(
                mybatis_xmls, metadata, validation_errors, validation_warnings
            )
    elif sql_count > 0:
        validation_warnings.append("SQL이 있지만 MyBatis 변환 결과가 없습니다.")
    
    # 검증 결과 판정
    validation_passed = len(validation_errors) == 0
    
    # Workspace에 저장
    validation_result = {
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
    }
    workspace.save_data("validation_result", validation_result, from_agent="SQL Critic")
    
    # 메시지 기록
    status = "PASSED" if validation_passed else "FAILED"
    workspace.send_message(
        from_agent="SQL Critic",
        to_agent="Fixer",
        message_type="response" if validation_passed else "error",
        content={
            "status": status,
            "errors": validation_errors,
            "warnings": validation_warnings,
            "llm_feedback": llm_feedback
        }
    )
    
    if validation_passed:
        logger.info(f"🔍 [SQL Critic] 검증 통과 ✓ (경고: {len(validation_warnings)}개)")
    else:
        logger.warning(f"🔍 [SQL Critic] 검증 실패 ✗ (에러: {len(validation_errors)}개)")
    
    return {
        "validation_passed": validation_passed,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "llm_feedback": llm_feedback,
        "current_node": "critic_validate",
        "messages": [{
            "from": "SQL Critic",
            "to": "Fixer",
            "type": "validation",
            "content": f"{status}: {len(validation_errors)} errors, {len(validation_warnings)} warnings"
        }]
    }


def _load_agent_prompt(agent_name: str) -> str:
    """
    서브에이전트 MD 파일에서 System Prompt 추출
    
    Args:
        agent_name: 에이전트 이름 (e.g., 'sql_critic_agent')
    
    Returns:
        System Prompt 문자열
    """
    import re
    
    # MD 파일 경로
    md_path = LANGCHAIN_DIR / "subagents" / "definitions" / f"{agent_name}.md"
    
    if not md_path.exists():
        raise FileNotFoundError(f"Agent MD 파일을 찾을 수 없습니다: {md_path}")
    
    content = md_path.read_text(encoding="utf-8")
    
    # ## System Prompt 섹션에서 ``` ``` 블록 추출
    # 패턴: ## System Prompt 다음의 첫 번째 코드 블록
    pattern = r'## System Prompt\s+```\n?([\s\S]*?)```'
    match = re.search(pattern, content)
    
    if match:
        prompt = match.group(1).strip()
        logger.info(f"📄 [Prompt Loader] {agent_name}에서 프롬프트 로드 ({len(prompt)} chars)")
        return prompt
    
    # 폴백: ## System Prompt 섹션의 전체 텍스트 (다음 ## 까지)
    fallback_pattern = r'## System Prompt\s+([\s\S]*?)(?=\n## |$)'
    fallback_match = re.search(fallback_pattern, content)
    
    if fallback_match:
        prompt = fallback_match.group(1).strip()
        logger.info(f"📄 [Prompt Loader] {agent_name}에서 프롬프트 로드 (폴백, {len(prompt)} chars)")
        return prompt
    
    raise ValueError(f"Agent MD 파일에서 System Prompt를 찾을 수 없습니다: {md_path}")


def _count_tokens(text: str, use_api: bool = False) -> int:
    """
    텍스트의 토큰 수 계산 (Mockup)
    
    Args:
        text: 토큰 수를 계산할 텍스트
        use_api: True면 /tokenize API 호출 (미구현), False면 근사치 사용
    
    Returns:
        추정 토큰 수
    
    Note:
        Mockup 구현: 텍스트 길이 / 4 (영어 기준 평균)
        한글의 경우 약 2~3 글자당 1토큰이지만, 보수적으로 길이/4 사용
    """
    if use_api:
        # TODO: /tokenize API 호출 구현
        # response = requests.post(f"{endpoint}/tokenizer", ...)
        pass
    
    # Mockup: 텍스트 길이 / 4 (근사치)
    return len(text) // 4


def _limit_by_tokens(candidates: List[Dict], max_tokens: int) -> tuple:
    """
    토큰 제한에 맞게 검토 대상 필터링
    
    Args:
        candidates: 검토 대상 SQL 목록
        max_tokens: 최대 허용 토큰 수
    
    Returns:
        (제한된 목록, 총 토큰 수)
    """
    import json
    
    result = []
    total_tokens = 0
    
    for item in candidates:
        item_json = json.dumps(item, ensure_ascii=False)
        item_tokens = _count_tokens(item_json)
        
        if total_tokens + item_tokens <= max_tokens:
            result.append(item)
            total_tokens += item_tokens
        else:
            # 토큰 제한 초과 시 중단
            logger.warning(f"📊 [Tokenizer] 토큰 제한 도달: {total_tokens}/{max_tokens}")
            break
    
    return result, total_tokens


def _call_llm_critic(mybatis_xmls: List[Dict], workspace: 'AgentWorkspace') -> Dict:
    """LLM을 호출하여 MyBatis 변환 결과 검토"""
    import os
    import json
    from dotenv import load_dotenv
    
    # .env 로드
    load_dotenv()
    
    endpoint = os.getenv("LLM_API_ENDPOINT")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "gpt-4")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    
    if not endpoint or not api_key:
        raise ValueError("LLM_API_ENDPOINT 또는 LLM_API_KEY가 설정되지 않았습니다.")
    
    # 검토 대상 준비 (변환 성공한 SQL만, DECLARE SECTION 제외)
    # SQL 절단 없이 전체 내용 포함 (검증 정확도를 위해)
    all_candidates = [
        {
            "sql_id": m.get("sql_id"),
            "sql_type": m.get("sql_type"),
            "original": m.get("original", ""),  # 전체 SQL 포함
            "converted": m.get("converted", "")  # 전체 변환 결과 포함
        }
        for m in mybatis_xmls
        if m.get("success") and m.get("converted")
        and m.get("note") != "skip_declare_section"
        and not str(m.get("note", "")).startswith("merged_into_cursor_")
    ]
    
    if not all_candidates:
        return {"passed": True, "issues": [], "summary": "검토 대상 SQL 없음"}
    
    # 배치 단위로 나눠서 처리 (SQL Critic도 모든 SQL을 반드시 검토)
    all_issues = []
    batch_size = Config.BATCH_SIZE_ELEMENTS
    
    for batch_idx, candidate_batch in enumerate(chunk_list(all_candidates, batch_size)):
        logger.info(f"🔍 [SQL Critic] 배치 {batch_idx + 1} 검토 ({len(candidate_batch)}개 SQL)")
        
        # MD 파일에서 System Prompt 로드
        system_prompt = _load_agent_prompt("sql_critic_agent")
        
        # {mybatis_xmls} 플레이스홀더 대체
        user_prompt = json.dumps(candidate_batch, ensure_ascii=False, indent=2)

        # HTTP 요청으로 LLM 호출
        import requests
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature
        }
        
        logger.info(f"🔍 [SQL Critic] LLM 호출: {model} (배치 {batch_idx + 1}, {len(candidate_batch)}개 SQL)")
        
        try:
            response = requests.post(
                f"{endpoint}/chat/completions",
                headers=headers,
                json=payload,
                timeout=Config.LLM_REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # JSON 파싱
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
            if json_match:
                content = json_match.group(1)
            
            llm_result = json.loads(content)
            batch_issues = llm_result.get("issues", [])
            all_issues.extend(batch_issues)
            logger.info(f"✅ [SQL Critic] 배치 {batch_idx + 1} 완료: {len(batch_issues)}개 이슈 발견")
            
        except json.JSONDecodeError as e:
            logger.warning(f"🔍 [SQL Critic] 배치 {batch_idx + 1} JSON 파싱 실패: {e}")
            continue
        except requests.exceptions.RequestException as e:
            logger.warning(f"🔍 [SQL Critic] 배치 {batch_idx + 1} 요청 실패: {e}")
            continue
    
    # 모든 배치 결과 집계
    final_result = {
        "passed": len(all_issues) == 0,
        "issues": all_issues,
        "summary": f"총 {len(all_candidates)}개 SQL 검토, {len(all_issues)}개 이슈 발견"
    }
    
    workspace.save_data("llm_critic_response", final_result, from_agent="SQL Critic")
    logger.info(f"✅ [SQL Critic] 전체 검토 완료: {final_result['summary']}")
    return final_result


def _rule_based_validation(
    mybatis_xmls: List[Dict], 
    metadata: Dict, 
    validation_errors: List[str], 
    validation_warnings: List[str]
) -> tuple:
    """폴백용 룰 기반 검증"""
    import re
    
    failed_conversions = [m for m in mybatis_xmls if not m.get("success")]
    if failed_conversions:
        validation_errors.append(f"MyBatis 변환 실패: {len(failed_conversions)}개 SQL")
    
    # 의심스러운 패턴 감지
    suspicious_patterns = [
        (r'@@\w+@@', 'Oracle 시스템 변수 오용'),
        (r'\$\$\w+\$\$', 'PostgreSQL 함수 구문 오류'),
    ]
    for m in mybatis_xmls:
        converted = m.get("converted", "") or ""
        original = m.get("original", "") or ""
        for pattern, reason in suspicious_patterns:
            if re.search(pattern, converted) or re.search(pattern, original):
                validation_errors.append(f"[{m.get('sql_id')}] {reason}")
                m["confidence"] = 0.5
                m["suspicious"] = True
                break
    
    return validation_errors, validation_warnings


def fixer_node(state: ParserPipelineState) -> Dict[str, Any]:
    """
    Fixer Agent: Critic 피드백 기반 수정
    
    Critic에서 발견된 오류를 분석하고 LLM을 사용하여
    메타데이터와 MyBatis 변환 결과를 보완합니다.
    
    수정 대상:
    1. 누락된 SQL 블록 보완
    2. 잘못된 MyBatis 변환 재시도
    3. 빈 필드 채우기
    """
    retry_count = state.get("retry_count", 0) + 1
    max_retries = state.get("max_retries", 3)
    
    logger.info(f"🔧 [Fixer] 수정 시작 (시도 {retry_count}/{max_retries})")
    
    workspace = AgentWorkspace(state["workspace_path"])
    validation_errors = state.get("validation_errors", [])
    validation_warnings = state.get("validation_warnings", [])
    
    # Critic으로부터 피드백 수신
    workspace.send_message(
        from_agent="Critic",
        to_agent="Fixer",
        message_type="request",
        content={
            "errors": validation_errors,
            "warnings": validation_warnings,
            "retry": retry_count
        }
    )
    
    fixer_feedback = []
    metadata = state.get("metadata", {})
    mybatis_xmls = state.get("mybatis_xmls", [])
    
    # =====================================
    # 수정 1: MyBatis 변환 실패 재시도
    # =====================================
    failed_mybatis = [m for m in mybatis_xmls if not m.get("success")]
    if failed_mybatis:
        logger.info(f"🔧 [Fixer] MyBatis 변환 실패 {len(failed_mybatis)}개 재시도")
        
        for m in failed_mybatis:
            sql_id = m.get("sql_id", "unknown")
            original = m.get("original", "")
            
            # 기본 변환 재시도 (LLM 없이)
            import re
            converted = re.sub(r':(\w+)', r'#{\\1}', original)
            
            # 결과 업데이트
            m["converted"] = converted
            m["success"] = True
            m["confidence"] = 0.6
            m["note"] = f"fixer_retry_{retry_count}"
            
            fixer_feedback.append(f"MyBatis 재변환: {sql_id}")
    
    # =====================================
    # 수정 2: 빈 SQL 내용 보완
    # =====================================
    sql_blocks = metadata.get("sql_blocks", [])
    for i, sql in enumerate(sql_blocks):
        if not sql.get("content") and not sql.get("raw"):
            # 원본 코드에서 SQL 추출 시도
            sql["content"] = f"-- SQL #{i+1} placeholder"
            sql["note"] = "fixer_added_placeholder"
            fixer_feedback.append(f"SQL #{i+1} 플레이스홀더 추가")
    
    # =====================================
    # 수정 3: 함수 이름 없는 경우 보완
    # =====================================
    functions = metadata.get("functions", [])
    for i, func in enumerate(functions):
        if not func.get("name"):
            func["name"] = f"unknown_function_{i+1}"
            func["note"] = "fixer_generated_name"
            fixer_feedback.append(f"함수 #{i+1} 이름 생성")
    
    # =====================================
    # 수정 4: 낮은 신뢰도 MyBatis 보완
    # =====================================
    low_confidence = [m for m in mybatis_xmls if m.get("confidence", 1.0) < 0.7]
    for m in low_confidence:
        # 신뢰도 향상 (실제로는 LLM으로 재처리)
        if m.get("success"):
            m["confidence"] = Config.DEFAULT_CONFIDENCE_BOOST  # 약간 향상
            m["note"] = f"confidence_boosted_retry_{retry_count}"
            fixer_feedback.append(f"신뢰도 향상: {m.get('sql_id')}")
    
    # =====================================
    # 수정 5: 의심스러운 SQL 패턴 수정
    # =====================================
    import re
    suspicious_items = [m for m in mybatis_xmls if m.get("suspicious")]
    for m in suspicious_items:
        original = m.get("original", "")
        converted = m.get("converted", "") or ""
        sql_id = m.get("sql_id", "unknown")
        
        # @@...@@ 패턴 제거 (Oracle 시스템 변수 오용)
        if re.search(r'@@\w+@@', original) or re.search(r'@@\w+@@', converted):
            # 패턴을 ? 플레이스홀더로 대체
            fixed_sql = re.sub(r'@@\w+@@', '?', converted)
            m["converted"] = fixed_sql
            m["confidence"] = 0.7
            m["note"] = f"suspicious_fixed_retry_{retry_count}"
            m["fix_applied"] = "removed_@@_pattern"
            fixer_feedback.append(f"의심 패턴 수정: {sql_id} (@@...@@ -> ?)")
            logger.info(f"🔧 [Fixer] {sql_id}: 의심 패턴 수정됨")
    
    # 결과 저장
    workspace.save_data("metadata_fixed", metadata, from_agent="Fixer")
    workspace.save_data("mybatis_fixed", mybatis_xmls, from_agent="Fixer")
    workspace.save_data("fixer_feedback", fixer_feedback, from_agent="Fixer")
    
    # 메시지 기록
    workspace.send_message(
        from_agent="Fixer",
        to_agent="Critic",
        message_type="response",
        content={
            "status": "fixed",
            "fixes_applied": len(fixer_feedback),
            "feedback": fixer_feedback,
            "retry_count": retry_count
        }
    )
    
    logger.info(f"🔧 [Fixer] 수정 완료: {len(fixer_feedback)}개 적용")
    
    return {
        "metadata": metadata,
        "mybatis_xmls": mybatis_xmls,
        "retry_count": retry_count,
        "fixer_feedback": fixer_feedback,
        "validation_passed": False,  # 다시 검증 필요
        "validation_errors": [],  # 리셋
        "validation_warnings": [],  # 리셋
        "current_node": "fixer",
        "messages": [{
            "from": "Fixer",
            "to": "Critic",
            "type": "data",
            "content": f"Applied {len(fixer_feedback)} fixes, retry {retry_count}"
        }]
    }


def check_validation(state: ParserPipelineState) -> str:
    """
    조건부 엣지: 검증 결과에 따라 분기
    
    Returns:
        "PASS": 검증 통과 → parser_respond로 진행
        "RETRY": 검증 실패 + 재시도 가능 → fixer로 이동
        "FAIL": 검증 실패 + 재시도 초과 → 완료로 이동
    """
    if state.get("validation_passed", False):
        return "PASS"
    
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if retry_count < max_retries:
        return "RETRY"
    
    return "FAIL"


def parser_respond_node(state: ParserPipelineState) -> Dict[str, Any]:
    """
    Parser Agent: 결과 반환 노드
    """
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
    """
    Orchestrator: 작업 완료 노드
    """
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
    
    # 대화 로그 저장
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
    workflow.add_node("parser_critic", parser_critic_node)  # Parser Critic 추가
    workflow.add_node("sql_convert", sql_convert_node)
    workflow.add_node("critic_validate", critic_validate_node)
    workflow.add_node("fixer", fixer_node)  # Fixer Agent 추가
    workflow.add_node("parser_respond", parser_respond_node)
    workflow.add_node("orch_complete", orchestrator_complete_node)
    
    # 엣지 연결
    workflow.add_edge("orch_receive", "orch_delegate")
    workflow.add_edge("orch_delegate", "parser_parse")
    workflow.add_edge("parser_parse", "parser_classify")
    workflow.add_edge("parser_classify", "parser_critic")  # Parser Critic 경유
    workflow.add_edge("parser_critic", "sql_convert")  # Critic 후 SQL 변환
    workflow.add_edge("sql_convert", "critic_validate")
    
    # 조건부 엣지: 검증 결과에 따라 분기
    workflow.add_conditional_edges(
        "critic_validate",
        check_validation,
        {
            "PASS": "parser_respond",    # 검증 통과 → 결과 반환
            "RETRY": "fixer",            # 검증 실패 + 재시도 가능 → Fixer
            "FAIL": "orch_complete",     # 검증 실패 + 재시도 초과 → 완료
        }
    )
    
    # Fixer → Critic 재검증 루프
    workflow.add_edge("fixer", "critic_validate")
    
    workflow.add_edge("parser_respond", "orch_complete")
    workflow.add_edge("orch_complete", END)
    
    # 시작점
    workflow.set_entry_point("orch_receive")
    
    return workflow.compile()


# ============================================================
# 메인 실행
# ============================================================

def run_pipeline(
    source_code: str,
    filename: str = "input.pc",
    workspace_path: str = "./agent_workspace"
) -> ParserPipelineState:
    """
    파이프라인 실행
    
    Args:
        source_code: Pro*C 소스 코드
        filename: 파일명
        workspace_path: 워크스페이스 경로
        
    Returns:
        최종 상태
    """
    # 그래프 생성
    graph = build_parser_pipeline()
    
    # 초기 상태
    initial_state = create_initial_state(source_code, filename, workspace_path)
    
    print(f"\n📂 Workspace: {Path(workspace_path).absolute()}")
    print("=" * Config.SEPARATOR_WIDTH)
    print("🚀 LangGraph 파이프라인 시작")
    print("=" * Config.SEPARATOR_WIDTH)
    
    # 실행
    final_state = graph.invoke(initial_state)
    
    return final_state


def print_result(state: ParserPipelineState):
    """결과 출력"""
    print("\n" + "=" * Config.SEPARATOR_WIDTH)
    print("📊 파이프라인 결과")
    print("=" * Config.SEPARATOR_WIDTH)
    
    # 메시지 흐름
    print("\n💬 메시지 흐름:")
    for i, msg in enumerate(state.get("messages", []), 1):
        print(f"  {i}. {msg['from']} → {msg['to']}: {msg['content'][:Config.MESSAGE_PREVIEW_LENGTH]}")
    
    # 메타데이터 요약
    metadata = state.get("metadata", {})
    if metadata:
        print("\n📦 추출된 메타데이터:")
        for key, items in metadata.items():
            if items:
                print(f"  - {key}: {len(items)}개")
    
    # Critic 검증 결과
    if state.get("validation_passed") is not None:
        status = "✓ 통과" if state["validation_passed"] else "✗ 실패"
        print(f"\n🔍 Critic 검증: {status}")
        
        for err in state.get("validation_errors", []):
            print(f"  ❌ {err}")
        for warn in state.get("validation_warnings", []):
            print(f"  ⚠️ {warn}")
    
    # 에러
    errors = state.get("errors", [])
    if errors:
        print("\n❌ 에러:")
        for e in errors:
            print(f"  - {e}")
    
    print("\n" + "=" * Config.SEPARATOR_WIDTH)
    
    if state.get("is_complete"):
        print("✅ 파이프라인 완료!")
    else:
        print("⚠️ 파이프라인 미완료")


def main():
    parser = argparse.ArgumentParser(description="LangGraph 파싱 파이프라인")
    parser.add_argument(
        "--source", "-s",
        help="Pro*C 소스 파일 경로"
    )
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
    
    args = parser.parse_args()
    
    # 워크스페이스 초기화
    if args.clean:
        ws = AgentWorkspace(args.workspace)
        ws.clear()
        print(f"🗑️ 워크스페이스 초기화: {args.workspace}")
    
    # 소스 코드 로드
    if args.source:
        source_path = Path(args.source)
        if not source_path.exists():
            print(f"❌ 파일을 찾을 수 없습니다: {source_path}")
            sys.exit(1)
        source_code = source_path.read_text(encoding="utf-8")
        filename = source_path.name
    else:
        # 기본 테스트 코드 (cursor 포함)
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

/* =========================================== */
/* 엣지 케이스: Fixer Agent 검증용             */
/* =========================================== */

/* 엣지 케이스 1: 비정상 SQL (변환 실패 유도) */
int test_malformed_sql() {
    EXEC SQL BEGIN DECLARE SECTION;
        int v_val;
    EXEC SQL END DECLARE SECTION;
    
    /* 의도적으로 잘못된 호스트 변수 형식 사용 */
    EXEC SQL SELECT @@INVALID@@SYNTAX@@ INTO :v_val FROM dual;
    
    return v_val;
}

/* 엣지 케이스 2: 복잡한 중첩 쿼리 (낮은 신뢰도 유도) */
int test_complex_query(int dept_id) {
    EXEC SQL BEGIN DECLARE SECTION;
        int total_count;
        char summary[200];
    EXEC SQL END DECLARE SECTION;
    
    EXEC SQL SELECT 
        (SELECT COUNT(*) FROM employees WHERE dept_id = :dept_id) +
        (SELECT COUNT(*) FROM contractors WHERE dept_id = :dept_id)
        INTO :total_count
        FROM dual;
    
    EXEC SQL SELECT 
        'Dept ' || TO_CHAR(:dept_id) || ' has ' || TO_CHAR(:total_count) || ' people'
        INTO :summary
        FROM dual;
    
    return total_count;
}
'''
        filename = "sample.pc"
    
    # 파이프라인 실행
    final_state = run_pipeline(source_code, filename, args.workspace)
    
    # 결과 출력
    print_result(final_state)
    
    # Workspace 정보
    workspace = AgentWorkspace(args.workspace)
    workspace.print_message_history()
    
    print(f"\n📁 생성된 파일:")
    for f in workspace.list_data_files():
        print(f"  - data/{f}")


if __name__ == "__main__":
    main()
