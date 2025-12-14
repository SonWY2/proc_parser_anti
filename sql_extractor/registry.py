"""
규칙 레지스트리 모듈

SQL 타입 및 호스트 변수 규칙을 등록하고 관리합니다.
"""

from typing import List, Dict, Any, Optional
import logging

from .rules.base import SQLTypeRule, HostVariableRule, RuleMatch
from .rules.sql_type_rules import DEFAULT_SQL_TYPE_RULES
from .rules.host_variable_rules import DEFAULT_HOST_VARIABLE_RULES

logger = logging.getLogger(__name__)


class SQLTypeRegistry:
    """SQL 타입 규칙 레지스트리
    
    규칙을 등록하고, SQL 텍스트에서 타입을 결정합니다.
    규칙은 우선순위 순서로 검사됩니다.
    
    Example:
        registry = SQLTypeRegistry()
        
        # 기본 규칙 로드
        registry.load_defaults()
        
        # 커스텀 규칙 추가
        registry.register(MyCustomRule())
        
        # 타입 결정
        result = registry.determine_type("EXEC SQL SELECT ...")
        print(result.value)  # "select"
    """
    
    def __init__(self):
        self._rules: List[SQLTypeRule] = []
    
    def register(self, rule: SQLTypeRule) -> None:
        """규칙 등록
        
        등록 후 우선순위로 자동 정렬됩니다.
        
        Args:
            rule: 등록할 규칙
        """
        self._rules.append(rule)
        self._sort_rules()
        logger.debug(f"Registered SQL type rule: {rule.name} (priority: {rule.priority})")
    
    def register_many(self, rules: List[SQLTypeRule]) -> None:
        """여러 규칙 등록
        
        Args:
            rules: 등록할 규칙 목록
        """
        for rule in rules:
            self._rules.append(rule)
        self._sort_rules()
        logger.debug(f"Registered {len(rules)} SQL type rules")
    
    def _sort_rules(self) -> None:
        """우선순위로 규칙 정렬 (높은 것 먼저)"""
        self._rules.sort(key=lambda r: r.priority, reverse=True)
    
    def load_defaults(self) -> None:
        """기본 규칙 로드"""
        self.register_many(DEFAULT_SQL_TYPE_RULES)
        logger.info(f"Loaded {len(DEFAULT_SQL_TYPE_RULES)} default SQL type rules")
    
    def load_db2_rules(self) -> None:
        """DB2 전용 규칙 로드"""
        from .rules.db2_rules import DB2_RULES
        self.register_many(DB2_RULES)
        logger.info(f"Loaded {len(DB2_RULES)} DB2 SQL type rules")
    
    def clear(self) -> None:
        """모든 규칙 제거"""
        self._rules.clear()
    
    def determine_type(self, sql_text: str) -> RuleMatch:
        """SQL 타입 결정
        
        등록된 규칙을 우선순위 순서로 적용하여
        첫 번째 매칭되는 규칙의 값을 반환합니다.
        
        Args:
            sql_text: EXEC SQL 구문 전체 텍스트
        
        Returns:
            RuleMatch: 매칭 결과 (매칭 없으면 value="unknown")
        """
        for rule in self._rules:
            try:
                result = rule.match(sql_text)
                if result.matched:
                    logger.debug(f"SQL type matched: {result.value} by {rule.__class__.__name__}")
                    return result
            except Exception as e:
                logger.warning(f"Rule {rule.__class__.__name__} failed: {e}")
                continue
        
        logger.debug(f"No SQL type matched for: {sql_text[:50]}...")
        return RuleMatch(matched=False, value="unknown")
    
    def list_rules(self) -> List[Dict[str, Any]]:
        """등록된 규칙 목록 반환
        
        Returns:
            규칙 정보 딕셔너리 목록
        """
        return [
            {
                'name': r.name,
                'priority': r.priority,
                'class': r.__class__.__name__
            }
            for r in self._rules
        ]
    
    @property
    def rule_count(self) -> int:
        """등록된 규칙 수"""
        return len(self._rules)


class HostVariableRegistry:
    """호스트 변수 규칙 레지스트리
    
    호스트 변수 추출 규칙을 관리합니다.
    규칙 순서가 중요합니다 (복잡한 패턴이 먼저 검사되어야 함).
    
    Example:
        registry = HostVariableRegistry()
        registry.load_defaults()
        
        variables = registry.extract_all(":var1, :arr[i]:ind")
        # [{'type': 'basic', 'var_name': 'var1', ...}, ...]
    """
    
    def __init__(self):
        self._rules: List[HostVariableRule] = []
    
    def register(self, rule: HostVariableRule) -> None:
        """규칙 등록
        
        Args:
            rule: 등록할 규칙
        """
        self._rules.append(rule)
        logger.debug(f"Registered host variable rule: {rule.name}")
    
    def register_many(self, rules: List[HostVariableRule]) -> None:
        """여러 규칙 등록
        
        Args:
            rules: 등록할 규칙 목록
        """
        for rule in rules:
            self._rules.append(rule)
        logger.debug(f"Registered {len(rules)} host variable rules")
    
    def load_defaults(self) -> None:
        """기본 규칙 로드"""
        self.register_many(DEFAULT_HOST_VARIABLE_RULES)
        logger.info(f"Loaded {len(DEFAULT_HOST_VARIABLE_RULES)} default host variable rules")
    
    def clear(self) -> None:
        """모든 규칙 제거"""
        self._rules.clear()
    
    def extract_all(self, sql_text: str) -> List[Dict[str, Any]]:
        """SQL에서 모든 호스트 변수 추출
        
        각 규칙을 순서대로 적용하여 모든 호스트 변수를 추출합니다.
        중복/겹치는 매칭은 제거됩니다.
        
        Args:
            sql_text: SQL 텍스트
        
        Returns:
            호스트 변수 정보 딕셔너리 목록
        """
        all_matches = []
        
        for rule in self._rules:
            try:
                for match in rule.pattern.finditer(sql_text):
                    var_info = rule.extract(match)
                    var_info['raw'] = match.group(0)
                    var_info['start'] = match.start()
                    var_info['end'] = match.end()
                    all_matches.append(var_info)
            except Exception as e:
                logger.warning(f"Host variable rule {rule.name} failed: {e}")
                continue
        
        # 위치로 정렬
        all_matches.sort(key=lambda v: v['start'])
        
        # 중복/겹침 제거
        return self._remove_overlapping(all_matches)
    
    def _remove_overlapping(self, variables: List[Dict]) -> List[Dict]:
        """중복/겹치는 변수 제거
        
        겹치는 매칭 중 더 긴 것을 우선합니다.
        
        Args:
            variables: 정렬된 변수 목록
        
        Returns:
            중복 제거된 변수 목록
        """
        if not variables:
            return []
        
        result = [variables[0]]
        
        for var in variables[1:]:
            last = result[-1]
            
            # 겹치지 않으면 추가
            if var['start'] >= last['end']:
                result.append(var)
            # 겹치지만 더 길면 교체
            elif (var['end'] - var['start']) > (last['end'] - last['start']):
                result[-1] = var
            # 그 외 (겹치고 더 짧으면)는 무시
        
        return result
    
    def classify_by_direction(
        self, 
        sql_text: str, 
        sql_type: str
    ) -> tuple[List[Dict], List[Dict]]:
        """호스트 변수를 입력/출력으로 분류
        
        INTO 절의 변수는 OUTPUT, 나머지는 INPUT으로 분류합니다.
        
        Args:
            sql_text: SQL 텍스트
            sql_type: SQL 타입 (select, fetch_into 등)
        
        Returns:
            (input_vars, output_vars) 튜플
        """
        all_vars = self.extract_all(sql_text)
        
        # SELECT나 FETCH의 INTO 절 변수는 OUTPUT
        if sql_type in ('select', 'fetch_into'):
            into_match = re.search(
                r'\bINTO\b([\s\S]*?)(?:\bFROM\b|\bWHERE\b|;|$)', 
                sql_text, 
                re.IGNORECASE
            )
            
            if into_match:
                into_start = into_match.start(1)
                into_end = into_match.end(1)
                
                input_vars = []
                output_vars = []
                
                for var in all_vars:
                    if into_start <= var['start'] < into_end:
                        output_vars.append(var)
                    else:
                        input_vars.append(var)
                
                return input_vars, output_vars
        
        # 그 외 모든 변수는 INPUT
        return all_vars, []
    
    @property
    def rule_count(self) -> int:
        """등록된 규칙 수"""
        return len(self._rules)


# re import for classify_by_direction
import re
