"""
공유 상태 정의

LangGraph StateGraph에서 사용하는 상태 타입들을 정의합니다.
"""
from typing import TypedDict, Annotated, Any, Optional
from operator import add


def add_messages(left: list, right: list) -> list:
    """메시지 리스트 병합 (LangGraph add_messages 호환)"""
    return left + right


class AgentState(TypedDict, total=False):
    """
    기본 에이전트 상태 (정적 워크플로우용)
    
    정적 워크플로우에서 에이전트 간 공유되는 상태입니다.
    """
    # 메시지 히스토리
    messages: Annotated[list, add_messages]
    
    # 중간 산출물 (FLOW.md, PARSED.md, SQL_MAP.md 등)
    artifacts: dict[str, str]
    
    # 현재 워크플로우 단계
    current_step: str
    
    # 변환 컨텍스트 (target_dir, output_dir 등)
    context: dict[str, Any]
    
    # 에러 목록
    errors: list[str]


class DynamicAgentState(TypedDict, total=False):
    """
    동적 오케스트레이션 상태 (Reflection + Self-Evolve용)
    
    동적 오케스트레이션에서 사용하는 확장 상태입니다.
    Planner, Router, Reflector 간 공유됩니다.
    """
    # 기본 필드 (AgentState 호환)
    messages: Annotated[list, add_messages]
    artifacts: dict[str, str]
    context: dict[str, Any]
    errors: list[str]
    
    # 동적 계획 수립
    current_plan: list[str]         # 현재 계획 (동적 생성/수정)
    executed_steps: list[str]       # 실행 완료된 단계
    
    # 에이전트 선택
    selected_agent: str             # 현재 선택된 에이전트
    
    # Reflection (자기 반성)
    reflections: list[str]          # 반성 기록
    quality_scores: list[float]     # 품질 점수 히스토리
    
    # Self-Evolve (자기 개선)
    pending_improvements: list[str] # 개선 필요 항목
    lessons_applied: list[str]      # 적용된 교훈
    
    # 반복 제어
    iteration_count: int            # 반복 횟수
    is_complete: bool               # 완료 여부
    
    # 최종 결과
    final_output: Optional[str]     # 최종 출력


class MigrationState(TypedDict, total=False):
    """
    Pro*C 마이그레이션 파이프라인 상태
    
    5개 Subagent가 데이터를 이어달리기하듯 처리하는 상태입니다.
    각 에이전트는 특정 필드를 읽고 특정 필드를 업데이트합니다.
    
    데이터 흐름:
        Parser → Critic → Draftsman → SQL Specialist → BXM Designer
    """
    # ===== 1. 초기 입력 =====
    filename: str                   # 원본 파일명
    source_code: str                # Pro*C 소스 코드
    
    # ===== 2. Parser Agent 산출물 =====
    ast_data: dict                  # {headers, host_vars, sql_blocks, functions}
    
    # ===== 3. Critic Agent 산출물 =====
    validation_errors: list[str]    # 검증 에러 목록 (비어있으면 통과)
    
    # ===== 4. Draftsman Agent 산출물 =====
    draft_xmls: list[dict]          # [{id, xml, confidence, original_sql}]
    
    # ===== 5. SQL Specialist Agent 산출물 =====
    refined_sqls: list[dict]        # [{id, final_xml, changes}]
    
    # ===== 6. BXM Designer Agent 산출물 =====
    java_code: str                  # 생성된 Java Service 코드
    mapper_xml: str                 # 생성된 MyBatis Mapper XML
    
    # ===== 제어 필드 =====
    current_agent: str              # 현재 실행 중인 에이전트
    is_complete: bool               # 파이프라인 완료 여부
    errors: list[str]               # 실행 중 발생한 에러


def create_migration_state(
    source_code: str,
    filename: str = "unknown.pc"
) -> dict:
    """
    마이그레이션 파이프라인 초기 상태 생성
    
    Args:
        source_code: Pro*C 소스 코드
        filename: 원본 파일명
        
    Returns:
        초기화된 MigrationState 딕셔너리
    """
    return {
        "filename": filename,
        "source_code": source_code,
        "ast_data": {},
        "validation_errors": [],
        "draft_xmls": [],
        "refined_sqls": [],
        "java_code": "",
        "mapper_xml": "",
        "current_agent": "",
        "is_complete": False,
        "errors": [],
    }


def create_initial_state(
    task: str,
    context: dict[str, Any] = None,
    mode: str = "dynamic"
) -> dict:
    """
    초기 상태 생성
    
    Args:
        task: 사용자 작업 요청
        context: 변환 컨텍스트 (target_dir 등)
        mode: "dynamic" 또는 "static"
    
    Returns:
        초기화된 상태 딕셔너리
    """
    base_state = {
        "messages": [{"role": "user", "content": task}],
        "artifacts": {},
        "context": context or {},
        "errors": [],
    }
    
    if mode == "dynamic":
        return {
            **base_state,
            "current_plan": [],
            "executed_steps": [],
            "selected_agent": "",
            "reflections": [],
            "quality_scores": [],
            "pending_improvements": [],
            "lessons_applied": [],
            "iteration_count": 0,
            "is_complete": False,
            "final_output": None,
        }
    else:
        return {
            **base_state,
            "current_step": "",
        }
