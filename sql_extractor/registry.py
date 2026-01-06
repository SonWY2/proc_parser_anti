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
    config.PARSER_MODE에 따라 정규식 또는 pyparsing을 사용합니다.
    
    Args:
        config: SQLExtractorConfig 인스턴스 (선택사항)
    
    Example:
        # 기본 사용 (auto 모드)
        registry = HostVariableRegistry()
        registry.load_defaults()
        
        # pyparsing 강제 사용
        config = SQLExtractorConfig(PARSER_MODE="pyparsing")
        registry = HostVariableRegistry(config=config)
        
        variables = registry.extract_all(":var1, :arr[i]:ind")
        # [{'type': 'basic', 'var_name': 'var1', ...}, ...]
    """
    
    def __init__(self, config: 'SQLExtractorConfig' = None):
        from .config import SQLExtractorConfig
        
        self._rules: List[HostVariableRule] = []
        self._config = config or SQLExtractorConfig()
        
        # pyparsing 파서 (지연 초기화)
        self._pyparsing_parser = None
        self._use_pyparsing: Optional[bool] = None
    
    def _init_parser(self) -> None:
        """파서 초기화 (지연 로딩)"""
        if self._use_pyparsing is not None:
            return  # 이미 초기화됨
        
        parser_mode = self._config.PARSER_MODE.lower()
        
        if parser_mode == "regex":
            self._use_pyparsing = False
            logger.info("HostVariableRegistry: regex 모드 사용")
        elif parser_mode == "pyparsing":
            try:
                from .pyparsing_parser import PyparsingProCParser, HAS_PYPARSING
                if not HAS_PYPARSING:
                    raise ImportError("pyparsing library not installed")
                self._pyparsing_parser = PyparsingProCParser(config=self._config)
                self._use_pyparsing = True
                logger.info("HostVariableRegistry: pyparsing 모드 사용")
            except ImportError as e:
                raise RuntimeError(f"pyparsing 모드가 요청되었으나 사용 불가: {e}")
        else:  # auto
            try:
                from .pyparsing_parser import PyparsingProCParser, HAS_PYPARSING
                if HAS_PYPARSING:
                    self._pyparsing_parser = PyparsingProCParser(config=self._config)
                    self._use_pyparsing = True
                    logger.info("HostVariableRegistry: pyparsing 자동 감지됨, pyparsing 모드 사용")
                else:
                    self._use_pyparsing = False
                    logger.info("HostVariableRegistry: pyparsing 미설치, regex 모드로 fallback")
            except ImportError:
                self._use_pyparsing = False
                logger.info("HostVariableRegistry: pyparsing 모듈 로드 실패, regex 모드로 fallback")
    
    @property
    def use_pyparsing(self) -> bool:
        """현재 pyparsing 사용 여부"""
        self._init_parser()
        return self._use_pyparsing
    
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
        
        config.PARSER_MODE에 따라 pyparsing 또는 정규식을 사용합니다.
        pyparsing 모드에서는 블랙리스트/문자열 리터럴 필터링이 더 정확합니다.
        
        Args:
            sql_text: SQL 텍스트
        
        Returns:
            호스트 변수 정보 딕셔너리 목록
        """
        self._init_parser()
        
        # pyparsing 모드
        if self._use_pyparsing and self._pyparsing_parser:
            return self._extract_with_pyparsing(sql_text)
        
        # regex 모드
        return self._extract_with_regex(sql_text)
    
    def _extract_with_pyparsing(self, sql_text: str) -> List[Dict[str, Any]]:
        """pyparsing 기반 호스트 변수 추출"""
        raw_vars = self._pyparsing_parser.extract_all_host_variables(sql_text)
        
        result = []
        for raw in raw_vars:
            parsed = self._pyparsing_parser.parse_host_variable(raw)
            if parsed:
                parsed['raw'] = raw
                # 위치 정보 추가
                start = sql_text.find(raw)
                parsed['start'] = start
                parsed['end'] = start + len(raw) if start >= 0 else 0
                result.append(parsed)
        
        return result
    
    def _extract_with_regex(self, sql_text: str) -> List[Dict[str, Any]]:
        """정규식 기반 호스트 변수 추출 (기존 규칙 사용)"""
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
