"""
DB2 전용 규칙 모듈

DB2 데이터베이스의 특수 SQL 구문을 인식하는 규칙들을 정의합니다.
예: WITH UR, WITH CS, FETCH FIRST 등
"""

import re
from .base import SQLTypeRule, RuleMatch


class SelectWithURRule(SQLTypeRule):
    """SELECT ... WITH UR 규칙 (Uncommitted Read)
    
    DB2에서 잠금 없이 데이터를 읽는 격리 수준입니다.
    """
    
    @property
    def name(self) -> str:
        return "select"
    
    @property
    def priority(self) -> int:
        return 55  # 일반 SELECT보다 높은 우선순위
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(
            r'EXEC\s+SQL\s+SELECT[\s\S]*?WITH\s+UR', 
            re.IGNORECASE
        )
    
    def match(self, sql_text: str) -> RuleMatch:
        if self.pattern.search(sql_text):
            return RuleMatch(
                matched=True, 
                value=self.name,
                metadata={'isolation_level': 'UR', 'dbms': 'db2'}
            )
        return RuleMatch(matched=False)


class SelectWithCSRule(SQLTypeRule):
    """SELECT ... WITH CS 규칙 (Cursor Stability)
    
    DB2의 기본 격리 수준입니다.
    """
    
    @property
    def name(self) -> str:
        return "select"
    
    @property
    def priority(self) -> int:
        return 55
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(
            r'EXEC\s+SQL\s+SELECT[\s\S]*?WITH\s+CS', 
            re.IGNORECASE
        )
    
    def match(self, sql_text: str) -> RuleMatch:
        if self.pattern.search(sql_text):
            return RuleMatch(
                matched=True,
                value=self.name,
                metadata={'isolation_level': 'CS', 'dbms': 'db2'}
            )
        return RuleMatch(matched=False)


class SelectWithRSRule(SQLTypeRule):
    """SELECT ... WITH RS 규칙 (Read Stability)"""
    
    @property
    def name(self) -> str:
        return "select"
    
    @property
    def priority(self) -> int:
        return 55
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(
            r'EXEC\s+SQL\s+SELECT[\s\S]*?WITH\s+RS', 
            re.IGNORECASE
        )
    
    def match(self, sql_text: str) -> RuleMatch:
        if self.pattern.search(sql_text):
            return RuleMatch(
                matched=True,
                value=self.name,
                metadata={'isolation_level': 'RS', 'dbms': 'db2'}
            )
        return RuleMatch(matched=False)


class SelectWithRRRule(SQLTypeRule):
    """SELECT ... WITH RR 규칙 (Repeatable Read)"""
    
    @property
    def name(self) -> str:
        return "select"
    
    @property
    def priority(self) -> int:
        return 55
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(
            r'EXEC\s+SQL\s+SELECT[\s\S]*?WITH\s+RR', 
            re.IGNORECASE
        )
    
    def match(self, sql_text: str) -> RuleMatch:
        if self.pattern.search(sql_text):
            return RuleMatch(
                matched=True,
                value=self.name,
                metadata={'isolation_level': 'RR', 'dbms': 'db2'}
            )
        return RuleMatch(matched=False)


class FetchFirstRule(SQLTypeRule):
    """FETCH FIRST n ROWS ONLY 규칙
    
    결과 행 수를 제한하는 DB2 구문입니다.
    """
    
    @property
    def name(self) -> str:
        return "select"
    
    @property
    def priority(self) -> int:
        return 55
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(
            r'EXEC\s+SQL\s+SELECT[\s\S]*?FETCH\s+FIRST\s+\d+\s+ROWS?\s+ONLY',
            re.IGNORECASE
        )
    
    def match(self, sql_text: str) -> RuleMatch:
        if self.pattern.search(sql_text):
            # 행 수 추출
            row_match = re.search(r'FETCH\s+FIRST\s+(\d+)', sql_text, re.IGNORECASE)
            row_count = int(row_match.group(1)) if row_match else None
            
            return RuleMatch(
                matched=True,
                value=self.name,
                metadata={'fetch_first': row_count, 'dbms': 'db2'}
            )
        return RuleMatch(matched=False)


class OptimizeForRule(SQLTypeRule):
    """OPTIMIZE FOR n ROWS 규칙
    
    쿼리 최적화 힌트입니다.
    """
    
    @property
    def name(self) -> str:
        return "select"
    
    @property
    def priority(self) -> int:
        return 55
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(
            r'EXEC\s+SQL\s+SELECT[\s\S]*?OPTIMIZE\s+FOR\s+\d+\s+ROWS?',
            re.IGNORECASE
        )
    
    def match(self, sql_text: str) -> RuleMatch:
        if self.pattern.search(sql_text):
            row_match = re.search(r'OPTIMIZE\s+FOR\s+(\d+)', sql_text, re.IGNORECASE)
            row_count = int(row_match.group(1)) if row_match else None
            
            return RuleMatch(
                matched=True,
                value=self.name,
                metadata={'optimize_for': row_count, 'dbms': 'db2'}
            )
        return RuleMatch(matched=False)


# DB2 전용 규칙 목록
DB2_RULES = [
    SelectWithURRule(),
    SelectWithCSRule(),
    SelectWithRSRule(),
    SelectWithRRRule(),
    FetchFirstRule(),
    OptimizeForRule(),
]
