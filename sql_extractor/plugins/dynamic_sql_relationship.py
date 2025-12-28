"""
동적 SQL 관계 플러그인

동적 SQL 문을 감지하고 그룹화합니다:
PREPARE -> EXECUTE (-> DEALLOCATE)

또한 C 문자열 조작 함수를 추적하여 전체 SQL 문자열을 재구성합니다.
"""

import re
from typing import List, Dict, Optional

from .base import SQLRelationshipPlugin


class DynamicSQLRelationshipPlugin(SQLRelationshipPlugin):
    """
    Pro*C 코드에서 동적 SQL 관계를 감지하는 플러그인입니다.
    
    동적 SQL 작업은 일반적으로 다음을 따릅니다:
    1. PREPARE statement_name FROM <sql_source>
    2. EXECUTE statement_name [USING <params>] (여러 번 가능)
    3. DEALLOCATE statement_name (선택 사항)
    """

    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """PREPARE 문이 존재하는지 확인합니다."""
        return any(el.get('sql_type', '').upper() == 'PREPARE' for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict], all_elements: List[Dict] = None) -> List[Dict]:
        """동적 SQL 관계를 추출합니다."""
        relationships = []
        stmt_counter = {}
        
        for prepare_el in sql_elements:
            if prepare_el.get('sql_type', '').upper() != 'PREPARE':
                continue
            
            stmt_name = self._extract_statement_name(prepare_el)
            if not stmt_name:
                continue
            
            if stmt_name not in stmt_counter:
                stmt_counter[stmt_name] = 0
            stmt_counter[stmt_name] += 1
            
            relationship_id = self._generate_relationship_id(
                "dynamic_sql", stmt_name, stmt_counter[stmt_name]
            )
            
            related_sql_ids = [prepare_el['sql_id']]
            execute_elements = []
            
            execute_els = self._find_all_statements(
                sql_elements, 'EXECUTE', stmt_name, after_line=prepare_el['line_start']
            )
            for exec_el in execute_els:
                related_sql_ids.append(exec_el['sql_id'])
                execute_elements.append(exec_el)
            
            deallocate_el = self._find_statement(
                sql_elements, 'DEALLOCATE', stmt_name, after_line=prepare_el['line_start']
            )
            if deallocate_el:
                related_sql_ids.append(deallocate_el['sql_id'])
            
            sql_source = self._extract_sql_source(prepare_el)
            is_literal = not sql_source.startswith(':')
            
            all_parameters = []
            for exec_el in execute_elements:
                params = exec_el.get('input_host_vars', [])
                all_parameters.extend(params)
            all_parameters = list(dict.fromkeys(all_parameters))
            
            metadata = {
                'statement_name': stmt_name,
                'sql_source': sql_source,
                'is_literal_source': is_literal,
                'execution_count': len(execute_elements),
                'all_parameters': all_parameters,
                'has_deallocate': deallocate_el is not None
            }
            
            if is_literal:
                metadata['literal_sql'] = self._extract_literal_sql(prepare_el)
            elif all_elements:
                var_name = sql_source[1:]
                reconstructed_sql = self._reconstruct_sql_from_c_code(
                    var_name, prepare_el['line_start'], all_elements, prepare_el.get('function')
                )
                if reconstructed_sql:
                    metadata['reconstructed_sql'] = reconstructed_sql
            
            relationships.append({
                'relationship_id': relationship_id,
                'relationship_type': 'DYNAMIC_SQL',
                'sql_ids': related_sql_ids,
                'metadata': metadata
            })
        
        return relationships
    
    def _reconstruct_sql_from_c_code(self, variable_name: str, current_line: int, 
                                     all_elements: List[Dict], function_name: Optional[str]) -> Optional[str]:
        """C 문자열 조작 함수를 추적하여 SQL 문자열을 재구성합니다."""
        if not function_name:
            return None
            
        relevant_elements = [
            el for el in all_elements 
            if el.get('function') == function_name and el['line_end'] < current_line
        ]
        relevant_elements.sort(key=lambda x: x['line_start'])
        
        var_values = {}
        
        for el in relevant_elements:
            if el['type'] != 'function_call':
                continue
            
            name = el.get('name', '')
            raw_content = el.get('raw_content', '')
            arg_str_match = re.search(r'\w+\s*\((.*)\)', raw_content, re.DOTALL)
            if not arg_str_match:
                continue
            
            parsed_args = self._parse_c_args(arg_str_match.group(1))
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
                    var_values[dest_var] = val
            
            elif name == 'strcat':
                if len(parsed_args) >= 2:
                    src = parsed_args[1]
                    val = self._resolve_value(src, var_values)
                    if dest_var in var_values:
                        var_values[dest_var] += val
                    else:
                        var_values[dest_var] = val
                        
            elif name == 'strncat':
                if len(parsed_args) >= 2:
                    src = parsed_args[1]
                    val = self._resolve_value(src, var_values)
                    if dest_var in var_values:
                        var_values[dest_var] += val
                    else:
                        var_values[dest_var] = val

            elif name in ['sprintf', 'snprintf']:
                start_idx = 1 if name == 'sprintf' else 2
                if len(parsed_args) > start_idx:
                    fmt = parsed_args[start_idx]
                    fmt_val = self._resolve_value(fmt, var_values)
                    format_args = parsed_args[start_idx+1:]
                    formatted_str = self._simulate_sprintf(fmt_val, format_args, var_values)
                    var_values[dest_var] = formatted_str

        return var_values.get(variable_name)

    def _resolve_value(self, arg: str, var_values: Dict[str, str]) -> str:
        """Resolve a C argument to a string value."""
        arg = arg.strip()
        if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
            return arg[1:-1]
        if arg in var_values:
            return var_values[arg]
        return "?"

    def _simulate_sprintf(self, fmt: str, args: List[str], var_values: Dict[str, str]) -> str:
        """Simulate sprintf formatting."""
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
                    result.append(part)
            else:
                result.append(part)
                
        return "".join(result)

    def _parse_c_args(self, arg_str: str) -> List[str]:
        """Split C argument string by comma, respecting quotes and parentheses."""
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
        match = re.search(r'PREPARE\s+(\w+)\s+FROM', sql, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_sql_source(self, prepare_el: Dict) -> str:
        """Extract the SQL source (host var or literal) from PREPARE."""
        sql = prepare_el.get('normalized_sql', '')
        match = re.search(r'FROM\s+(.+)', sql, re.IGNORECASE)
        if match:
            source = match.group(1).strip()
            return source.rstrip(';').strip()
        return ''
    
    def _extract_literal_sql(self, prepare_el: Dict) -> str:
        """Extract literal SQL string if source is a literal."""
        raw = prepare_el.get('raw_content', '')
        match = re.search(r'FROM\s+([\'"])(.*?)\1', raw, re.IGNORECASE | re.DOTALL)
        if match:
            sql = match.group(2)
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
