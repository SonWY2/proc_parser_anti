"""
DB 방언 변환 플러그인

Oracle, DB2 등의 SQL을 MySQL 등 다른 DB 방언으로 변환합니다.
"""

import re
from typing import Dict, Any, List, Tuple
from .base import SQLTransformPlugin


class DialectPlugin(SQLTransformPlugin):
    """
    DB 방언 변환 플러그인 기본 클래스
    
    SQL 함수, 키워드 등을 다른 DB 방언으로 변환합니다.
    """
    
    name = "dialect_base"
    priority = 70  # 페이징보다 먼저 실행
    
    # 변환 규칙: (패턴, 대체문자열)
    replacements: List[Tuple[str, str]] = []
    
    def can_transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> bool:
        """모든 SQL에 대해 변환 시도"""
        return True
    
    def transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """정의된 규칙으로 변환"""
        result = sql
        for pattern, replacement in self.replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result


class OracleToMySQLPlugin(DialectPlugin):
    """
    Oracle → MySQL 변환 플러그인
    
    주요 변환:
    - NVL → IFNULL
    - SYSDATE → NOW()
    - DECODE → CASE WHEN
    - || 연결 → CONCAT
    - ROWNUM 처리
    - TO_CHAR/TO_DATE 변환
    """
    
    name = "oracle_to_mysql"
    
    replacements = [
        # 함수 변환
        (r'\bNVL\s*\(', 'IFNULL('),
        (r'\bNVL2\s*\(', 'IF('),  # NVL2(a,b,c) → IF(a,b,c)는 정확하지 않음, 수동 검토 필요
        (r'\bSYSDATE\b', 'NOW()'),
        (r'\bSYSTIMESTAMP\b', 'NOW()'),
        (r"\bTO_DATE\s*\(\s*'([^']+)'\s*\)", r"STR_TO_DATE('\1', '%Y-%m-%d')"),
        (r'\bLENGTH\s*\(', 'LENGTH('),  # 동일
        (r'\bSUBSTR\s*\(', 'SUBSTRING('),
        (r'\bINSTR\s*\(', 'LOCATE('),
        
        # 날짜 함수
        (r'\bADD_MONTHS\s*\(([^,]+),\s*([^)]+)\)', r'DATE_ADD(\1, INTERVAL \2 MONTH)'),
        (r'\bMONTHS_BETWEEN\s*\(([^,]+),\s*([^)]+)\)', r'TIMESTAMPDIFF(MONTH, \2, \1)'),
        
        # 문자열 연결 (기본 케이스만)
        # || 연결은 복잡한 경우가 많아 수동 검토 권장
        # (r"'([^']+)'\s*\|\|\s*'([^']+)'", r"CONCAT('\1', '\2')"),
    ]
    
    def transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """Oracle SQL을 MySQL로 변환"""
        result = super().transform(sql, sql_type, metadata)
        
        # DECODE → CASE 변환 (간단한 케이스만)
        result = self._convert_decode(result)
        
        # 문자열 연결 || → CONCAT
        result = self._convert_concat(result)
        
        return result
    
    def _convert_decode(self, sql: str) -> str:
        """
        DECODE 함수를 CASE WHEN으로 변환
        
        간단한 케이스만 처리, 복잡한 경우는 수동 검토 필요
        """
        # DECODE(expr, val1, result1, val2, result2, ..., default)
        decode_pattern = r'\bDECODE\s*\(\s*([^,]+),\s*([^)]+)\)'
        
        def replace_decode(match):
            expr = match.group(1).strip()
            args_str = match.group(2)
            
            # 인자 파싱 (간단한 케이스만)
            args = self._split_args(args_str)
            
            if len(args) < 2:
                return match.group(0)  # 변환 불가
            
            case_parts = [f"CASE {expr}"]
            
            i = 0
            while i + 1 < len(args):
                val = args[i].strip()
                result = args[i + 1].strip()
                case_parts.append(f"WHEN {val} THEN {result}")
                i += 2
            
            # 마지막 인자가 default
            if i < len(args):
                default = args[i].strip()
                case_parts.append(f"ELSE {default}")
            
            case_parts.append("END")
            return ' '.join(case_parts)
        
        return re.sub(decode_pattern, replace_decode, sql, flags=re.IGNORECASE)
    
    def _convert_concat(self, sql: str) -> str:
        """|| 연결을 CONCAT으로 변환"""
        # 간단한 a || b 패턴만 처리
        # 복잡한 중첩 케이스는 수동 검토 필요
        
        concat_pattern = r'(\S+)\s*\|\|\s*(\S+)'
        
        # 최대 10번 반복 (중첩 연결 처리)
        for _ in range(10):
            new_sql = re.sub(concat_pattern, r'CONCAT(\1, \2)', sql)
            if new_sql == sql:
                break
            sql = new_sql
        
        return sql
    
    def _split_args(self, args_str: str) -> List[str]:
        """쉼표로 인자 분리 (괄호, 따옴표 고려)"""
        args = []
        current = []
        paren_depth = 0
        in_quote = False
        quote_char = ''
        
        for char in args_str:
            if in_quote:
                current.append(char)
                if char == quote_char:
                    in_quote = False
            else:
                if char in '"\'':
                    in_quote = True
                    quote_char = char
                    current.append(char)
                elif char == '(':
                    paren_depth += 1
                    current.append(char)
                elif char == ')':
                    paren_depth -= 1
                    current.append(char)
                elif char == ',' and paren_depth == 0:
                    args.append(''.join(current).strip())
                    current = []
                else:
                    current.append(char)
        
        if current:
            args.append(''.join(current).strip())
        
        return args


class DB2ToMySQLPlugin(DialectPlugin):
    """
    DB2 → MySQL 변환 플러그인
    """
    
    name = "db2_to_mysql"
    
    replacements = [
        # 함수 변환
        (r'\bVALUE\s*\(', 'COALESCE('),  # VALUE → COALESCE
        (r'\bCURRENT\s+DATE\b', 'CURDATE()'),
        (r'\bCURRENT\s+TIME\b', 'CURTIME()'),
        (r'\bCURRENT\s+TIMESTAMP\b', 'NOW()'),
        
        # 문자열 함수
        (r'\bLOCATE\s*\(', 'LOCATE('),  # 동일
        (r'\bPOSSTR\s*\(([^,]+),\s*([^)]+)\)', r'LOCATE(\2, \1)'),  # 인자 순서 다름
        
        # FETCH FIRST 제거 (페이징 플러그인에서 처리)
        (r'\bFETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY\b', ''),
    ]


class MySQLToOraclePlugin(DialectPlugin):
    """
    MySQL → Oracle 변환 플러그인
    """
    
    name = "mysql_to_oracle"
    
    replacements = [
        # 함수 변환
        (r'\bIFNULL\s*\(', 'NVL('),
        (r'\bNOW\s*\(\s*\)', 'SYSDATE'),
        (r'\bCURDATE\s*\(\s*\)', 'TRUNC(SYSDATE)'),
        (r'\bCURTIME\s*\(\s*\)', 'TO_CHAR(SYSDATE, \'HH24:MI:SS\')'),
        
        # LIMIT/OFFSET 제거 (Oracle 페이징으로 대체 필요)
        (r'\bLIMIT\s+\d+\s+OFFSET\s+\d+\b', ''),
        (r'\bLIMIT\s+\d+\b', ''),
    ]
