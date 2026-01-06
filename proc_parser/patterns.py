"""
Pro*C 파싱에 사용되는 정규식 패턴들을 정의한 모듈입니다.
Include, 매크로, SQL 블록, 호스트 변수 등을 탐지하는 패턴을 포함합니다.
"""
import re

# Include: #include <...> 또는 #include "..."
# 캡처: quote_type (< 또는 "), path, quote_type (> 또는 ")
PATTERN_INCLUDE = re.compile(r'#include\s+([<"])(.*?)([>"])')

# Macro: #define NAME VALUE
# 캡처: name, value (옵션)
PATTERN_MACRO = re.compile(r'#define\s+(\w+)(?:\s+(.*?))?$', re.MULTILINE)

# SQL Block: EXEC SQL ... ;
# 여러 줄에 걸쳐 매칭하기 위해 DOTALL 사용.
# 캡처: EXEC SQL ... ; 내부의 내용
PATTERN_SQL = re.compile(r'EXEC\s+SQL\s+(.*?);', re.DOTALL | re.IGNORECASE)

# Special Construct: BAMCALL(...)
# 캡처: BAMCALL(...) 내부의 인자
PATTERN_BAMCALL = re.compile(r'BAMCALL\s*\((.*?)\);', re.DOTALL)

# SQL 내의 호스트 변수: :var
# 엣지 케이스 처리:
# 1. 문자열 내부 매칭을 피하기 위한 부정형 후방 탐색 (단순화된 확인)
# 2. 콜론 뒤에 유효한 식별자 확인
# 참고: 전체 문맥 인식 파서가 더 좋지만, 정규식으로 근사할 수 있습니다.
# 여기서는 더 간단한 정규식을 사용하고 변환기 로직에서 다듬을 것입니다.
PATTERN_HOST_VAR = re.compile(r':([a-zA-Z_]\w*)')

# 주석
PATTERN_COMMENT_SINGLE = re.compile(r'//.*')
PATTERN_COMMENT_MULTI = re.compile(r'/\*.*?\*/', re.DOTALL)

# 함수 정의 (C에 대한 휴리스틱)
# ReturnType FunctionName(Args) { ... }
# 정규식으로는 매우 어렵고, Tree-sitter에 의존하는 것이 좋습니다.
# 하지만 폴백이나 빠른 확인이 필요할 수 있습니다.

# 변수 선언 (휴리스틱)
# Type Name; 또는 Type Name = Value;

# Array DML 패턴 (FOR 절)
# EXEC SQL FOR :array_size INSERT/UPDATE/DELETE ...
PATTERN_ARRAY_DML = re.compile(
    r'EXEC\s+SQL\s+FOR\s+:?\w+\s+(INSERT|UPDATE|DELETE).*?;',
    re.IGNORECASE | re.DOTALL
)

# DECLARE SECTION 패턴
# EXEC SQL BEGIN DECLARE SECTION; ... EXEC SQL END DECLARE SECTION;
PATTERN_DECLARE_SECTION = re.compile(
    r'EXEC\s+SQL\s+BEGIN\s+DECLARE\s+SECTION\s*;(.*?)EXEC\s+SQL\s+END\s+DECLARE\s+SECTION\s*;',
    re.DOTALL | re.IGNORECASE
)

