"""
Pro*C SQL 문을 표준 SQL로 변환하고 호스트 변수를 처리하는 모듈입니다.
호스트 변수 추출, 플레이스홀더 대체, 네이밍 컨벤션 적용 등을 수행합니다.
"""
import re
from patterns import PATTERN_HOST_VAR
from plugins.naming_convention import NamingConventionPlugin

class SQLConverter:
    def __init__(self, naming_convention: NamingConventionPlugin = None, strip_semicolon: bool = True):
        self.naming_convention = naming_convention
        self.strip_semicolon = strip_semicolon

    def _strip_comments(self, sql):
        """
        SQL에서 주석을 제거합니다 (타입 감지용).
        문자열 리터럴 내부의 주석 구문은 제거하지 않습니다.
        """
        result = []
        i = 0
        in_string = False
        while i < len(sql):
            # 문자열 시작/종료
            if sql[i] == "'" and not in_string:
                in_string = True
                result.append(sql[i])
                i += 1
            elif sql[i] == "'" and in_string:
                # 이스케이프된 따옴표 확인
                if i + 1 < len(sql) and sql[i+1] == "'":
                    result.append("''")
                    i += 2
                else:
                    in_string = False
                    result.append(sql[i])
                    i += 1
            elif in_string:
                result.append(sql[i])
                i += 1
            # 블록 주석
            elif sql[i:i+2] == '/*':
                end = sql.find('*/', i + 2)
                if end == -1:
                    break
                i = end + 2
            # 라인 주석
            elif sql[i:i+2] == '--':
                end = sql.find('\n', i)
                if end == -1:
                    break
                i = end
            else:
                result.append(sql[i])
                i += 1
        return ''.join(result)

    def normalize_sql(self, raw_sql):
        """
        Pro*C SQL을 표준 SQL로 변환합니다.
        호스트 변수를 추출하고 플레이스홀더로 대체합니다.
        네이밍 컨벤션 플러그인이 제공되면 AS 구문을 사용하여 호스트 변수에 별칭을 지정합니다.
        """
        # 타입 감지를 위해 주석을 먼저 제거
        clean_for_type = self._strip_comments(raw_sql)
        clean_for_type = re.sub(r'\s+', ' ', clean_for_type).strip()
        
        # EXEC SQL prefix 제거
        type_check_sql = re.sub(r'^EXEC\s+SQL\s+', '', clean_for_type, flags=re.IGNORECASE).strip()
        
        # FOR :array_size 처리 (Array DML)
        type_check_sql = re.sub(r'^FOR\s+:?\w+(?:\[\w+\])?\s+', '', type_check_sql, flags=re.IGNORECASE).strip()
        
        first_word = type_check_sql.split(' ')[0].upper() if type_check_sql else ""
        
        sql_type = "UNKNOWN"
        if first_word in ["SELECT", "INSERT", "UPDATE", "DELETE", "DECLARE", "OPEN", "FETCH", "CLOSE", "PREPARE", "EXECUTE", "CONNECT", "COMMIT", "ROLLBACK", "ALTER", "CREATE", "DROP", "TRUNCATE", "MERGE", "CALL", "BEGIN", "END", "SET", "SAVEPOINT", "WHENEVER"]:
            sql_type = first_word
        
        input_vars = []
        output_vars = []
        
        # 토큰화를 위한 Regex
        # 1. 문자열: '...' (이스케이프된 따옴표 '' 처리)
        # 2. 주석: --... (줄바꿈까지) 또는 /*...*/
        # 3. 호스트 변수: :var 또는 :var:indicator 또는 :arr[i]
        # 4. EXEC SQL 키워드 (제거용)
        # 5. INTO 절 키워드
        # 6. FROM 키워드
        # 7. 공백 (정규화용)
        # 8. 기타 텍스트
        
        token_pattern = re.compile(
            r"(?P<string>'([^']|'')*')|"
            r"(?P<comment_single>--[^\n]*)|"
            r"(?P<comment_multi>/\*[\s\S]*?\*/)|"
            r"(?P<exec_sql>\bEXEC\s+SQL\s+)|"
            r"(?P<for_clause>\bFOR\s+:?\w+(?:\[[^\]]+\])?\s+)|"
            r"(?P<host_var>:[a-zA-Z_]\w*(?:\[[^\]]+\])?(?::[a-zA-Z_]\w*)?)|"
            r"(?P<into_keyword>\bINTO\b)|"
            r"(?P<from_keyword>\bFROM\b)|"
            r"(?P<whitespace>\s+)|"
            r"(?P<semicolon>;)|"
            r"(?P<other>.)",
            re.IGNORECASE | re.DOTALL
        )
        
        normalized_parts = []
        
        is_select_or_fetch = sql_type in ["SELECT", "FETCH"]
        is_insert = sql_type == "INSERT"
        
        iterator = token_pattern.finditer(raw_sql)
        
        in_into_clause = False
        last_token_was_semicolon = False
        
        for match in iterator:
            token_type = match.lastgroup
            token_value = match.group(0)
            
            if token_type == "string":
                if not in_into_clause:
                    normalized_parts.append(token_value)
            
            elif token_type == "comment_single":
                if not in_into_clause:
                    normalized_parts.append(token_value)
                    normalized_parts.append('\n')

            elif token_type == "comment_multi":
                if not in_into_clause:
                    normalized_parts.append(token_value)
            
            elif token_type == "exec_sql":
                # EXEC SQL은 normalized_sql에서 제거 (건너뜀)
                pass
            
            elif token_type == "for_clause":
                # FOR :array_size 절은 제거 (건너뜀)
                # 하지만 array_size 변수는 input으로 추출
                for_match = re.search(r':([a-zA-Z_]\w*(?:\[[^\]]+\])?)', token_value)
                if for_match:
                    input_vars.append(':' + for_match.group(1))
            
            elif token_type == "whitespace":
                if not in_into_clause:
                    normalized_parts.append(" ")
            
            elif token_type == "host_var":
                var_name = token_value
                
                # HH:MM:SS 엣지 케이스 확인
                is_time_format = False
                start_pos = match.start()
                if start_pos > 0 and raw_sql[start_pos-1].isdigit():
                     is_time_format = True
                
                if is_time_format:
                    if not in_into_clause:
                        normalized_parts.append(token_value)
                else:
                    # 인디케이터 변수 분리 (:var:ind)
                    if ':' in var_name[1:]:
                        parts = var_name.split(':')
                        main_var = ':' + parts[1]
                        indicator_var = ':' + parts[2] if len(parts) > 2 else None
                        
                        if in_into_clause:
                            output_vars.append(main_var)
                            if indicator_var:
                                output_vars.append(indicator_var)
                        else:
                            input_vars.append(main_var)
                            if indicator_var:
                                input_vars.append(indicator_var)
                            if self.naming_convention:
                                clean_name = main_var[1:].split('[')[0]  # 배열 인덱스 제거
                                alias = self.naming_convention.convert(clean_name)
                                normalized_parts.append(f"{main_var} AS {alias}")
                            else:
                                normalized_parts.append("?")
                    else:
                        if in_into_clause:
                            output_vars.append(var_name)
                        else:
                            input_vars.append(var_name)
                            if self.naming_convention:
                                clean_name = var_name[1:].split('[')[0]  # 배열 인덱스 제거
                                alias = self.naming_convention.convert(clean_name)
                                normalized_parts.append(f"{var_name} AS {alias}")
                            else:
                                normalized_parts.append("?")

            elif token_type == "into_keyword":
                if is_select_or_fetch and not is_insert:
                    in_into_clause = True
                else:
                    normalized_parts.append(token_value)
            
            elif token_type == "from_keyword":
                if in_into_clause:
                    in_into_clause = False
                    normalized_parts.append(token_value)
                else:
                    normalized_parts.append(token_value)
            
            elif token_type == "semicolon":
                if not in_into_clause:
                    if self.strip_semicolon:
                        last_token_was_semicolon = True
                    else:
                        normalized_parts.append(token_value)
            
            elif token_type == "other":
                if not in_into_clause:
                    normalized_parts.append(token_value)
        
        # 정규화된 SQL 재구성
        normalized_sql = "".join(normalized_parts).strip()
        
        # 세미콜론이 마지막에 있었고 strip_semicolon이 False면 다시 추가할 필요 없음 (이미 처리됨)
        
        # 동적 SQL 처리
        dynamic_sql_stmt = None
        if sql_type == "PREPARE":
            match = re.search(r'FROM\s+(:?\w+)', normalized_sql, re.IGNORECASE)
            if match:
                dynamic_sql_stmt = match.group(1)
        
        return {
            "type": "sql",
            "sql_type": sql_type,
            "raw_sql": raw_sql,
            "normalized_sql": normalized_sql,
            "input_host_vars": input_vars,
            "output_host_vars": output_vars,
            "dynamic_sql_stmt": dynamic_sql_stmt
        }

