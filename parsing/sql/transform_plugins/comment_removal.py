"""
SQL 주석 제거 플러그인

SQL 정규화 시 주석(/* */, --)을 제거합니다.
"""

import re
from typing import Dict, Any

from .base import SQLTransformPlugin


class CommentRemovalPlugin(SQLTransformPlugin):
    """
    SQL 주석 제거 플러그인
    
    SQL 정규화 과정에서 주석을 제거합니다.
    - 블록 주석: /* ... */
    - 라인 주석: -- ...
    
    Attributes:
        name: comment_removal
        priority: 10 (다른 변환보다 먼저 실행)
        
    Example:
        plugin = CommentRemovalPlugin()
        sql = "SELECT * /* 주석 */ FROM users -- 라인 주석"
        result = plugin.transform(sql, "select", {})
        # "SELECT * FROM users"
    """
    
    name = "comment_removal"
    priority = 10  # 가장 먼저 실행 (주석 제거 후 다른 변환)
    enabled = True
    
    # 블록 주석 패턴: /* ... */ (멀티라인 지원)
    BLOCK_COMMENT_PATTERN = re.compile(
        r'/\*.*?\*/',
        re.DOTALL
    )
    
    # 라인 주석 패턴: -- ... (줄 끝까지)
    LINE_COMMENT_PATTERN = re.compile(
        r'--[^\r\n]*'
    )
    
    # 힌트 주석 보존 패턴: /*+ ... */ (Oracle 힌트)
    HINT_COMMENT_PATTERN = re.compile(
        r'/\*\+[^*]*\*/'
    )
    
    def __init__(self, preserve_hints: bool = True):
        """
        Args:
            preserve_hints: Oracle 힌트 주석(/*+ ... */) 보존 여부
        """
        self.preserve_hints = preserve_hints
    
    def can_transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> bool:
        """
        주석이 포함된 SQL인지 확인
        """
        # 블록 주석 또는 라인 주석이 있으면 변환 가능
        return bool(
            self.BLOCK_COMMENT_PATTERN.search(sql) or
            self.LINE_COMMENT_PATTERN.search(sql)
        )
    
    def transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """
        SQL에서 주석 제거
        
        Args:
            sql: 주석이 포함된 SQL
            sql_type: SQL 타입
            metadata: 추가 메타데이터
            
        Returns:
            주석이 제거된 SQL
        """
        result = sql
        
        # 힌트 주석 보존
        hints = []
        if self.preserve_hints:
            hints = self.HINT_COMMENT_PATTERN.findall(result)
            # 힌트를 임시 플레이스홀더로 교체
            for i, hint in enumerate(hints):
                result = result.replace(hint, f"__HINT_{i}__", 1)
        
        # 블록 주석 제거
        result = self.BLOCK_COMMENT_PATTERN.sub(' ', result)
        
        # 라인 주석 제거
        result = self.LINE_COMMENT_PATTERN.sub('', result)
        
        # 힌트 복원
        if self.preserve_hints:
            for i, hint in enumerate(hints):
                result = result.replace(f"__HINT_{i}__", hint)
        
        # 연속 공백 정리
        result = re.sub(r'\s+', ' ', result)
        
        return result.strip()
    
    def get_info(self) -> Dict[str, Any]:
        """플러그인 정보"""
        info = super().get_info()
        info["preserve_hints"] = self.preserve_hints
        return info


class AggressiveCommentRemovalPlugin(CommentRemovalPlugin):
    """
    공격적 주석 제거 플러그인
    
    힌트 주석도 포함하여 모든 주석을 제거합니다.
    """
    
    name = "aggressive_comment_removal"
    
    def __init__(self):
        super().__init__(preserve_hints=False)
