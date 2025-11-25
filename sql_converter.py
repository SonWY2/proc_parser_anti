"""
Pro*C SQL 문을 표준 SQL로 변환하고 호스트 변수를 처리하는 모듈입니다.
호스트 변수 추출, 플레이스홀더 대체, 네이밍 컨벤션 적용 등을 수행합니다.
"""
import re
from patterns import PATTERN_HOST_VAR
from plugins.naming_convention import NamingConventionPlugin

class SQLConverter:
    def __init__(self, naming_convention: NamingConventionPlugin = None):
        self.naming_convention = naming_convention

    def normalize_sql(self, raw_sql):
        """
        Pro*C SQL을 표준 SQL로 변환합니다.
        호스트 변수를 추출하고 플레이스홀더로 대체합니다.
        네이밍 컨벤션 플러그인이 제공되면 AS 구문을 사용하여 호스트 변수에 별칭을 지정합니다.
        """
        # 단일 라인 주석을 올바르게 처리하기 위해 raw_sql을 직접 처리합니다.
        # 미리 줄바꿈을 없애면 단일 라인 주석(-- ...)이 망가집니다.
        
        # SQL 타입 결정 (먼저 원시 문자열에 대한 간단한 확인, 주석 처리된 경우 부정확할 수 있지만
        # 대개 EXEC SQL은 시작 부분에 있음)
        # 필요한 경우 토큰화 후 타입 감지를 개선할 수 있지만 지금은 간단하게 유지합니다.
        # 타입 감지를 위해 정리 (EXEC SQL 제거)
        clean_for_type = re.sub(r'\s+', ' ', raw_sql).strip()
        type_check_sql = re.sub(r'^EXEC\s+SQL\s+', '', clean_for_type, flags=re.IGNORECASE).strip()
        first_word = type_check_sql.split(' ')[0].upper()
        
        sql_type = "UNKNOWN"
        if first_word in ["SELECT", "INSERT", "UPDATE", "DELETE", "DECLARE", "OPEN", "FETCH", "CLOSE", "PREPARE", "EXECUTE", "CONNECT", "COMMIT", "ROLLBACK", "ALTER"]:
            sql_type = first_word
        
        input_vars = []
        output_vars = []
        
        # 토큰화를 위한 Regex
        # 1. 문자열: '...' (이스케이프된 따옴표 '' 처리)
        # 2. 주석: --... (줄바꿈까지) 또는 /*...*/
        # 3. 호스트 변수: :var
        # 4. INTO 절 키워드
        # 5. FROM 키워드
        # 6. 공백 (정규화용)
        # 7. 기타 텍스트
        
        # 참고: 여러 줄 일치를 위해 re.DOTALL을 사용하지만 -- 주석에 주의해야 합니다.
        # -- 주석은 줄바꿈과 일치해서는 안 됩니다.
        # 따라서 특정 정규식을 사용합니다.
        
        token_pattern = re.compile(
            r"(?P<string>'([^']|'')*')|"
            r"(?P<comment_single>--[^\n]*)|"
            r"(?P<comment_multi>/\*[\s\S]*?\*/)|"
            r"(?P<host_var>:[a-zA-Z_]\w*)|"
            r"(?P<into_keyword>\bINTO\b)|"
            r"(?P<from_keyword>\bFROM\b)|"
            r"(?P<whitespace>\s+)|"
            r"(?P<other>.)",
            re.IGNORECASE | re.DOTALL
        )
        
        normalized_parts = []
        
        is_select_or_fetch = sql_type in ["SELECT", "FETCH"]
        is_insert = sql_type == "INSERT"
        
        iterator = token_pattern.finditer(raw_sql)
        
        in_into_clause = False
        
        for match in iterator:
            token_type = match.lastgroup
            token_value = match.group(0)
            
            if token_type == "string":
                if not in_into_clause:
                    normalized_parts.append(token_value)
            
            elif token_type == "comment_single":
                if not in_into_clause:
                    normalized_parts.append(token_value)
                    # 소비되었다면 줄바꿈을 추가해야 할까요?
                    # 정규식 --[^\n]*은 줄바꿈을 소비하지 않습니다 (EOF 제외).
                    # 하지만 공백 정규식이 다음 줄바꿈을 소비할 수 있습니다.
                    # 공백을 스페이스로 정규화하면 주석을 다음 줄과 병합할 수 있습니다.
                    # 예: -- comment \n SELECT
                    # -- comment 는 "-- comment "와 일치
                    # \n 은 공백 -> " "과 일치
                    # 결과: -- comment  SELECT
                    # 이것은 효과적으로 SELECT를 주석 처리합니다!
                    # 따라서 단일 라인 주석의 경우 끝에 줄바꿈을 보존해야 합니다.
                    normalized_parts.append('\n')

            elif token_type == "comment_multi":
                if not in_into_clause:
                    normalized_parts.append(token_value)
            
            elif token_type == "whitespace":
                if not in_into_clause:
                    # 단일 스페이스로 정규화
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
                    if in_into_clause:
                        output_vars.append(var_name)
                    else:
                        input_vars.append(var_name)
                        if self.naming_convention:
                            clean_name = var_name[1:]
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
            
            elif token_type == "other":
                if not in_into_clause:
                    normalized_parts.append(token_value)
        
        # 정규화된 SQL 재구성
        # 여분의 공백이나 줄바꿈이 있을 수 있지만 깨진 SQL보다는 낫습니다.
        normalized_sql = "".join(normalized_parts).strip()
        # 다시 여러 공백을 정리할까요?
        # normalized_sql = re.sub(r'\s+', ' ', normalized_sql) 
        # 아니요, 그러면 단일 라인 주석이 다시 망가집니다!
        # 우리가 추가한 줄바꿈을 존중해야 합니다.
        
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

