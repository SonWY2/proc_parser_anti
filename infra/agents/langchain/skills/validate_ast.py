"""
Validate AST Skill

파싱된 AST 데이터의 무결성을 검증합니다.
"""

from typing import Any, Dict, List, Optional, Set
import logging

from .skill_interface import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class ValidateAstSkill(BaseSkill):
    """
    AST 검증 Skill
    
    파싱된 AST 데이터의 무결성을 검증합니다.
    - 필수 헤더 파일 확인
    - 미정의 변수 확인
    - SQL 블록 완전성 확인
    
    Input:
        ast_data: Dict - parse_proc_code의 출력
        
    Output:
        List[str] - 에러 목록 (빈 리스트면 성공)
    """
    
    # 기본 필수 헤더
    DEFAULT_REQUIRED_HEADERS: Set[str] = {
        "sqlca.h",  # SQL Communication Area
    }
    
    def __init__(self, required_headers: Set[str] = None):
        """
        Args:
            required_headers: 필수 헤더 파일 집합 (None이면 기본값 사용)
        """
        self._required_headers = required_headers or self.DEFAULT_REQUIRED_HEADERS
    
    @property
    def name(self) -> str:
        return "validate_ast"
    
    @property
    def description(self) -> str:
        return "AST 데이터의 무결성 검증 (필수 헤더, 미정의 변수 등)"
    
    def validate_input(self, input_data: Any) -> Optional[str]:
        if not isinstance(input_data, dict):
            return "입력은 딕셔너리여야 합니다"
        return None
    
    def invoke(self, input_data: Any) -> SkillResult:
        """
        AST 검증 실행
        
        Args:
            input_data: parse_proc_code의 출력 (ast_data 딕셔너리)
            
        Returns:
            SkillResult with validation errors list
        """
        error = self.validate_input(input_data)
        if error:
            return SkillResult(success=False, errors=[error])
        
        validation_errors: List[str] = []
        
        try:
            # 1. 필수 헤더 검증
            header_errors = self._validate_headers(input_data)
            validation_errors.extend(header_errors)
            
            # 2. SQL 블록 검증
            sql_errors = self._validate_sql_blocks(input_data)
            validation_errors.extend(sql_errors)
            
            # 3. 변수 참조 검증
            var_errors = self._validate_variable_references(input_data)
            validation_errors.extend(var_errors)
            
            # 4. 함수 검증
            func_errors = self._validate_functions(input_data)
            validation_errors.extend(func_errors)
            
            return SkillResult(
                success=len(validation_errors) == 0,
                data={"errors": validation_errors},
                errors=validation_errors,
            )
            
        except Exception as e:
            logger.exception(f"검증 실패: {e}")
            return SkillResult(success=False, errors=[str(e)])
    
    def _validate_headers(self, ast_data: Dict) -> List[str]:
        """필수 헤더 파일 검증"""
        errors = []
        headers = ast_data.get("headers", [])
        header_names = {h.get("name", "") for h in headers}
        
        for required in self._required_headers:
            if required not in header_names:
                errors.append(f"필수 헤더 누락: {required}")
        
        return errors
    
    def _validate_sql_blocks(self, ast_data: Dict) -> List[str]:
        """SQL 블록 검증"""
        errors = []
        sql_blocks = ast_data.get("sql_blocks", [])
        
        for i, block in enumerate(sql_blocks):
            block_id = block.get("id", f"sql_{i}")
            content = block.get("content", "")
            
            # 빈 SQL 체크
            if not content.strip():
                errors.append(f"빈 SQL 블록: {block_id}")
            
            # SQL 타입 체크
            sql_type = block.get("sql_type", "")
            if not sql_type:
                errors.append(f"SQL 타입 미정의: {block_id}")
        
        return errors
    
    def _validate_variable_references(self, ast_data: Dict) -> List[str]:
        """변수 참조 검증 (SQL에서 사용하는 변수가 선언되었는지)"""
        errors = []
        
        # 선언된 변수 목록
        declared_vars = {v.get("name", "") for v in ast_data.get("host_vars", [])}
        
        # SQL에서 사용하는 입출력 변수
        sql_blocks = ast_data.get("sql_blocks", [])
        
        for block in sql_blocks:
            block_id = block.get("id", "unknown")
            
            # 입력 변수 확인
            for var in block.get("inputs", []):
                var_name = var.lstrip(":") if isinstance(var, str) else var.get("name", "")
                if var_name and var_name not in declared_vars:
                    # 경고 수준 - 실제로는 매크로나 다른 곳에서 정의될 수 있음
                    logger.warning(f"미선언 입력 변수 가능성: {var_name} in {block_id}")
            
            # 출력 변수 확인
            for var in block.get("outputs", []):
                var_name = var.lstrip(":") if isinstance(var, str) else var.get("name", "")
                if var_name and var_name not in declared_vars:
                    logger.warning(f"미선언 출력 변수 가능성: {var_name} in {block_id}")
        
        return errors
    
    def _validate_functions(self, ast_data: Dict) -> List[str]:
        """함수 검증"""
        errors = []
        functions = ast_data.get("functions", [])
        
        # 함수 이름 중복 체크
        func_names = [f.get("name", "") for f in functions]
        seen = set()
        for name in func_names:
            if name in seen:
                errors.append(f"중복 함수 정의: {name}")
            seen.add(name)
        
        return errors
