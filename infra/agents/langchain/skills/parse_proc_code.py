"""
Parse Pro*C Code Skill

ProCParser를 래핑하여 Pro*C 소스 코드를 파싱합니다.
"""

from typing import Any, Dict, List, Optional
import logging

from .skill_interface import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class ParseProcCodeSkill(BaseSkill):
    """
    Pro*C 코드 파싱 Skill
    
    ProCParser.parse_file()을 래핑하여 소스 코드에서 
    헤더, 호스트 변수, SQL 블록, 함수 정보를 추출합니다.
    
    Input:
        source_code: str - Pro*C 소스 코드 문자열
        
    Output:
        {
            "headers": [...],
            "host_vars": [...],
            "sql_blocks": [...],
            "functions": [...]
        }
    """
    
    def __init__(self):
        self._parser = None
    
    @property
    def name(self) -> str:
        return "parse_proc_code"
    
    @property
    def description(self) -> str:
        return "Pro*C 소스 코드를 파싱하여 구조화된 AST 데이터로 변환"
    
    def _get_parser(self):
        """Parser 지연 초기화"""
        if self._parser is None:
            try:
                from parsing.core import ProCParser
                self._parser = ProCParser()
            except ImportError as e:
                logger.error(f"ProCParser 임포트 실패: {e}")
                raise
        return self._parser
    
    def validate_input(self, input_data: Any) -> Optional[str]:
        if not isinstance(input_data, str):
            return "입력은 문자열이어야 합니다"
        if not input_data.strip():
            return "빈 소스 코드는 처리할 수 없습니다"
        return None
    
    def invoke(self, input_data: Any) -> SkillResult:
        """
        소스 코드 파싱 실행
        
        Args:
            input_data: Pro*C 소스 코드 문자열 또는 {"source_code": str, "file_path": str} 딕셔너리
            
        Returns:
            SkillResult with parsed AST data
        """
        # 입력 정규화
        if isinstance(input_data, dict):
            source_code = input_data.get("source_code", "")
            file_path = input_data.get("file_path")
        else:
            source_code = input_data
            file_path = None
        
        # 유효성 검사
        error = self.validate_input(source_code)
        if error:
            return SkillResult(success=False, errors=[error])
        
        try:
            parser = self._get_parser()
            
            # 파일 경로가 있으면 파일 파싱, 없으면 문자열에서 파싱
            if file_path:
                elements = parser.parse_file(file_path)
            else:
                # 임시 파일 생성 또는 문자열 직접 파싱
                elements = self._parse_from_string(parser, source_code)
            
            # 결과 구조화
            result = self._structure_elements(elements)
            
            return SkillResult(success=True, data=result)
            
        except Exception as e:
            logger.exception(f"파싱 실패: {e}")
            return SkillResult(success=False, errors=[str(e)])
    
    def _parse_from_string(self, parser, source_code: str) -> List[Dict]:
        """
        문자열에서 직접 파싱
        
        임시 파일을 생성하여 파싱합니다.
        """
        import tempfile
        import os
        
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.pc', 
            delete=False, 
            encoding='utf-8'
        ) as f:
            f.write(source_code)
            temp_path = f.name
        
        try:
            elements = parser.parse_file(temp_path)
            return elements
        finally:
            # 임시 파일 삭제
            os.unlink(temp_path)
    
    def _structure_elements(self, elements: List[Dict]) -> Dict[str, Any]:
        """
        파싱된 요소를 카테고리별로 구조화
        
        Args:
            elements: ProCParser에서 반환한 요소 리스트
            
        Returns:
            {headers, host_vars, sql_blocks, functions} 딕셔너리
        """
        result = {
            "headers": [],
            "host_vars": [],
            "sql_blocks": [],
            "functions": [],
            "macros": [],
            "structs": [],
        }
        
        for elem in elements:
            elem_type = elem.get("type", "")
            
            if elem_type == "include":
                result["headers"].append({
                    "name": elem.get("name", ""),
                    "path": elem.get("path", ""),
                    "is_system": elem.get("is_system", False),
                })
            
            elif elem_type == "variable":
                result["host_vars"].append({
                    "name": elem.get("name", ""),
                    "dtype": elem.get("dtype", ""),
                    "is_static": elem.get("is_static", False),
                    "function_name": elem.get("function_name"),
                })
            
            elif elem_type == "sql":
                result["sql_blocks"].append({
                    "id": elem.get("sql_id", elem.get("id", "")),
                    "content": elem.get("content", elem.get("raw", "")),
                    "sql_type": elem.get("sql_type", ""),
                    "inputs": elem.get("inputs", []),
                    "outputs": elem.get("outputs", []),
                    "function_name": elem.get("function_name"),
                })
            
            elif elem_type == "function":
                result["functions"].append({
                    "name": elem.get("name", ""),
                    "return_type": elem.get("return_type", ""),
                    "params": elem.get("params", []),
                    "start_line": elem.get("start_line"),
                    "end_line": elem.get("end_line"),
                })
            
            elif elem_type == "macro":
                result["macros"].append({
                    "name": elem.get("name", ""),
                    "value": elem.get("value", ""),
                })
            
            elif elem_type == "struct":
                result["structs"].append({
                    "name": elem.get("name", ""),
                    "fields": elem.get("fields", []),
                })
        
        return result
