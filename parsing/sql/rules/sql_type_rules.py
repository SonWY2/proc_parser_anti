"""
SQL 타입 결정 규칙 모듈

EXEC SQL 구문의 타입을 결정하는 규칙들을 정의합니다.
우선순위가 높은 규칙이 먼저 검사됩니다.
"""

import re
from .base import SQLTypeRule, RuleMatch


class IncludeRule(SQLTypeRule):
    """EXEC SQL INCLUDE 규칙"""
    
    @property
    def name(self) -> str:
        return "include"
    
    @property
    def priority(self) -> int:
        return 100  # 최우선
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+INCLUDE\s+\w+\s*;', re.IGNORECASE)


class DeclareSectionBeginRule(SQLTypeRule):
    """BEGIN DECLARE SECTION 규칙"""
    
    @property
    def name(self) -> str:
        return "declare_section_begin"
    
    @property
    def priority(self) -> int:
        return 95
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(
            r'EXEC\s+SQL\s+BEGIN\s+DECLARE\s+SECTION', 
            re.IGNORECASE
        )


class DeclareSectionEndRule(SQLTypeRule):
    """END DECLARE SECTION 규칙"""
    
    @property
    def name(self) -> str:
        return "declare_section_end"
    
    @property
    def priority(self) -> int:
        return 95
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(
            r'EXEC\s+SQL\s+END\s+DECLARE\s+SECTION', 
            re.IGNORECASE
        )


class DeclareCursorRule(SQLTypeRule):
    """DECLARE CURSOR 규칙"""
    
    @property
    def name(self) -> str:
        return "declare_cursor"
    
    @property
    def priority(self) -> int:
        return 90
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(
            r'EXEC\s+SQL\s+DECLARE\s+\w+\s+CURSOR\s+FOR', 
            re.IGNORECASE
        )


class OpenCursorRule(SQLTypeRule):
    """OPEN CURSOR 규칙"""
    
    @property
    def name(self) -> str:
        return "open"
    
    @property
    def priority(self) -> int:
        return 80
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+OPEN\s+\w+', re.IGNORECASE)


class CloseCursorRule(SQLTypeRule):
    """CLOSE CURSOR 규칙"""
    
    @property
    def name(self) -> str:
        return "close"
    
    @property
    def priority(self) -> int:
        return 80
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+CLOSE\s+\w+', re.IGNORECASE)


class FetchIntoRule(SQLTypeRule):
    """FETCH INTO 규칙"""
    
    @property
    def name(self) -> str:
        return "fetch_into"
    
    @property
    def priority(self) -> int:
        return 85
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(
            r'EXEC\s+SQL\s+FETCH\s+[\s\S]*?INTO', 
            re.IGNORECASE
        )


class SelectRule(SQLTypeRule):
    """SELECT 규칙"""
    
    @property
    def name(self) -> str:
        return "select"
    
    @property
    def priority(self) -> int:
        return 50
    
    @property
    def pattern(self) -> re.Pattern:
        # 주석을 포함할 수 있음
        return re.compile(
            r'EXEC\s+SQL\s+(?:/\*.*?\*/\s*)?SELECT', 
            re.IGNORECASE | re.DOTALL
        )


class InsertRule(SQLTypeRule):
    """INSERT 규칙"""
    
    @property
    def name(self) -> str:
        return "insert"
    
    @property
    def priority(self) -> int:
        return 50
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+INSERT', re.IGNORECASE)


class UpdateRule(SQLTypeRule):
    """UPDATE 규칙"""
    
    @property
    def name(self) -> str:
        return "update"
    
    @property
    def priority(self) -> int:
        return 50
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+UPDATE', re.IGNORECASE)


class DeleteRule(SQLTypeRule):
    """DELETE 규칙"""
    
    @property
    def name(self) -> str:
        return "delete"
    
    @property
    def priority(self) -> int:
        return 50
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+DELETE', re.IGNORECASE)


class CommitRule(SQLTypeRule):
    """COMMIT 규칙"""
    
    @property
    def name(self) -> str:
        return "commit"
    
    @property
    def priority(self) -> int:
        return 60
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+COMMIT', re.IGNORECASE)


class RollbackRule(SQLTypeRule):
    """ROLLBACK 규칙"""
    
    @property
    def name(self) -> str:
        return "rollback"
    
    @property
    def priority(self) -> int:
        return 60
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+ROLLBACK', re.IGNORECASE)


class PrepareRule(SQLTypeRule):
    """PREPARE 규칙 (동적 SQL)"""
    
    @property
    def name(self) -> str:
        return "prepare"
    
    @property
    def priority(self) -> int:
        return 70
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+PREPARE', re.IGNORECASE)


class ExecuteRule(SQLTypeRule):
    """EXECUTE 규칙 (동적 SQL)"""
    
    @property
    def name(self) -> str:
        return "execute"
    
    @property
    def priority(self) -> int:
        return 70
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+EXECUTE', re.IGNORECASE)


class ConnectRule(SQLTypeRule):
    """CONNECT 규칙"""
    
    @property
    def name(self) -> str:
        return "connect"
    
    @property
    def priority(self) -> int:
        return 65
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+CONNECT', re.IGNORECASE)


class WheneverRule(SQLTypeRule):
    """WHENEVER 규칙"""
    
    @property
    def name(self) -> str:
        return "whenever"
    
    @property
    def priority(self) -> int:
        return 75
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+WHENEVER', re.IGNORECASE)


class DisconnectRule(SQLTypeRule):
    """DISCONNECT 규칙"""
    
    @property
    def name(self) -> str:
        return "disconnect"
    
    @property
    def priority(self) -> int:
        return 65
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r'EXEC\s+SQL\s+DISCONNECT', re.IGNORECASE)


# 기본 SQL 타입 규칙 목록
DEFAULT_SQL_TYPE_RULES = [
    IncludeRule(),
    DeclareSectionBeginRule(),
    DeclareSectionEndRule(),
    DeclareCursorRule(),
    OpenCursorRule(),
    CloseCursorRule(),
    FetchIntoRule(),
    PrepareRule(),
    ExecuteRule(),
    WheneverRule(),
    ConnectRule(),
    DisconnectRule(),
    CommitRule(),
    RollbackRule(),
    SelectRule(),
    InsertRule(),
    UpdateRule(),
    DeleteRule(),
]

