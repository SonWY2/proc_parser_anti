# Verifier Module Usage Guide

파싱 결과 검증 모듈 사용 가이드입니다.

---

## 목차

1. [헤더 섹션 검증](#1-헤더-섹션-검증) - 변수/매크로/헤더 파싱 검증
2. [함수 및 메타데이터 검증](#2-함수-및-메타데이터-검증) - 변수/SQL 추출 검증
3. [SQL 메타데이터 검증 (규칙 기반)](#3-sql-메타데이터-검증-규칙-기반) - 정규식 기반 검증
4. [LLM 기반 SQL 검증](#4-llm-기반-sql-검증) - LLM을 이용한 정밀 검증

---

## 1. 헤더 섹션 검증

함수 선언 윗부분(#include, #define, EXEC SQL DECLARE SECTION 등)을 입력으로 **변수/매크로/헤더**가 올바르게 파싱되었는지 검증합니다.

### 입력 데이터

| 입력 | 설명 | 파일 |
|------|------|------|
| `header_source` | 함수 선언 이전의 소스 코드 | 원본 .sqc 파일 |
| `macros_data` | 매크로 분석 결과 | `macros.jsonl` |
| `includes_data` | include 분석 결과 | `includes.jsonl` |
| `variables_data` | 전역 변수 분석 결과 | `variables.jsonl` (scope="global") |

### 사용 예제

```python
from verification.verifier import ParsingVerifier

# 1. 검증기 생성
verifier = ParsingVerifier()

# 2. 헤더 섹션 소스 코드 (함수 선언 이전 부분)
header_source = '''
#include <stdio.h>
#include <sqlca.h>

#define MAX_SIZE 256
#define ERROR_CODE -1

EXEC SQL BEGIN DECLARE SECTION;
    char in_acct_no[11];
    double out_balance_amt;
    short ind_balance_amt;
EXEC SQL END DECLARE SECTION;
'''

# 3. 분석 결과 로드 (실제로는 jsonl 파일에서)
macros_data = [
    {"name": "MAX_SIZE", "value": "256", "params": None},
    {"name": "ERROR_CODE", "value": "-1", "params": None},
]

includes_data = [
    {"type": "include", "path": "stdio.h", "is_system": True},
    {"type": "include", "path": "sqlca.h", "is_system": True},
]

variables_data = [
    {"name": "in_acct_no", "type": "char", "array_size": "11", "scope": "global"},
    {"name": "out_balance_amt", "type": "double", "scope": "global"},
    {"name": "ind_balance_amt", "type": "short", "scope": "global", "is_indicator": True},
]

# 4. 컨텍스트 생성 (매크로 정보 포함)
context = verifier.build_context(
    macros_data=macros_data,
    headers_data=includes_data,
    variables_data=variables_data,
)

# 5. 검증 수행 (순서 중요: 매크로 → 헤더 → 변수)
macro_result = verifier.verify_macro(
    original_source=header_source,
    analysis_result=macros_data,
    context=context,
)

header_result = verifier.verify_header(
    original_source=header_source,
    analysis_result=includes_data,
    context=context,
)

variable_result = verifier.verify_variable(
    original_source=header_source,
    analysis_result=variables_data,
    context=context,  # 매크로 정보가 배열 크기 해석에 사용됨
)

# 6. 결과 출력
print(macro_result.summary())    # ✅ macro: 2/2 passed, 0 errors
print(header_result.summary())   # ✅ header: 2/2 passed, 0 errors
print(variable_result.summary()) # ✅ variable: 3/3 passed, 0 errors
```

### 매크로 컨텍스트 활용

변수 검증 시 매크로 상수가 배열 크기에 사용된 경우 자동으로 해석됩니다:

```python
# 원본: char buffer[MAX_SIZE];
# MAX_SIZE가 256으로 정의된 경우

# 컨텍스트에서 매크로 값 조회
value = context.get_macro_value("MAX_SIZE")  # "256"

# 배열 크기 검증 시 자동 해석
# expected: "MAX_SIZE" (resolved: 256)
# actual: "256" (resolved: 256)
# -> PASS
```

---

## 2. 함수 및 메타데이터 검증

함수와 관련 메타데이터를 입력으로 **변수/SQL이 올바르게 추출**되었는지 검증합니다.

### 입력 데이터

| 입력 | 설명 | 파일 |
|------|------|------|
| `extracted_code` | SQL이 주석으로 대체된 코드 | `*_extracted.c` |
| `functions_data` | 함수 정보 (이름, 파라미터, sql_ids) | `functions.jsonl` |
| `sql_data` | SQL 정보 (sql_id, 함수 연결) | `sql.jsonl` |
| `local_variables` | 함수 내 로컬 변수 | `variables.jsonl` (scope="local") |

### 사용 예제

```python
from verification.verifier import ParsingVerifier

verifier = ParsingVerifier()

# 1. 추출된 코드 (_extracted.c 내용)
extracted_code = '''
int process_balance_query(char *acct_no) {
    int result = 0;
    char temp_buffer[256];
    
    /* SQL: sql_001 - SELECT balance query */
    
    if (result == 0) {
        /* SQL: sql_002 - UPDATE balance */
    }
    
    return result;
}
'''

# 2. 함수 분석 결과
functions_data = [
    {
        "name": "process_balance_query",
        "return_type": "int",
        "params": [{"name": "acct_no", "type": "char *"}],
        "sql_ids": ["sql_001", "sql_002"],
        "local_variables": [
            {"name": "result", "type": "int"},
            {"name": "temp_buffer", "type": "char", "array_size": "256"},
        ],
    },
]

# 3. SQL 분석 결과
sql_data = [
    {"sql_id": "sql_001", "function": "process_balance_query", "sql_type": "SELECT"},
    {"sql_id": "sql_002", "function": "process_balance_query", "sql_type": "UPDATE"},
]

# 4. 컨텍스트 생성
context = verifier.build_context(
    functions_data=functions_data,
    sql_data=sql_data,
)

# 5. SQL 추출 검증
result = verifier.verify_sql_extraction(
    extracted_code=extracted_code,
    analysis_result={
        "sql_ids": ["sql_001", "sql_002"],
        "functions": functions_data,
        "local_variables": functions_data[0]["local_variables"],
    },
    context=context,
)

print(result.summary())  # ✅ sql_extraction: 2/2 passed, 0 errors

# 6. 이슈 확인
for issue in result.issues:
    print(f"[{issue.severity}] {issue.message}")
```

### 검증 항목

- ✅ 모든 EXEC SQL 문이 추출되었는지 확인
- ✅ SQL이 올바른 주석 형식(`/* SQL: xxx */`)으로 대체되었는지 확인
- ✅ SQL ID가 함수와 올바르게 연결되었는지 확인
- ✅ 로컬 변수가 누락 없이 추출되었는지 확인
- ✅ 추출 후 남은 코드에 미추출된 SQL이 없는지 확인

---

## 3. SQL 메타데이터 검증

함수별 추출된 SQL들을 입력으로 **input, output, alias가 올바르게 처리**되었는지 검증합니다.

> **Note**: 함수 하나에 여러 SQL이 존재할 수 있으므로, `verify_function_sql_metadata`를 사용하여 리스트로 받아 일괄 검증합니다.

### 입력 데이터

| 입력 | 설명 | 파일 |
|------|------|------|
| `function_name` | 함수 이름 | `functions.jsonl`의 `name` |
| `sql_list` | 해당 함수의 SQL 분석 결과 리스트 | `sql.jsonl` (function 필터링) |

### 사용 예제

```python
from verification.verifier import ParsingVerifier

verifier = ParsingVerifier()

# 1. 함수 이름
function_name = "process_balance_query"

# 2. 해당 함수의 SQL 분석 결과 리스트 (여러 SQL)
sql_list = [
    {
        "sql_id": "sql_001",
        "function": "process_balance_query",
        "sql_type": "SELECT",
        "raw_content": '''
SELECT a.acct_no, a.acct_nm AS account_name
INTO :out_acct_no, :out_acct_nm
FROM ACCOUNT a
WHERE a.acct_no = :in_acct_no
''',
        "input_host_vars": [":in_acct_no"],
        "output_host_vars": [":out_acct_no", ":out_acct_nm"],
        "mybatis_sql": "SELECT ... WHERE a.acct_no = #{inAcctNo}",
    },
    {
        "sql_id": "sql_002",
        "function": "process_balance_query",
        "sql_type": "UPDATE",
        "raw_content": '''
UPDATE ACCOUNT SET LAST_LOGIN = SYSDATE
WHERE ACCT_NO = :in_acct_no
''',
        "input_host_vars": [":in_acct_no"],
        "output_host_vars": [],
        "mybatis_sql": "UPDATE ... WHERE ACCT_NO = #{inAcctNo}",
    },
]

# 3. 함수별 SQL 메타데이터 일괄 검증
result = verifier.verify_function_sql_metadata(
    function_name=function_name,
    sql_list=sql_list,
)

print(result.summary())  # ✅ sql_metadata: 2/2 passed, 0 errors

# 4. 상세 이슈 확인
for issue in result.issues:
    print(f"[{issue.severity}] {issue.category}: {issue.message}")
```

### 단일 SQL 검증 (선택)

개별 SQL을 검증하려면 `verify_sql_metadata`를 직접 호출할 수 있습니다:

```python
result = verifier.verify_sql_metadata(
    sql_content=sql_metadata["raw_content"],
    analysis_result=sql_metadata,
)
```

### 검증 항목

| 항목 | 설명 |
|------|------|
| `input_host_vars` | WHERE, SET 절 등에서 사용된 모든 입력 호스트 변수(`:in_xxx`) 추출 확인 |
| `output_host_vars` | INTO 절의 모든 출력 변수(`:out_xxx`) 추출 확인 |
| `indicator_vars` | 인디케이터 변수(`:ind_xxx`) 매핑 확인 |
| `aliases` | SELECT 컬럼 alias가 올바르게 분석되었는지 확인 |
---

## 4. LLM 기반 검증 (전체 단계)

LLM을 사용하여 **모든 검증 단계**(헤더/매크로/변수, SQL 추출, SQL 메타데이터)를 정밀하게 수행합니다.

### 환경 설정

```bash
set OPENAI_API_KEY=your-api-key-here
```

또는 테스트 스크립트(`test_llm_verifier.py`) 상단에서 직접 설정:
```python
API_KEY = "your-api-key"
MODEL_NAME = "gpt-4o-mini"
ENDPOINT = "https://api.openai.com/v1"
```

### LLM 검증기 목록

| 플러그인 | 검증 항목 | 용도 |
|---------|----------|------|
| `LLMHeaderVerifier` | 매크로, 헤더, 변수 선언 | 1) 헤더 섹션 파싱 검증 |
| `LLMSQLExtractionVerifier` | SQL 추출, 함수 매핑, 로컬 변수 | 2) 함수/SQL 추출 검증 |
| `LLMSQLMetadataVerifier` | Input/Output 변수, Alias, MyBatis | 3) SQL 메타데이터 검증 |

### 사용 예제

```python
from verification.verifier.llm_client import LLMClient
from verification.verifier.plugins.llm_header_verifier import LLMHeaderVerifier
from verification.verifier.plugins.llm_sql_extraction_verifier import LLMSQLExtractionVerifier
from verification.verifier.plugins.llm_sql_metadata_verifier import LLMSQLMetadataVerifier
from verification.verifier.types import VerificationInput, VerificationType

# LLM 클라이언트 생성
llm_client = LLMClient(api_key="your-key", model="gpt-4o-mini")

# 1) 헤더 섹션 검증
header_verifier = LLMHeaderVerifier(llm_client)
result = header_verifier.verify(VerificationInput(
    verification_type=VerificationType.HEADER,
    original_source=header_source,
    analysis_result={"macros": [...], "includes": [...], "variables": [...]}
))

# 2) SQL 추출 검증
extraction_verifier = LLMSQLExtractionVerifier(llm_client)
result = extraction_verifier.verify(VerificationInput(
    verification_type=VerificationType.SQL_EXTRACTION,
    original_source=extracted_code,
    analysis_result={"functions": [...], "sql_ids": [...]}
))

# 3) SQL 메타데이터 검증
metadata_verifier = LLMSQLMetadataVerifier(llm_client)
result = metadata_verifier.verify(VerificationInput(
    verification_type=VerificationType.SQL_METADATA,
    original_source=raw_sql,
    analysis_result={"input_host_vars": [...], "output_host_vars": [...], "mybatis_sql": "..."}
))
```

### 통합 테스트

```bash
python test_llm_verifier.py
```

모든 LLM 검증기를 한번에 테스트하며, 의도적으로 오류가 포함된 샘플 데이터로 에러 탐지를 확인합니다.


---

## 전체 검증 (디렉토리 기반)

출력 디렉토리의 모든 jsonl 파일을 로드하여 전체 검증을 한 번에 수행합니다.

```python
from verification.verifier import ParsingVerifier

verifier = ParsingVerifier()

# 소스 파일 로드
with open("test.sqc", 'r', encoding='utf-8') as f:
    original_source = f.read()

with open("testoutput/test_extracted.c", 'r', encoding='utf-8') as f:
    extracted_code = f.read()

# 전체 검증 수행
results = verifier.verify_all(
    original_source=original_source,
    extracted_code=extracted_code,
    output_dir="testoutput",
)

# 결과 요약 출력
verifier.print_summary(results)
```

**출력 예시:**

```
============================================================
Verification Summary
============================================================
✅ macro: 3/3 passed, 0 errors, 0 warnings
✅ header: 5/5 passed, 0 errors, 0 warnings
✅ variable: 18/18 passed, 0 errors, 2 warnings
✅ sql_extraction: 40/40 passed, 0 errors, 0 warnings
✅ sql_metadata: 40/40 passed, 0 errors, 1 warnings
------------------------------------------------------------
✅ All verifications passed! (3 warnings)
============================================================
```

---

## 검증 결과 구조

```python
@dataclass
class VerificationResult:
    verification_type: VerificationType  # macro, header, variable, etc.
    status: VerificationStatus           # pass, fail, warning, skipped
    total_items: int                     # 총 검증 항목 수
    passed_items: int                    # 통과한 항목 수
    failed_items: int                    # 실패한 항목 수
    issues: List[VerificationIssue]      # 발견된 이슈 목록
    details: Dict[str, Any]              # 추가 상세 정보

@dataclass
class VerificationIssue:
    issue_id: str           # 이슈 고유 ID
    severity: str           # error, warning, info
    category: str           # missing, incorrect, extra, mismatch
    message: str            # 이슈 메시지
    expected: str           # 기대값
    actual: str             # 실제값
    line_number: int        # 관련 라인 번호
    suggestion: str         # 수정 제안
```

---

## 추가 참고

- 코드 예제: [usage_examples.py](./usage_examples.py)
- 플러그인 구현: [plugins/](./plugins/)
- 타입 정의: [types.py](./types.py)
