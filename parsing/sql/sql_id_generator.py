"""
SQL ID 생성기 모듈

SQL 타입별로 순차적인 ID를 생성합니다.
예: select_0, select_1, insert_0, update_0
"""

from typing import Dict, Optional
from collections import defaultdict


class SQLIdGenerator:
    """
    SQL 타입 기반 순차 ID 생성기
    
    Example:
        generator = SQLIdGenerator()
        id1 = generator.generate_id("select")  # "select_0"
        id2 = generator.generate_id("select")  # "select_1"
        id3 = generator.generate_id("insert")  # "insert_0"
    """
    
    def __init__(self, prefix: str = "", separator: str = "_"):
        """
        생성기 초기화
        
        Args:
            prefix: ID 접두사 (예: "sql_" → "sql_select_0")
            separator: 타입과 번호 사이 구분자
        """
        self._counters: Dict[str, int] = defaultdict(int)
        self._prefix = prefix
        self._separator = separator
    
    def generate_id(self, sql_type: str) -> str:
        """
        SQL 타입에 대한 새 ID 생성
        
        Args:
            sql_type: SQL 타입 (select, insert, update, delete, ...)
        
        Returns:
            생성된 ID (예: select_0, insert_1)
        """
        # 타입 정규화 (소문자)
        normalized_type = sql_type.lower()
        
        # 일부 타입은 상위 타입으로 매핑
        type_mapping = {
            "declare_cursor": "select",
            "fetch_into": "select",
            "open": "cursor_op",
            "close": "cursor_op",
            "commit": "transaction",
            "rollback": "transaction",
            "prepare": "dynamic",
            "execute": "dynamic",
        }
        
        base_type = type_mapping.get(normalized_type, normalized_type)
        
        # ID 생성
        current_count = self._counters[base_type]
        self._counters[base_type] += 1
        
        if self._prefix:
            return f"{self._prefix}{base_type}{self._separator}{current_count}"
        return f"{base_type}{self._separator}{current_count}"
    
    def peek_next_id(self, sql_type: str) -> str:
        """
        다음에 생성될 ID 미리보기 (카운터 증가 없음)
        
        Args:
            sql_type: SQL 타입
        
        Returns:
            다음 ID
        """
        normalized_type = sql_type.lower()
        type_mapping = {
            "declare_cursor": "select",
            "fetch_into": "select",
        }
        base_type = type_mapping.get(normalized_type, normalized_type)
        current_count = self._counters[base_type]
        
        if self._prefix:
            return f"{self._prefix}{base_type}{self._separator}{current_count}"
        return f"{base_type}{self._separator}{current_count}"
    
    def get_current_count(self, sql_type: str) -> int:
        """특정 타입의 현재 카운트 조회"""
        normalized_type = sql_type.lower()
        return self._counters.get(normalized_type, 0)
    
    def get_all_counts(self) -> Dict[str, int]:
        """모든 타입의 카운트 조회"""
        return dict(self._counters)
    
    def reset(self, sql_type: str = None):
        """
        카운터 리셋
        
        Args:
            sql_type: 특정 타입만 리셋 (None이면 전체 리셋)
        """
        if sql_type:
            normalized_type = sql_type.lower()
            self._counters[normalized_type] = 0
        else:
            self._counters.clear()
    
    def set_counter(self, sql_type: str, value: int):
        """특정 타입의 카운터 값 설정"""
        normalized_type = sql_type.lower()
        self._counters[normalized_type] = value


# 전역 인스턴스 (편의용)
_global_generator: Optional[SQLIdGenerator] = None


def get_global_generator() -> SQLIdGenerator:
    """전역 ID 생성기 반환"""
    global _global_generator
    if _global_generator is None:
        _global_generator = SQLIdGenerator()
    return _global_generator


def reset_global_generator():
    """전역 ID 생성기 리셋"""
    global _global_generator
    if _global_generator:
        _global_generator.reset()
