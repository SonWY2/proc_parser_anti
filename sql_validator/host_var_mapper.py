"""
호스트 변수 매핑 모듈

Pro*C 호스트 변수와 MyBatis 파라미터 간의 매핑을 분석합니다.
"""

import re
from typing import List, Tuple, Dict, Set
from loguru import logger


# 패턴 정의
PROC_HOST_VAR_PATTERN = re.compile(r':([a-zA-Z_][a-zA-Z0-9_]*)(?::([a-zA-Z_][a-zA-Z0-9_]*))?')
MYBATIS_PARAM_PATTERN = re.compile(r'[#$]\{([a-zA-Z_][a-zA-Z0-9_]*)\}')


def extract_host_variables(sql: str) -> List[str]:
    """
    Pro*C SQL에서 호스트 변수를 추출합니다.
    
    Args:
        sql: Pro*C SQL 문자열
        
    Returns:
        호스트 변수 이름 리스트 (순서 유지)
    """
    # 문자열 리터럴 제거
    sql_no_strings = re.sub(r"'[^']*'", '', sql)
    sql_no_strings = re.sub(r'"[^"]*"', '', sql_no_strings)
    
    matches = PROC_HOST_VAR_PATTERN.findall(sql_no_strings)
    # 첫 번째 그룹만 추출 (indicator 변수 제외)
    return [m[0] for m in matches if m[0]]


def extract_mybatis_params(sql: str) -> List[str]:
    """
    MyBatis SQL에서 파라미터를 추출합니다.
    
    Args:
        sql: MyBatis SQL 문자열
        
    Returns:
        파라미터 이름 리스트 (순서 유지)
    """
    # 문자열 리터럴 제거
    sql_no_strings = re.sub(r"'[^']*'", '', sql)
    sql_no_strings = re.sub(r'"[^"]*"', '', sql_no_strings)
    
    return MYBATIS_PARAM_PATTERN.findall(sql_no_strings)


def extract_variable_mapping(asis: str, tobe: str) -> List[Tuple[str, str]]:
    """
    Pro*C 호스트 변수와 MyBatis 파라미터 간 매핑을 추출합니다.
    
    순서 기반으로 매핑합니다 (첫 번째 :var → 첫 번째 #{param}).
    
    Args:
        asis: 원본 Pro*C SQL
        tobe: 변환된 MyBatis SQL
        
    Returns:
        [(':host_var', '#{mybatis_param}'), ...] 형태의 매핑 리스트
    """
    host_vars = extract_host_variables(asis)
    mybatis_params = extract_mybatis_params(tobe)
    
    mappings = []
    
    # 순서 기반 매핑
    for i, host_var in enumerate(host_vars):
        if i < len(mybatis_params):
            mappings.append((f':{host_var}', f'#{{{mybatis_params[i]}}}'))
        else:
            # MyBatis 파라미터가 부족한 경우
            mappings.append((f':{host_var}', '(없음)'))
    
    # MyBatis 파라미터가 더 많은 경우
    for i in range(len(host_vars), len(mybatis_params)):
        mappings.append(('(없음)', f'#{{{mybatis_params[i]}}}'))
    
    return mappings


def get_naming_transformation(host_var: str, mybatis_param: str) -> str:
    """
    변수명 변환 유형을 추론합니다.
    
    Args:
        host_var: Pro*C 호스트 변수명
        mybatis_param: MyBatis 파라미터명
        
    Returns:
        변환 유형 설명
    """
    if host_var == mybatis_param:
        return "동일"
    
    # snake_case → camelCase 변환 확인
    expected_camel = snake_to_camel(host_var)
    if expected_camel == mybatis_param:
        return "snake_case → camelCase"
    
    # camelCase → snake_case 변환 확인
    expected_snake = camel_to_snake(host_var)
    if expected_snake == mybatis_param:
        return "camelCase → snake_case"
    
    return "커스텀 변환"


def snake_to_camel(name: str) -> str:
    """snake_case를 camelCase로 변환"""
    components = name.split('_')
    return components[0].lower() + ''.join(x.title() for x in components[1:])


def camel_to_snake(name: str) -> str:
    """camelCase를 snake_case로 변환"""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def format_mapping_table(mappings: List[Tuple[str, str]]) -> str:
    """
    매핑 테이블을 텍스트로 포맷합니다.
    
    Args:
        mappings: 매핑 리스트
        
    Returns:
        포맷된 테이블 문자열
    """
    if not mappings:
        return "변수 매핑 없음"
    
    lines = [
        "┌─────────────────────┬─────────────────────┬───────────────────┐",
        "│   Pro*C 호스트 변수  │   MyBatis 파라미터   │      변환 유형     │",
        "├─────────────────────┼─────────────────────┼───────────────────┤"
    ]
    
    for host_var, mybatis_param in mappings:
        # 변환 유형 추론
        if host_var != '(없음)' and mybatis_param != '(없음)':
            # 변수명만 추출
            hv = host_var.lstrip(':')
            mp = mybatis_param[2:-1]  # #{..} 제거
            transform = get_naming_transformation(hv, mp)
        else:
            transform = "N/A"
        
        lines.append(f"│ {host_var:<19} │ {mybatis_param:<19} │ {transform:<17} │")
    
    lines.append("└─────────────────────┴─────────────────────┴───────────────────┘")
    
    return '\n'.join(lines)


def analyze_variable_mapping(asis: str, tobe: str) -> Dict:
    """
    변수 매핑을 분석하고 요약 정보를 반환합니다.
    
    Args:
        asis: 원본 Pro*C SQL
        tobe: 변환된 MyBatis SQL
        
    Returns:
        분석 결과 딕셔너리
    """
    mappings = extract_variable_mapping(asis, tobe)
    host_vars = extract_host_variables(asis)
    mybatis_params = extract_mybatis_params(tobe)
    
    return {
        'mappings': mappings,
        'host_var_count': len(host_vars),
        'mybatis_param_count': len(mybatis_params),
        'matched': len(host_vars) == len(mybatis_params),
        'table': format_mapping_table(mappings)
    }
