"""
pyparsing 기반 Pro*C SQL 파서

기존 정규식 기반 파싱을 pyparsing으로 리팩토링한 버전입니다.
더 나은 가독성, 유지보수성, 에러 처리를 제공합니다.

pyparsing이 없는 환경에서는 정규식 기반 fallback을 사용합니다.
"""

import re
import logging
from typing import Dict, List, Optional, Any

from .types import SqlType, HostVariable, HostVariableType, VariableDirection

logger = logging.getLogger(__name__)

# pyparsing 가용성 확인
try:
    from pyparsing import (
        Word, Literal, Optional as Opt, ZeroOrMore,
        alphas, alphanums, nums, Suppress, Regex, CaselessKeyword,
        ParseException, SkipTo, lineEnd
    )
    HAS_PYPARSING = True
except ImportError:
    HAS_PYPARSING = False
    logger.warning("pyparsing not available. Using regex-only mode.")


class PyparsingProCParser:
    """pyparsing 기반 Pro*C SQL 파서
    
    pyparsing을 사용하여 Pro*C SQL 구문을 파싱합니다.
    pyparsing이 없는 환경에서는 정규식 fallback을 사용합니다.
    """
    
    def __init__(self):
        """파서 초기화 및 문법 설정"""
        self.has_pyparsing = HAS_PYPARSING
        
        if self.has_pyparsing:
            self._setup_grammar()
        
        # 정규식 패턴들 (fallback용)
        self._setup_regex_patterns()
    
    def _setup_regex_patterns(self):
        """정규식 패턴 설정"""
        # 호스트 변수 패턴
        self.host_var_pattern = re.compile(
            r':[\w$#@]+(?:\[[\w\d]+\])?(?:\.[\w$#@]+)?(?::[\w$#@]+)?'
        )
        
        # SQL 키워드 패턴
        self.sql_patterns = {
            'include': re.compile(r'EXEC\s+SQL\s+INCLUDE\s+SQLCA\s*;', re.IGNORECASE),
            'declare_section_begin': re.compile(
                r'EXEC\s+SQL\s+BEGIN\s+DECLARE\s+SECTION', re.IGNORECASE
            ),
            'declare_section_end': re.compile(
                r'EXEC\s+SQL\s+END\s+DECLARE\s+SECTION', re.IGNORECASE
            ),
            'declare_cursor': re.compile(
                r'EXEC\s+SQL\s+DECLARE\s+\w+\s+CURSOR\s+FOR', re.IGNORECASE
            ),
            'open': re.compile(r'EXEC\s+SQL\s+OPEN\b', re.IGNORECASE),
            'close': re.compile(r'EXEC\s+SQL\s+CLOSE\b', re.IGNORECASE),
            'fetch_into': re.compile(
                r'EXEC\s+SQL\s+FETCH\s+[\s\S]+?INTO', re.IGNORECASE
            ),
            'select': re.compile(
                r'EXEC\s+SQL\s+(?:\/\*.*?\*\/\s*)?SELECT', re.IGNORECASE | re.DOTALL
            ),
            'insert': re.compile(r'EXEC\s+SQL\s+INSERT', re.IGNORECASE),
            'update': re.compile(r'EXEC\s+SQL\s+UPDATE', re.IGNORECASE),
            'delete': re.compile(r'EXEC\s+SQL\s+DELETE', re.IGNORECASE),
            'commit': re.compile(r'EXEC\s+SQL\s+COMMIT', re.IGNORECASE),
            'rollback': re.compile(r'EXEC\s+SQL\s+ROLLBACK', re.IGNORECASE),
            'connect': re.compile(r'EXEC\s+SQL\s+CONNECT', re.IGNORECASE),
            'prepare': re.compile(r'EXEC\s+SQL\s+PREPARE', re.IGNORECASE),
            'execute': re.compile(r'EXEC\s+SQL\s+EXECUTE', re.IGNORECASE),
            'whenever': re.compile(r'EXEC\s+SQL\s+WHENEVER', re.IGNORECASE),
        }
        
        # 호스트 변수 상세 패턴
        self.host_var_struct_indicator = re.compile(
            r':(\w+)\.(\w+):(\w+)'
        )
        self.host_var_array_indicator = re.compile(
            r':(\w+)\[([^\]]+)\]:(\w+)'
        )
        self.host_var_array = re.compile(
            r':(\w+)\[([^\]]+)\]'
        )
        self.host_var_struct = re.compile(
            r':(\w+)\.(\w+)'
        )
        self.host_var_indicator = re.compile(
            r':(\w+):(\w+)'
        )
        self.host_var_basic = re.compile(
            r':(\w+)'
        )
    
    def _setup_grammar(self):
        """pyparsing 문법 규칙 설정"""
        if not self.has_pyparsing:
            return
        
        # 기본 토큰 정의
        self.identifier = Word(alphas + "_", alphanums + "_$#@")
        self.number = Word(nums)
        colon = Literal(":")
        
        # 호스트 변수 문법 정의
        self.host_var_basic_pp = (
            Suppress(colon) + 
            self.identifier("var_name")
        )
        
        self.host_var_array_pp = (
            Suppress(colon) + 
            self.identifier("var_name") +
            Suppress("[") +
            (self.identifier | self.number)("index") +
            Suppress("]")
        )
        
        self.host_var_struct_pp = (
            Suppress(colon) + 
            self.identifier("var_name") +
            Suppress(".") +
            self.identifier("field_name")
        )
        
        self.host_var_indicator_pp = (
            Suppress(colon) + 
            self.identifier("var_name") +
            Suppress(colon) +
            self.identifier("indicator_name")
        )
        
        self.host_var_struct_indicator_pp = (
            Suppress(colon) + 
            self.identifier("var_name") +
            Suppress(".") +
            self.identifier("field_name") +
            Suppress(colon) +
            self.identifier("indicator_name")
        )
        
        self.host_var_array_indicator_pp = (
            Suppress(colon) + 
            self.identifier("var_name") +
            Suppress("[") +
            (self.identifier | self.number)("index") +
            Suppress("]") +
            Suppress(colon) +
            self.identifier("indicator_name")
        )
        
        # SQL 키워드 정의
        self.kw_select = CaselessKeyword("SELECT")
        self.kw_insert = CaselessKeyword("INSERT")
        self.kw_update = CaselessKeyword("UPDATE")
        self.kw_delete = CaselessKeyword("DELETE")
        self.kw_declare = CaselessKeyword("DECLARE")
        self.kw_cursor = CaselessKeyword("CURSOR")
        self.kw_for = CaselessKeyword("FOR")
        self.kw_open = CaselessKeyword("OPEN")
        self.kw_fetch = CaselessKeyword("FETCH")
        self.kw_close = CaselessKeyword("CLOSE")
        self.kw_into = CaselessKeyword("INTO")
        self.kw_exec = CaselessKeyword("EXEC")
        self.kw_sql = CaselessKeyword("SQL")
        self.kw_begin = CaselessKeyword("BEGIN")
        self.kw_end = CaselessKeyword("END")
        self.kw_section = CaselessKeyword("SECTION")
        
        # SQL 구문 패턴 정의
        self.declare_cursor_stmt = (
            self.kw_declare +
            self.identifier("cursor_name") +
            self.kw_cursor +
            self.kw_for +
            SkipTo(Literal(";") | lineEnd)("query")
        )
        
        self.open_cursor_stmt = (
            self.kw_open +
            self.identifier("cursor_name")
        )
        
        self.fetch_cursor_stmt = (
            self.kw_fetch +
            self.identifier("cursor_name") +
            self.kw_into +
            SkipTo(Literal(";") | lineEnd)("into_clause")
        )
        
        self.close_cursor_stmt = (
            self.kw_close +
            self.identifier("cursor_name")
        )
        
        self.begin_section_stmt = (
            self.kw_begin +
            self.kw_declare +
            self.kw_section
        )
        
        self.end_section_stmt = (
            self.kw_end +
            self.kw_declare +
            self.kw_section
        )
    
    def determine_sql_type(self, sql_statement: str) -> str:
        """SQL 문의 타입 결정
        
        pyparsing을 먼저 시도하고, 실패하면 정규식으로 fallback합니다.
        
        Args:
            sql_statement: EXEC SQL 문
        
        Returns:
            SQL 타입 문자열 (기존 호환성 유지)
        
        Raises:
            Exception: 알 수 없는 SQL 타입인 경우
        """
        # pyparsing 시도
        if self.has_pyparsing:
            try:
                result = self._determine_sql_type_pyparsing(sql_statement)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"pyparsing SQL 파싱 실패, 정규식으로 fallback: {e}")
        
        # 정규식 fallback
        return self._determine_sql_type_regex(sql_statement)
    
    def _determine_sql_type_pyparsing(self, sql_statement: str) -> Optional[str]:
        """pyparsing 기반 SQL 타입 결정"""
        if not self.has_pyparsing:
            return None
        
        sql_upper = sql_statement.upper()
        
        try:
            # DECLARE CURSOR
            try:
                self.declare_cursor_stmt.parseString(
                    sql_statement.replace("EXEC SQL", "").strip(), 
                    parseAll=False
                )
                return "declare_cursor"
            except ParseException:
                pass
            
            # OPEN CURSOR
            try:
                self.open_cursor_stmt.parseString(
                    sql_statement.replace("EXEC SQL", "").strip(),
                    parseAll=False
                )
                return "open"
            except ParseException:
                pass
            
            # FETCH CURSOR
            try:
                self.fetch_cursor_stmt.parseString(
                    sql_statement.replace("EXEC SQL", "").strip(),
                    parseAll=False
                )
                return "fetch_into"
            except ParseException:
                pass
            
            # CLOSE CURSOR
            try:
                self.close_cursor_stmt.parseString(
                    sql_statement.replace("EXEC SQL", "").strip(),
                    parseAll=False
                )
                return "close"
            except ParseException:
                pass
            
            # BEGIN DECLARE SECTION
            try:
                self.begin_section_stmt.parseString(
                    sql_statement.replace("EXEC SQL", "").strip(),
                    parseAll=False
                )
                return "declare_section_begin"
            except ParseException:
                pass
            
            # END DECLARE SECTION
            try:
                self.end_section_stmt.parseString(
                    sql_statement.replace("EXEC SQL", "").strip(),
                    parseAll=False
                )
                return "declare_section_end"
            except ParseException:
                pass
            
        except Exception as e:
            logger.debug(f"pyparsing 파싱 중 오류: {e}")
        
        return None
    
    def _determine_sql_type_regex(self, sql_statement: str) -> str:
        """정규식 기반 SQL 타입 결정 (fallback)
        
        Args:
            sql_statement: EXEC SQL 문
        
        Returns:
            SQL 타입 문자열
        
        Raises:
            Exception: 알 수 없는 SQL 타입인 경우
        """
        # INCLUDE 확인
        if sql_statement.strip() in ["EXEC SQL INCLUDE SQLCA;"]:
            return "include"
        
        # 패턴 순서대로 확인 (더 구체적인 것 먼저)
        pattern_order = [
            'declare_section_begin',
            'declare_section_end', 
            'declare_cursor',
            'fetch_into',
            'open',
            'close',
            'insert',
            'update',
            'delete',
            'select',
            'commit',
            'rollback',
            'connect',
            'prepare',
            'execute',
            'whenever',
        ]
        
        for pattern_name in pattern_order:
            if pattern_name in self.sql_patterns:
                if self.sql_patterns[pattern_name].search(sql_statement):
                    return pattern_name
        
        raise Exception(f"Unknown SQL type: {sql_statement[:50]}...")
    
    def parse_host_variable(self, text: str) -> Optional[Dict[str, Any]]:
        """호스트 변수 파싱
        
        Args:
            text: 파싱할 텍스트 (예: ":var_name", ":arr[10]", ":struct.field")
        
        Returns:
            파싱 결과 딕셔너리 또는 None
        """
        # pyparsing 시도
        if self.has_pyparsing:
            result = self._parse_host_variable_pyparsing(text)
            if result:
                return result
        
        # 정규식 fallback
        return self._parse_host_variable_regex(text)
    
    def _parse_host_variable_pyparsing(self, text: str) -> Optional[Dict[str, Any]]:
        """pyparsing 기반 호스트 변수 파싱"""
        if not self.has_pyparsing:
            return None
        
        try:
            # 복합 형태 1: :struct.field:indicator
            try:
                result = self.host_var_struct_indicator_pp.parseString(text, parseAll=True)
                return {
                    'type': HostVariableType.STRUCT_INDICATOR.value,
                    'var_name': result.var_name,
                    'field_name': result.field_name,
                    'indicator_name': result.indicator_name
                }
            except ParseException:
                pass
            
            # 복합 형태 2: :array[idx]:indicator
            try:
                result = self.host_var_array_indicator_pp.parseString(text, parseAll=True)
                return {
                    'type': HostVariableType.ARRAY_INDICATOR.value,
                    'var_name': result.var_name,
                    'index': result.index,
                    'indicator_name': result.indicator_name
                }
            except ParseException:
                pass
            
            # 배열: :var[idx]
            try:
                result = self.host_var_array_pp.parseString(text, parseAll=True)
                return {
                    'type': HostVariableType.ARRAY.value,
                    'var_name': result.var_name,
                    'index': result.index
                }
            except ParseException:
                pass
            
            # 구조체: :var.field
            try:
                result = self.host_var_struct_pp.parseString(text, parseAll=True)
                return {
                    'type': HostVariableType.STRUCT.value,
                    'var_name': result.var_name,
                    'field_name': result.field_name
                }
            except ParseException:
                pass
            
            # 인디케이터: :var:ind
            try:
                result = self.host_var_indicator_pp.parseString(text, parseAll=True)
                return {
                    'type': HostVariableType.INDICATOR.value,
                    'var_name': result.var_name,
                    'indicator_name': result.indicator_name
                }
            except ParseException:
                pass
            
            # 기본: :var
            try:
                result = self.host_var_basic_pp.parseString(text, parseAll=True)
                return {
                    'type': HostVariableType.BASIC.value,
                    'var_name': result.var_name
                }
            except ParseException:
                pass
            
        except Exception as e:
            logger.debug(f"호스트 변수 pyparsing 파싱 중 오류: {text} - {e}")
        
        return None
    
    def _parse_host_variable_regex(self, text: str) -> Optional[Dict[str, Any]]:
        """정규식 기반 호스트 변수 파싱"""
        # :struct.field:indicator
        match = self.host_var_struct_indicator.match(text)
        if match:
            return {
                'type': HostVariableType.STRUCT_INDICATOR.value,
                'var_name': match.group(1),
                'field_name': match.group(2),
                'indicator_name': match.group(3)
            }
        
        # :arr[idx]:indicator
        match = self.host_var_array_indicator.match(text)
        if match:
            return {
                'type': HostVariableType.ARRAY_INDICATOR.value,
                'var_name': match.group(1),
                'index': match.group(2),
                'indicator_name': match.group(3)
            }
        
        # :arr[idx]
        match = self.host_var_array.match(text)
        if match:
            return {
                'type': HostVariableType.ARRAY.value,
                'var_name': match.group(1),
                'index': match.group(2)
            }
        
        # :struct.field
        match = self.host_var_struct.match(text)
        if match:
            return {
                'type': HostVariableType.STRUCT.value,
                'var_name': match.group(1),
                'field_name': match.group(2)
            }
        
        # :var:indicator
        match = self.host_var_indicator.match(text)
        if match:
            return {
                'type': HostVariableType.INDICATOR.value,
                'var_name': match.group(1),
                'indicator_name': match.group(2)
            }
        
        # :var (기본)
        match = self.host_var_basic.match(text)
        if match:
            return {
                'type': HostVariableType.BASIC.value,
                'var_name': match.group(1)
            }
        
        return None
    
    def extract_all_host_variables(self, sql: str) -> List[str]:
        """SQL 문자열에서 모든 호스트 변수 추출
        
        Args:
            sql: SQL 문자열
        
        Returns:
            호스트 변수 리스트 (예: [':var1', ':var2:ind', ':arr[0]'])
        """
        candidates = self.host_var_pattern.findall(sql)
        
        # 각 후보를 검증
        validated = []
        for candidate in candidates:
            if self.parse_host_variable(candidate):
                validated.append(candidate)
        
        return validated
    
    def classify_host_variables(
        self, sql: str, sql_type: str
    ) -> tuple[List[str], List[str]]:
        """호스트 변수를 입력/출력으로 분류
        
        Args:
            sql: SQL 문자열
            sql_type: SQL 타입
        
        Returns:
            (input_vars, output_vars) 튜플
        """
        all_vars = self.extract_all_host_variables(sql)
        input_vars = []
        output_vars = []
        
        # INTO 절 찾기
        into_match = re.search(r'\bINTO\b([\s\S]*?)(?:\bFROM\b|\bWHERE\b|;|$)', sql, re.IGNORECASE)
        
        if into_match and sql_type in ['select', 'fetch_into']:
            into_clause = into_match.group(1)
            into_vars = self.extract_all_host_variables(into_clause)
            output_vars = into_vars
            input_vars = [v for v in all_vars if v not in into_vars]
        else:
            input_vars = all_vars
        
        return input_vars, output_vars


# 편의 함수
def get_sql_parser() -> Optional[PyparsingProCParser]:
    """SQL 파서 인스턴스 반환
    
    Returns:
        PyparsingProCParser 인스턴스 또는 None
    """
    try:
        return PyparsingProCParser()
    except Exception as e:
        logger.error(f"SQL 파서 생성 실패: {e}")
        return None
