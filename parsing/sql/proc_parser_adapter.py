"""
proc_parser 호환 SQL 어댑터 모듈

sql_extractor의 기능을 proc_parser 형식으로 변환하는 어댑터를 제공합니다.
"""

import re
import logging
from typing import List, Dict, Any, Optional

from .config import SQLExtractorConfig
from .tree_sitter_extractor import TreeSitterSQLExtractor, SQLBlock
from .pyparsing_parser import PyparsingProCParser
from .types import ExtractedSQL

logger = logging.getLogger(__name__)


class ProcParserSQLAdapter:
    """
    sql_extractor를 proc_parser 형식으로 변환하는 어댑터
    
    sql_extractor의 TreeSitterSQLExtractor와 PyparsingProCParser를 사용하여
    SQL을 추출하고, proc_parser.core가 사용하는 딕셔너리 형식으로 변환합니다.
    
    주요 기능:
    - Tree-sitter 기반 정확한 SQL 블록 추출
    - pyparsing 기반 정교한 SQL 타입 분류
    - 호스트 변수 입출력 분류 (블랙리스트 지원)
    - SQL 정규화 (EXEC SQL 제거, INTO 절 처리)
    
    Usage:
        adapter = ProcParserSQLAdapter()
        sql_elements = adapter.extract_sql_elements(code, functions)
        for el in sql_elements:
            print(el['sql_id'], el['sql_type'], el['normalized_sql'])
    """
    
    def __init__(self, config: SQLExtractorConfig = None):
        """
        어댑터 초기화
        
        Args:
            config: SQL 추출기 설정 (None이면 기본값 사용)
        """
        self.config = config or SQLExtractorConfig()
        self.ts_extractor = TreeSitterSQLExtractor()
        self.parser = PyparsingProCParser(config=self.config)
        self._sql_counter = 0
    
    def reset_counter(self):
        """SQL ID 카운터 초기화"""
        self._sql_counter = 0
    
    def extract_sql_elements(
        self, 
        content: str, 
        functions: List[Dict] = None
    ) -> List[ExtractedSQL]:
        """
        Pro*C 코드에서 SQL 요소를 추출하여 ExtractedSQL 객체 리스트로 반환
        
        Args:
            content: Pro*C 소스 코드
            functions: 함수 정보 리스트 (스코프 해결용)
                       [{'name': 'func_name', 'line_start': 10, 'line_end': 50}, ...]
        
        Returns:
            ExtractedSQL 객체 리스트
        """
        # Tree-sitter로 SQL 블록 추출
        sql_blocks = self.ts_extractor.extract_sql_blocks(content, functions)
        
        results = []
        for block in sql_blocks:
            extracted = self._process_sql_block(block, content)
            if extracted:
                results.append(extracted)
        
        return results
    
    def extract_sql_elements_as_dicts(
        self, 
        content: str, 
        functions: List[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Pro*C 코드에서 SQL 요소를 추출하여 딕셔너리 리스트로 반환
        
        proc_parser.core와 직접 호환되는 형식입니다.
        
        Args:
            content: Pro*C 소스 코드
            functions: 함수 정보 리스트
        
        Returns:
            proc_parser 호환 딕셔너리 리스트
        """
        elements = self.extract_sql_elements(content, functions)
        return [el.to_dict() for el in elements]
    
    def _process_sql_block(
        self, 
        block: SQLBlock, 
        content: str
    ) -> Optional[ExtractedSQL]:
        """
        개별 SQL 블록을 처리하여 ExtractedSQL 객체 생성
        
        Args:
            block: Tree-sitter로 추출된 SQL 블록
            content: 전체 소스 코드 (바이트 오프셋 계산용)
        
        Returns:
            ExtractedSQL 객체 또는 None (처리 실패 시)
        """
        try:
            raw_sql = block.text
            
            # SQL 타입 결정
            sql_type = self.parser.determine_sql_type(raw_sql)
            
            # 호스트 변수 분류
            input_vars, output_vars = self.parser.classify_host_variables(
                raw_sql, sql_type
            )
            
            # 호스트 변수에 콜론 접두사 추가
            input_vars = [f":{v}" if not v.startswith(':') else v for v in input_vars]
            output_vars = [f":{v}" if not v.startswith(':') else v for v in output_vars]
            
            # SQL 정규화
            normalized = self._normalize_sql(raw_sql, sql_type)
            
            # SQL ID 생성
            self._sql_counter += 1
            sql_id = f"sql_{self._sql_counter:03d}"
            
            # SQL 타입 대문자 변환
            sql_type_upper = sql_type.upper().replace('_', ' ') if sql_type else "UNKNOWN"
            # fetch_into -> FETCH, declare_cursor -> DECLARE
            if sql_type_upper == "FETCH INTO":
                sql_type_upper = "FETCH"
            elif sql_type_upper == "DECLARE CURSOR":
                sql_type_upper = "DECLARE"
            elif sql_type_upper == "BEGIN DECLARE SECTION" or sql_type_upper == "DECLARE SECTION BEGIN":
                sql_type_upper = "BEGIN"
            elif sql_type_upper == "END DECLARE SECTION" or sql_type_upper == "DECLARE SECTION END":
                sql_type_upper = "END"
            
            return ExtractedSQL(
                type="sql",
                sql_id=sql_id,
                sql_type=sql_type_upper,
                raw_content=raw_sql,
                normalized_sql=normalized,
                input_host_vars=input_vars,
                output_host_vars=output_vars,
                line_start=block.start_line,
                line_end=block.end_line,
                byte_start=block.start_byte,
                byte_end=block.end_byte,
                function=block.containing_function,
                relationship=None,
                parse_method="pyparsing" if self.parser else "regex",
                # 기존 호환성 필드
                id=sql_id,
                name=f"{sql_type}_{self._sql_counter - 1}" if sql_type else sql_id,
                sql=raw_sql,
                function_name=block.containing_function,
                input_vars=input_vars,
                output_vars=output_vars
            )
            
        except Exception as e:
            logger.warning(f"SQL 블록 처리 실패: {e}")
            logger.debug(f"문제의 SQL: {block.text[:100]}...")
            return None
    
    def _normalize_sql(self, raw_sql: str, sql_type: str) -> str:
        """
        Pro*C SQL을 정규화
        
        - EXEC SQL 접두사 제거
        - INTO 절 제거 (SELECT/FETCH)
        - 공백 정규화
        - 세미콜론 제거
        
        Args:
            raw_sql: 원본 Pro*C SQL
            sql_type: SQL 타입
        
        Returns:
            정규화된 SQL
        """
        sql = raw_sql.strip()
        
        # EXEC SQL 제거
        sql = re.sub(r'^\s*EXEC\s+SQL\s+', '', sql, flags=re.IGNORECASE)
        
        # FOR :array_size 절 제거 (Array DML)
        sql = re.sub(r'^\s*FOR\s+:?\w+(?:\[[^\]]+\])?\s+', '', sql, flags=re.IGNORECASE)
        
        # INTO 절 제거 (SELECT, FETCH)
        if sql_type and sql_type.lower() in ['select', 'fetch', 'fetch_into']:
            # INTO ... FROM 패턴
            sql = re.sub(
                r'\bINTO\s+[^;]+?\s+FROM\b',
                'FROM',
                sql,
                flags=re.IGNORECASE | re.DOTALL
            )
            # FETCH cursor INTO ... 에서 INTO 이후 제거
            if sql_type.lower() in ['fetch', 'fetch_into']:
                sql = re.sub(
                    r'\bINTO\s+[^;]+',
                    '',
                    sql,
                    flags=re.IGNORECASE
                )
        
        # 세미콜론 제거
        sql = sql.rstrip(';').strip()
        
        # 공백 정규화
        sql = re.sub(r'\s+', ' ', sql)
        
        return sql


def get_proc_parser_adapter(config: SQLExtractorConfig = None) -> ProcParserSQLAdapter:
    """
    ProcParserSQLAdapter 인스턴스 반환
    
    Args:
        config: SQL 추출기 설정
    
    Returns:
        ProcParserSQLAdapter 인스턴스
    """
    return ProcParserSQLAdapter(config=config)
