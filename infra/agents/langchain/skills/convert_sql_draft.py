"""
Convert SQL Draft Skill

SQL 블록을 MyBatis XML 형식으로 1차 변환합니다.
"""

from typing import Any, Dict, List, Optional
import logging

from .skill_interface import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class ConvertSqlDraftSkill(BaseSkill):
    """
    SQL 초안 변환 Skill
    
    MyBatisConverter를 래핑하여 Pro*C SQL을 MyBatis XML 형식으로 변환합니다.
    이 변환은 1차 초안이며, 후속 LLM 에이전트가 보정합니다.
    
    Input:
        sql_block: Dict - {id, content, sql_type, inputs, outputs}
        
    Output:
        {
            "id": str,
            "xml": str,
            "confidence": str  # "high", "medium", "low"
        }
    """
    
    def __init__(self):
        self._converter = None
    
    @property
    def name(self) -> str:
        return "convert_sql_draft"
    
    @property
    def description(self) -> str:
        return "Pro*C SQL을 MyBatis XML 형식으로 1차 변환"
    
    def _get_converter(self):
        """MyBatisConverter 지연 초기화"""
        if self._converter is None:
            try:
                from parsing.sql import MyBatisConverter
                self._converter = MyBatisConverter()
            except ImportError as e:
                logger.error(f"MyBatisConverter 임포트 실패: {e}")
                raise
        return self._converter
    
    def validate_input(self, input_data: Any) -> Optional[str]:
        if not isinstance(input_data, dict):
            return "입력은 딕셔너리여야 합니다"
        if "content" not in input_data and "sql" not in input_data:
            return "SQL content가 필요합니다"
        return None
    
    def invoke(self, input_data: Any) -> SkillResult:
        """
        SQL 초안 변환 실행
        
        Args:
            input_data: SQL 블록 딕셔너리
            
        Returns:
            SkillResult with converted MyBatis XML
        """
        error = self.validate_input(input_data)
        if error:
            return SkillResult(success=False, errors=[error])
        
        try:
            converter = self._get_converter()
            
            # 입력 정규화
            sql_id = input_data.get("id", "sql_0")
            sql_content = input_data.get("content") or input_data.get("sql", "")
            sql_type = input_data.get("sql_type", self._detect_sql_type(sql_content))
            input_vars = input_data.get("inputs", [])
            output_vars = input_data.get("outputs", [])
            
            # MyBatis 변환
            mybatis_result = converter.convert_sql(
                sql=sql_content,
                sql_type=sql_type,
                sql_id=sql_id,
                input_vars=input_vars,
                output_vars=output_vars,
            )
            
            # 변환 신뢰도 계산
            confidence = self._calculate_confidence(mybatis_result)
            
            result = {
                "id": sql_id,
                "xml": mybatis_result.sql,
                "mybatis_type": mybatis_result.mybatis_type,
                "original_sql": sql_content,
                "confidence": confidence,
                "input_params": mybatis_result.input_params,
                "output_fields": mybatis_result.output_fields,
            }
            
            return SkillResult(success=True, data=result)
            
        except Exception as e:
            logger.exception(f"SQL 변환 실패: {e}")
            return SkillResult(success=False, errors=[str(e)])
    
    def _detect_sql_type(self, sql: str) -> str:
        """SQL 타입 자동 감지"""
        sql_upper = sql.upper().strip()
        
        if sql_upper.startswith("SELECT"):
            return "select"
        elif sql_upper.startswith("INSERT"):
            return "insert"
        elif sql_upper.startswith("UPDATE"):
            return "update"
        elif sql_upper.startswith("DELETE"):
            return "delete"
        elif "DECLARE" in sql_upper and "CURSOR" in sql_upper:
            return "cursor_declare"
        elif sql_upper.startswith("OPEN"):
            return "cursor_open"
        elif sql_upper.startswith("FETCH"):
            return "cursor_fetch"
        elif sql_upper.startswith("CLOSE"):
            return "cursor_close"
        else:
            return "unknown"
    
    def _calculate_confidence(self, mybatis_result) -> str:
        """
        변환 신뢰도 계산
        
        - high: 단순 SELECT/INSERT/UPDATE/DELETE
        - medium: 커서 관련, 동적 SQL 포함
        - low: 변환 오류 가능성, 복잡한 구조
        """
        sql = mybatis_result.sql.upper()
        
        # 복잡한 구조 체크
        complex_patterns = [
            "DECODE",
            "NVL",
            "CASE WHEN",
            "CONNECT BY",
            "UNION ALL",
            "BULK COLLECT",
        ]
        
        has_complex = any(p in sql for p in complex_patterns)
        
        if has_complex:
            return "low"
        
        # 커서 관련 체크
        if "cursor" in mybatis_result.mybatis_type:
            return "medium"
        
        # 호스트 변수 변환 확인
        if ":(" in mybatis_result.sql or ":#" in mybatis_result.sql:
            # 변환되지 않은 호스트 변수가 있음
            return "low"
        
        return "high"
