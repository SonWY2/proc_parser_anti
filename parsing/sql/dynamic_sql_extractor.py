"""
동적 SQL 추출 모듈

strncpy, strcpy, strcat, sprintf 등 C 문자열 함수로 
조합된 SQL을 추출합니다.

기존 DynamicSQLRelationshipPlugin._reconstruct_sql_from_c_code 로직을 
sql_extractor로 통합.
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class DynamicSQL:
    """동적 SQL 정보"""
    variable_name: str
    reconstructed_sql: str
    function_name: Optional[str]
    confidence: float  # 재구성 신뢰도 (0.0 ~ 1.0)
    source_operations: List[str]  # 추적된 문자열 연산들


class DynamicSQLExtractor:
    """
    C 문자열 함수를 추적하여 동적 SQL 추출
    
    지원하는 함수:
    - strcpy, strncpy
    - strcat, strncat  
    - sprintf, snprintf
    
    Example:
        extractor = DynamicSQLExtractor()
        result = extractor.extract_dynamic_sql(
            variable_name="sql_stmt",
            c_elements=parsed_c_elements,
            before_line=100,
            function_name="process_data"
        )
    """
    
    def __init__(self):
        self._string_functions = {
            'strcpy', 'strncpy', 'strcat', 'strncat', 
            'sprintf', 'snprintf', 'memcpy'
        }
    
    def extract_dynamic_sql(
        self,
        variable_name: str,
        c_elements: List[Dict],
        before_line: int,
        function_name: Optional[str] = None
    ) -> Optional[DynamicSQL]:
        """
        C 코드 요소에서 동적 SQL 재구성
        
        Args:
            variable_name: SQL을 담는 호스트 변수명
            c_elements: 파싱된 C 코드 요소 목록
            before_line: PREPARE 문 이전 라인까지만 탐색
            function_name: 탐색할 함수 범위 (None이면 전체)
        
        Returns:
            DynamicSQL 객체 또는 None
        """
        # 관련 요소 필터링
        relevant = self._filter_relevant_elements(
            c_elements, before_line, function_name
        )
        
        if not relevant:
            return None
        
        # 변수 상태 추적
        var_values, operations = self._track_string_operations(
            relevant, variable_name
        )
        
        reconstructed = var_values.get(variable_name)
        if not reconstructed:
            return None
        
        # 신뢰도 계산
        confidence = self._calculate_confidence(operations)
        
        return DynamicSQL(
            variable_name=variable_name,
            reconstructed_sql=reconstructed,
            function_name=function_name,
            confidence=confidence,
            source_operations=operations
        )
    
    def _filter_relevant_elements(
        self,
        c_elements: List[Dict],
        before_line: int,
        function_name: Optional[str]
    ) -> List[Dict]:
        """관련 C 요소 필터링"""
        filtered = []
        
        for el in c_elements:
            # 라인 범위 체크
            line_end = el.get('line_end', el.get('line_start', 0))
            if line_end >= before_line:
                continue
            
            # 함수 범위 체크
            if function_name and el.get('function') != function_name:
                continue
            
            # 함수 호출 타입만
            if el.get('type') == 'function_call':
                filtered.append(el)
        
        # 라인 순서 정렬
        filtered.sort(key=lambda x: x.get('line_start', 0))
        return filtered
    
    def _track_string_operations(
        self,
        elements: List[Dict],
        target_var: str
    ) -> Tuple[Dict[str, str], List[str]]:
        """
        문자열 연산 추적
        
        Returns:
            (변수-값 딕셔너리, 연산 목록)
        """
        var_values: Dict[str, str] = {}
        operations: List[str] = []
        
        for el in elements:
            func_name = el.get('name', '')
            if func_name not in self._string_functions:
                continue
            
            raw_content = el.get('raw_content', '')
            args = self._parse_c_args(raw_content, func_name)
            
            if not args:
                continue
            
            dest_var = args[0].strip()
            
            if func_name in ['strcpy', 'strncpy']:
                if len(args) >= 2:
                    src = args[1]
                    val = self._resolve_value(src, var_values)
                    var_values[dest_var] = val
                    operations.append(f"{func_name}({dest_var}, {src})")
            
            elif func_name in ['strcat', 'strncat']:
                if len(args) >= 2:
                    src = args[1]
                    val = self._resolve_value(src, var_values)
                    if dest_var in var_values:
                        var_values[dest_var] += val
                    else:
                        var_values[dest_var] = val
                    operations.append(f"{func_name}({dest_var}, {src})")
            
            elif func_name in ['sprintf', 'snprintf']:
                start_idx = 1 if func_name == 'sprintf' else 2
                if len(args) > start_idx:
                    fmt = args[start_idx]
                    fmt_val = self._resolve_value(fmt, var_values)
                    format_args = args[start_idx + 1:]
                    formatted = self._simulate_sprintf(fmt_val, format_args, var_values)
                    var_values[dest_var] = formatted
                    operations.append(f"{func_name}({dest_var}, {fmt}, ...)")
        
        return var_values, operations
    
    def _parse_c_args(self, raw_content: str, func_name: str) -> List[str]:
        """C 함수 호출에서 인자 파싱"""
        # 함수 호출 패턴: func(arg1, arg2, ...)
        match = re.search(rf'{func_name}\s*\((.+)\)', raw_content, re.DOTALL)
        if not match:
            return []
        
        arg_str = match.group(1)
        return self._split_args(arg_str)
    
    def _split_args(self, arg_str: str) -> List[str]:
        """인자 문자열을 쉼표로 분리 (따옴표, 괄호 고려)"""
        args = []
        current = []
        in_quote = False
        quote_char = ''
        paren_depth = 0
        
        for char in arg_str:
            if in_quote:
                current.append(char)
                if char == quote_char and (len(current) < 2 or current[-2] != '\\'):
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
    
    def _resolve_value(self, arg: str, var_values: Dict[str, str]) -> str:
        """인자 값 해석"""
        arg = arg.strip()
        
        # 문자열 리터럴
        if (arg.startswith('"') and arg.endswith('"')) or \
           (arg.startswith("'") and arg.endswith("'")):
            return arg[1:-1]
        
        # 변수 조회
        if arg in var_values:
            return var_values[arg]
        
        # 알 수 없는 값
        return "?"
    
    def _simulate_sprintf(
        self,
        fmt: str,
        args: List[str],
        var_values: Dict[str, str]
    ) -> str:
        """sprintf 시뮬레이션"""
        parts = re.split(r'(%[-+0-9.]*[a-zA-Z])', fmt)
        result = []
        arg_idx = 0
        
        for part in parts:
            if part.startswith('%') and part != '%%':
                if arg_idx < len(args):
                    val = self._resolve_value(args[arg_idx], var_values)
                    result.append(val)
                    arg_idx += 1
                else:
                    result.append('?')
            else:
                result.append(part)
        
        return ''.join(result)
    
    def _calculate_confidence(self, operations: List[str]) -> float:
        """재구성 신뢰도 계산"""
        if not operations:
            return 0.0
        
        # 연산이 많을수록 신뢰도 약간 감소 (복잡성)
        base = 1.0
        penalty = len(operations) * 0.05
        
        # ? 플레이스홀더가 있으면 신뢰도 감소
        placeholder_penalty = sum(1 for op in operations if '?' in str(op)) * 0.1
        
        return max(0.0, min(1.0, base - penalty - placeholder_penalty))
