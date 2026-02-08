"""
마이그레이션 그래프 빌더

5개 Subagent를 연결하는 StateGraph를 구성합니다.
Parser → Critic → Draftsman → SQL Specialist → BXM Designer
"""

from typing import Any, Dict, Optional
import logging

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel

from ..state import MigrationState, create_migration_state
from ..skills import get_tools_map, SkillsRegistry
from ..subagents import SubagentLoader

logger = logging.getLogger(__name__)


def parser_node(state: MigrationState) -> Dict[str, Any]:
    """
    Parser Agent 노드
    
    Pro*C 소스 코드를 파싱하여 AST 데이터를 생성합니다.
    """
    logger.info("🛠️ Parser Agent 실행...")
    
    try:
        tools_map = get_tools_map()
        skill = tools_map.get("parse_proc_code")
        
        if skill is None:
            return {
                "errors": ["parse_proc_code skill이 등록되지 않았습니다"],
                "current_agent": "parser_agent",
            }
        
        result = skill.invoke(state["source_code"])
        
        if not result.success:
            return {
                "errors": result.errors,
                "current_agent": "parser_agent",
            }
        
        return {
            "ast_data": result.data,
            "current_agent": "parser_agent",
        }
        
    except Exception as e:
        logger.exception(f"Parser 실행 실패: {e}")
        return {
            "errors": [str(e)],
            "current_agent": "parser_agent",
        }


def critic_node(state: MigrationState) -> Dict[str, Any]:
    """
    Critic Agent 노드
    
    AST 데이터의 무결성을 검증합니다.
    """
    logger.info("🔍 Critic Agent 실행...")
    
    try:
        tools_map = get_tools_map()
        skill = tools_map.get("validate_ast")
        
        if skill is None:
            # Skill이 없으면 검증 건너뛰기
            logger.warning("validate_ast skill이 없어서 검증 건너뜀")
            return {
                "validation_errors": [],
                "current_agent": "critic_agent",
            }
        
        result = skill.invoke(state["ast_data"])
        
        return {
            "validation_errors": result.errors if result.errors else [],
            "current_agent": "critic_agent",
        }
        
    except Exception as e:
        logger.exception(f"Critic 실행 실패: {e}")
        return {
            "validation_errors": [str(e)],
            "current_agent": "critic_agent",
        }


def draftsman_node(state: MigrationState) -> Dict[str, Any]:
    """
    Draftsman Agent 노드
    
    SQL 블록을 MyBatis XML로 1차 변환합니다.
    """
    logger.info("📝 Draftsman Agent 실행...")
    
    try:
        tools_map = get_tools_map()
        skill = tools_map.get("convert_sql_draft")
        
        if skill is None:
            return {
                "errors": ["convert_sql_draft skill이 등록되지 않았습니다"],
                "current_agent": "draftsman_agent",
            }
        
        ast_data = state.get("ast_data", {})
        sql_blocks = ast_data.get("sql_blocks", [])
        
        drafts = []
        for block in sql_blocks:
            result = skill.invoke(block)
            if result.success:
                drafts.append(result.data)
            else:
                logger.warning(f"SQL 변환 실패: {block.get('id')}: {result.errors}")
                drafts.append({
                    "id": block.get("id", "unknown"),
                    "xml": "",
                    "confidence": "failed",
                    "errors": result.errors,
                })
        
        return {
            "draft_xmls": drafts,
            "current_agent": "draftsman_agent",
        }
        
    except Exception as e:
        logger.exception(f"Draftsman 실행 실패: {e}")
        return {
            "errors": [str(e)],
            "current_agent": "draftsman_agent",
        }


def specialist_node(state: MigrationState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    SQL Specialist Agent 노드 (LLM 사용)
    
    Draft XML을 원본과 비교하여 보정합니다.
    """
    logger.info("🧠 SQL Specialist Agent 실행...")
    
    try:
        ast_data = state.get("ast_data", {})
        sql_blocks = ast_data.get("sql_blocks", [])
        draft_xmls = state.get("draft_xmls", [])
        
        refined = []
        
        for orig, draft in zip(sql_blocks, draft_xmls):
            # 신뢰도가 높으면 LLM 호출 생략
            if draft.get("confidence") == "high":
                refined.append({
                    "id": orig.get("id", "unknown"),
                    "final_xml": draft.get("xml", ""),
                    "changes": [],
                })
                continue
            
            # LLM으로 보정 요청
            prompt = f"""Pro*C SQL을 MyBatis XML로 변환한 결과를 검토하고 수정해주세요.

## 원본 Pro*C SQL
```sql
{orig.get('content', '')}
```

## 1차 변환 결과 (Python 생성)
```xml
{draft.get('xml', '')}
```

## 검토할 항목
1. 바인드 변수 매핑: :var → #{{var}} 올바르게 변환되었는가?
2. Oracle 특수 구문: DECODE, NVL 등이 처리되었는가?
3. 동적 쿼리: 조건부 WHERE가 <if> 태그로 변환되어야 하는가?

## 응답 형식
수정된 MyBatis XML만 반환하세요. 설명 없이 XML만 출력하세요.
"""
            
            try:
                response = llm.invoke(prompt)
                final_xml = response.content.strip()
                
                # XML 코드 블록 제거
                if final_xml.startswith("```"):
                    lines = final_xml.split("\n")
                    final_xml = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
                
                refined.append({
                    "id": orig.get("id", "unknown"),
                    "final_xml": final_xml,
                    "changes": ["LLM 보정 완료"],
                })
                
            except Exception as llm_error:
                logger.warning(f"LLM 호출 실패, 원본 사용: {llm_error}")
                refined.append({
                    "id": orig.get("id", "unknown"),
                    "final_xml": draft.get("xml", ""),
                    "changes": [],
                })
        
        return {
            "refined_sqls": refined,
            "current_agent": "sql_specialist_agent",
        }
        
    except Exception as e:
        logger.exception(f"SQL Specialist 실행 실패: {e}")
        return {
            "errors": [str(e)],
            "current_agent": "sql_specialist_agent",
        }


def designer_node(state: MigrationState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    BXM Designer Agent 노드 (LLM 사용)
    
    Java Service 코드와 Mapper XML을 생성합니다.
    """
    logger.info("🏗️ BXM Designer Agent 실행...")
    
    try:
        ast_data = state.get("ast_data", {})
        refined_sqls = state.get("refined_sqls", [])
        filename = state.get("filename", "unknown.pc")
        
        # 클래스 이름 생성 (order.pc → OrderService)
        base_name = filename.replace(".pc", "").replace(".sqc", "")
        class_name = "".join(word.capitalize() for word in base_name.split("_")) + "Service"
        
        # 함수 정보
        functions = ast_data.get("functions", [])
        
        # SQL 정보
        sql_info = "\n".join([
            f"- {sql.get('id')}: {sql.get('final_xml', '')[:100]}..."
            for sql in refined_sqls
        ])
        
        prompt = f"""Pro*C 파일을 BXM 표준에 맞는 Java Service 클래스로 변환해주세요.

## 파일 정보
- 원본 파일: {filename}
- 클래스명: {class_name}

## 함수 목록
{functions}

## SQL 매핑
{sql_info}

## BXM 표준 규칙
1. @BxmCategory 어노테이션 사용
2. BaseBxmService 상속
3. @Autowired로 Mapper 주입
4. try-catch로 BxmException 처리

## 응답 형식
다음 두 개의 코드 블록을 생성하세요:

### Java Service
```java
// OrderService.java
```

### Mapper XML
```xml
<!-- OrderMapper.xml -->
```
"""
        
        try:
            response = llm.invoke(prompt)
            content = response.content
            
            # Java 코드와 XML 분리
            java_code = ""
            mapper_xml = ""
            
            if "```java" in content:
                java_match = content.split("```java")[1].split("```")[0]
                java_code = java_match.strip()
            
            if "```xml" in content:
                xml_match = content.split("```xml")[1].split("```")[0]
                mapper_xml = xml_match.strip()
            
            return {
                "java_code": java_code,
                "mapper_xml": mapper_xml,
                "is_complete": True,
                "current_agent": "bxm_designer_agent",
            }
            
        except Exception as llm_error:
            logger.warning(f"LLM 호출 실패: {llm_error}")
            return {
                "errors": [str(llm_error)],
                "current_agent": "bxm_designer_agent",
            }
        
    except Exception as e:
        logger.exception(f"BXM Designer 실행 실패: {e}")
        return {
            "errors": [str(e)],
            "current_agent": "bxm_designer_agent",
        }


def check_validation(state: MigrationState) -> str:
    """
    검증 결과에 따라 분기
    
    Returns:
        "STOP": 검증 실패, 파이프라인 중단
        "CONTINUE": 검증 통과, 다음 단계로
    """
    errors = state.get("validation_errors", [])
    
    if errors:
        logger.warning(f"검증 실패, 파이프라인 중단: {errors}")
        return "STOP"
    
    return "CONTINUE"


def build_migration_graph(llm: BaseChatModel = None):
    """
    마이그레이션 파이프라인 그래프 빌드
    
    Args:
        llm: LLM 인스턴스 (SQL Specialist, BXM Designer에서 사용)
        
    Returns:
        컴파일된 StateGraph
    """
    workflow = StateGraph(MigrationState)
    
    # 노드 등록
    workflow.add_node("Parser", parser_node)
    workflow.add_node("Critic", critic_node)
    workflow.add_node("Draftsman", draftsman_node)
    workflow.add_node("Specialist", lambda s: specialist_node(s, llm) if llm else s)
    workflow.add_node("Designer", lambda s: designer_node(s, llm) if llm else s)
    
    # 엣지 연결
    workflow.add_edge("Parser", "Critic")
    
    # 조건부 엣지: 검증 결과에 따라 분기
    workflow.add_conditional_edges(
        "Critic",
        check_validation,
        {
            "STOP": END,
            "CONTINUE": "Draftsman",
        }
    )
    
    workflow.add_edge("Draftsman", "Specialist")
    workflow.add_edge("Specialist", "Designer")
    workflow.add_edge("Designer", END)
    
    # 시작점 설정
    workflow.set_entry_point("Parser")
    
    return workflow.compile()
