"""
동적 SQL 관계 플러그인

동적 SQL 문을 감지하고 그룹화합니다:
PREPARE -> EXECUTE (-> DEALLOCATE)

또한 C 문자열 조작 함수를 추적하여 전체 SQL 문자열을 재구성하려고 시도합니다.
"""

import re
from typing import List, Dict, Optional, Any
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sql_relationship_plugin import SQLRelationshipPlugin
from sql_converter import SQLConverter


class DynamicSQLRelationshipPlugin(SQLRelationshipPlugin):
    """
    Pro*C 코드에서 동적 SQL 관계를 감지하는 플러그인입니다.
    
    동적 SQL 작업은 일반적으로 다음을 따릅니다:
    1. PREPARE statement_name FROM <sql_source>
    2. EXECUTE statement_name [USING <params>] (여러 번 가능)
    3. DEALLOCATE statement_name (선택 사항)
    
    이 플러그인은 이러한 문을 그룹화하고 MyBatis 변환을 위한 메타데이터를 추출합니다.
    또한 C 코드를 분석하여 동적 SQL 문자열을 재구성하려고 시도합니다.
    """
    
    def __init__(self):
        self.sql_converter = SQLConverter()

    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """PREPARE 문이 존재하는지 확인합니다."""
        return any(el.get('sql_type', '').upper() == 'PREPARE' for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict], all_elements: List[Dict] = None) -> List[Dict]:
        """
        동적 SQL 관계를 추출합니다.
        
        동적 SQL 메타데이터가 포함된 관계 딕셔너리 목록을 반환합니다.
        """
        relationships = []
        stmt_counter = {}
        
        # 모든 PREPARE 문 찾기
        for prepare_el in sql_elements:
            if prepare_el.get('sql_type', '').upper() != 'PREPARE':
                continue
            
            stmt_name = self._extract_statement_name(prepare_el)
            if not stmt_name:
                continue
            
            # 고유 관계 ID 생성
            if stmt_name not in stmt_counter:
                stmt_counter[stmt_name] = 0
            stmt_counter[stmt_name] += 1
            
            relationship_id = self._generate_relationship_id(
                "dynamic_sql", stmt_name, stmt_counter[stmt_name]
            )
            
            # 관련된 EXECUTE 및 DEALLOCATE 문 찾기
            related_sql_ids = [prepare_el['sql_id']]
            execute_elements = []
            
            # EXECUTE 문 검색
            execute_els = self._find_all_statements(
                sql_elements, 'EXECUTE', stmt_name, after_line=prepare_el['line_start']
            )
            for exec_el in execute_els:
                related_sql_ids.append(exec_el['sql_id'])
                execute_elements.append(exec_el)
            
            # DEALLOCATE 문 검색 (선택 사항)
            deallocate_el = self._find_statement(
                sql_elements, 'DEALLOCATE', stmt_name, after_line=prepare_el['line_start']
            )
            if deallocate_el:
                related_sql_ids.append(deallocate_el['sql_id'])
            
            # SQL 소스 추출 (호스트 변수 또는 리터럴)
            sql_source = self._extract_sql_source(prepare_el)
            is_literal = not sql_source.startswith(':')
            
            # EXECUTE 문의 모든 파라미터 집계
            all_parameters = []
            for exec_el in execute_elements:
                params = exec_el.get('input_host_vars', [])
                all_parameters.extend(params)
            all_parameters = list(dict.fromkeys(all_parameters))  # 중복 제거
            
            # 관계 메타데이터 생성
            metadata = {
                'statement_name': stmt_name,
                'sql_source': sql_source,
                'is_literal_source': is_literal,
                'execution_count': len(execute_elements),
                'all_parameters': all_parameters,
                'has_deallocate': deallocate_el is not None
            }
            
            # 리터럴인 경우 실제 SQL 추출 시도
            if is_literal:
                metadata['literal_sql'] = self._extract_literal_sql(prepare_el)
            elif all_elements:
                # 호스트 변수인 경우 C 코드에서 SQL 재구성 시도
                var_name = sql_source[1:] # 선행 콜론 제거
                # MyBatis 별칭 제거 (예: :var AS varName -> var)
                if ' AS ' in var_name:
                    var_name = var_name.split(' AS ')[0]

                reconstructed_sql = self._reconstruct_sql_from_c_code(
                    var_name, prepare_el['line_start'], all_elements, prepare_el.get('function')
                )
                if reconstructed_sql:
                    metadata['reconstructed_sql'] = reconstructed_sql
                    # 정규화도 수행
                    normalized = self.sql_converter.normalize_sql(reconstructed_sql)
                    metadata['normalized_reconstructed_sql'] = normalized['normalized_sql']
            
            relationships.append({
                'relationship_id': relationship_id,
                'relationship_type': 'DYNAMIC_SQL',
                'sql_ids': related_sql_ids,
                'metadata': metadata
            })
        
        return relationships
    
    def _reconstruct_sql_from_c_code(self, variable_name: str, current_line: int, 
                                     all_elements: List[Dict], function_name: Optional[str]) -> Optional[str]:
        """
        C 문자열 조작 함수를 추적하여 SQL 문자열을 재구성하려고 시도합니다.
        
        Args:
            variable_name: SQL을 보유한 호스트 변수의 이름.
            current_line: PREPARE 문의 라인 번호.
            all_elements: 모든 파싱된 요소 목록 (C 및 Pro*C).
            function_name: 검색할 함수 범위.
            
        Returns:
            재구성된 SQL 문자열 또는 실패 시 None.
        """
        if not function_name:
            return None
            
        # 동일한 함수 내에서 PREPARE 문 이전의 요소 필터링
        relevant_elements = [
            el for el in all_elements 
            if el.get('function') == function_name and el['line_end'] < current_line
        ]
        
        # 라인 번호로 정렬
        relevant_elements.sort(key=lambda x: x['line_start'])
        
        # 변수의 상태를 추적해야 함.
        # 이것은 단순화된 시뮬레이션임.
        # 다음을 찾음:
        # 1. strcpy(var, "string")
        # 2. strcat(var, "string")
        # 3. sprintf(var, "fmt", args...)
        
        # 중간 변수도 처리해야 할까?
        # 예: strcpy(temp, "..."); strcat(sql, temp);
        # 지금은 변수 값의 딕셔너리를 추적.
        
        var_values = {}
        
        for el in relevant_elements:
            if el['type'] != 'function_call':
                continue
            
            name = el.get('name', '')
            args = el.get('args', []) # args가 문자열 리스트나 딕셔너리로 파싱되었다고 가정
            
            # CParser가 구조화된 args를 제공하지 않는 경우 제대로 파싱하려면 raw args가 필요함
            # CParser가 raw arg 문자열을 제공하면 분할해야 함.
            # raw content를 가져와서 대략적으로 args를 파싱할 수 있다고 가정.
            
            raw_content = el.get('raw_content', '')
            # raw content에서 args 추출: func(arg1, arg2)
            arg_str_match = re.search(r'\w+\s*\((.*)\)', raw_content, re.DOTALL)
            if not arg_str_match:
                # Fallback: try to construct from args if available
                if args:
                     parsed_args = args
                else:
                     continue
            else:
                arg_str = arg_str_match.group(1)
                # 따옴표와 괄호를 존중하여 쉼표로 args 분할
                parsed_args = self._parse_c_args(arg_str)
            
            if not parsed_args:
                continue
                
            dest_var = parsed_args[0]
            
            if name == 'strcpy':
                if len(parsed_args) >= 2:
                    src = parsed_args[1]
                    val = self._resolve_value(src, var_values)
                    var_values[dest_var] = val
                    
            elif name == 'strncpy':
                 if len(parsed_args) >= 2:
                    src = parsed_args[1]
                    val = self._resolve_value(src, var_values)
                    var_values[dest_var] = val # 단순화를 위해 strcpy로 취급
            
            elif name == 'strcat':
                if len(parsed_args) >= 2:
                    src = parsed_args[1]
                    val = self._resolve_value(src, var_values)
                    if dest_var in var_values:
                        var_values[dest_var] += val
                    else:
                        var_values[dest_var] = val # 알 수 없는 경우 빈 시작으로 가정?
                        
            elif name == 'strncat':
                if len(parsed_args) >= 2:
                    src = parsed_args[1]
                    val = self._resolve_value(src, var_values)
                    if dest_var in var_values:
                        var_values[dest_var] += val
                    else:
                        var_values[dest_var] = val

            elif name in ['sprintf', 'snprintf']:
                # sprintf(buf, fmt, args...)
                # snprintf(buf, size, fmt, args...)
                start_idx = 1 if name == 'sprintf' else 2
                if len(parsed_args) > start_idx:
                    fmt = parsed_args[start_idx]
                    fmt_val = self._resolve_value(fmt, var_values)
                    
                    # %s, %d 등을 플레이스홀더나 값으로 대체
                    # 남은 args 필요
                    format_args = parsed_args[start_idx+1:]
                    formatted_str = self._simulate_sprintf(fmt_val, format_args, var_values)
                    var_values[dest_var] = formatted_str

        return var_values.get(variable_name)

    def _resolve_value(self, arg: str, var_values: Dict[str, str]) -> str:
        """Resolve a C argument to a string value."""
        arg = arg.strip()
        # 리터럴 문자열
        if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
            return arg[1:-1]
        
        # 변수 조회
        if arg in var_values:
            return var_values[arg]
            
        # 알 수 없는 변수 또는 표현식
        return "?" # 플레이스홀더

    def _simulate_sprintf(self, fmt: str, args: List[str], var_values: Dict[str, str]) -> str:
        """
        Simulate sprintf formatting.
        Replaces %s, %d etc with values from args or placeholders.
        """
        # % 지정자를 찾기 위한 간단한 정규식
        # 이것은 전체 printf 파서가 아니며 기본 지원만 함
        parts = re.split(r'(%[-+0-9.]*[a-zA-Z])', fmt)
        result = []
        arg_idx = 0
        
        for part in parts:
            if part.startswith('%') and part != '%%':
                if arg_idx < len(args):
                    val = self._resolve_value(args[arg_idx], var_values)
                    # val이 '?'인 경우 ? 또는 :var로 유지할 수 있음
                    # SQL 조각인 경우 추가함.
                    # 값(숫자나 문자열 리터럴 등)인 경우 유지할 수 있음?
                    # 대개 동적 SQL에서 %s는 테이블 이름이나 절에 사용됨.
                    # %d는 값일 수 있음.
                    # 해결된 값을 사용하자.
                    result.append(val)
                    arg_idx += 1
                else:
                    result.append(part) # 인자가 충분하지 않음?
            else:
                result.append(part)
                
        return "".join(result)

    def _parse_c_args(self, arg_str: str) -> List[str]:
        """
        Split C argument string by comma, respecting quotes and parentheses.
        """
        args = []
        current_arg = []
        in_quote = False
        quote_char = ''
        paren_depth = 0
        
        for char in arg_str:
            if in_quote:
                current_arg.append(char)
                if char == quote_char and (len(current_arg) < 2 or current_arg[-2] != '\\'):
                    in_quote = False
            else:
                if char == '"' or char == "'":
                    in_quote = True
                    quote_char = char
                    current_arg.append(char)
                elif char == '(':
                    paren_depth += 1
                    current_arg.append(char)
                elif char == ')':
                    paren_depth -= 1
                    current_arg.append(char)
                elif char == ',' and paren_depth == 0:
                    args.append("".join(current_arg).strip())
                    current_arg = []
                else:
                    current_arg.append(char)
        
        if current_arg:
            args.append("".join(current_arg).strip())
            
        return args

    def _extract_statement_name(self, prepare_el: Dict) -> Optional[str]:
        """Extract statement name from PREPARE statement."""
        sql = prepare_el.get('normalized_sql', '')
        # 패턴: PREPARE <stmt_name> FROM ...
        match = re.search(r'PREPARE\s+(\w+)\s+FROM', sql, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_sql_source(self, prepare_el: Dict) -> str:
        """Extract the SQL source (host var or literal) from PREPARE."""
        sql = prepare_el.get('normalized_sql', '')
        # 패턴: PREPARE stmt FROM <source>
        match = re.search(r'FROM\s+(.+)', sql, re.IGNORECASE)
        if match:
            source = match.group(1).strip()
            # 세미콜론이 있으면 제거
            return source.rstrip(';').strip()
        return ''
    
    def _extract_literal_sql(self, prepare_el: Dict) -> str:
        """Extract literal SQL string if source is a literal."""
        raw = prepare_el.get('raw_content', '')
        # 패턴: PREPARE ... FROM "SELECT ..." 또는 'SELECT ...'
        # 잠재적인 C 문자열 연결이나 여러 줄 문자열을 대략적으로 처리
        match = re.search(r'FROM\s+([\'"])(.*?)\1', raw, re.IGNORECASE | re.DOTALL)
        if match:
            sql = match.group(2)
            # 기본 정리: 줄바꿈을 공백으로 대체, 공백 축소
            return re.sub(r'\s+', ' ', sql).strip()
        return ''
    
    def _find_statement(self, sql_elements: List[Dict], stmt_type: str,
                       stmt_name: str, after_line: int) -> Optional[Dict]:
        """Find a specific statement referencing the prepared statement."""
        for el in sql_elements:
            if (el.get('sql_type', '').upper() == stmt_type.upper() and
                el.get('line_start', 0) > after_line and
                stmt_name in el.get('normalized_sql', '')):
                return el
        return None
    
    def _find_all_statements(self, sql_elements: List[Dict], stmt_type: str,
                            stmt_name: str, after_line: int) -> List[Dict]:
        """Find all statements of a type referencing the prepared statement."""
        results = []
        for el in sql_elements:
            if (el.get('sql_type', '').upper() == stmt_type.upper() and
                el.get('line_start', 0) > after_line and
                stmt_name in el.get('normalized_sql', '')):
                results.append(el)
        return results
