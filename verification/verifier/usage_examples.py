"""
Verifier Module Usage Guide
===========================

파싱 결과 검증 모듈 사용 가이드

이 가이드는 세 가지 주요 검증 시나리오에 대한 사용법을 설명합니다:
1. 헤더 섹션 검증 (변수, 매크로, 헤더)
2. 함수 및 메타데이터 검증 (변수, SQL 추출)
3. SQL 메타데이터 검증 (input, output, alias)
"""

# ============================================================================
# 1. 헤더 섹션 검증 (Header Section Verification)
# ============================================================================
#
# 함수 선언 윗부분(#include, #define, typedef, EXEC SQL DECLARE SECTION 등)을
# 입력으로 변수/매크로/헤더가 올바르게 파싱되었는지 검증합니다.
#

def example_header_section_verification():
    """
    예제 1: 헤더 섹션 검증
    
    입력:
    - header_source: 함수 선언 이전의 소스 코드 (헤더 부분)
    - macros_data: macros.jsonl에서 로드한 매크로 분석 결과
    - includes_data: includes.jsonl에서 로드한 include 분석 결과
    - variables_data: variables.jsonl에서 전역 변수 분석 결과
    """
    from verification.verifier import ParsingVerifier, VerificationContext
    
    # 1. 검증기 생성
    verifier = ParsingVerifier()
    
    # 2. 헤더 섹션 소스 코드 (함수 선언 이전 부분)
    header_source = '''
#include <stdio.h>
#include <string.h>
#include <sqlca.h>

#define MAX_SIZE 256
#define BUFFER_LEN 1024
#define ERROR_CODE -1

EXEC SQL BEGIN DECLARE SECTION;
    char in_acct_no[11];
    char in_balance_dt[9];
    long in_min_balance;
    double out_balance_amt;
    short ind_balance_amt;
EXEC SQL END DECLARE SECTION;
'''

    # 3. 분석 결과 (실제로는 jsonl 파일에서 로드)
    macros_data = [
        {"name": "MAX_SIZE", "value": "256", "params": None},
        {"name": "BUFFER_LEN", "value": "1024", "params": None},
        {"name": "ERROR_CODE", "value": "-1", "params": None},
    ]
    
    includes_data = [
        {"type": "include", "path": "stdio.h", "is_system": True},
        {"type": "include", "path": "string.h", "is_system": True},
        {"type": "include", "path": "sqlca.h", "is_system": True},
    ]
    
    variables_data = [
        {"name": "in_acct_no", "type": "char", "array_size": "11", "scope": "global"},
        {"name": "in_balance_dt", "type": "char", "array_size": "9", "scope": "global"},
        {"name": "in_min_balance", "type": "long", "scope": "global"},
        {"name": "out_balance_amt", "type": "double", "scope": "global"},
        {"name": "ind_balance_amt", "type": "short", "scope": "global", "is_indicator": True},
    ]
    
    # 4. 컨텍스트 생성 (매크로 정보 포함 - 변수 검증에서 사용)
    context = verifier.build_context(
        macros_data=macros_data,
        headers_data=includes_data,
        variables_data=variables_data,
    )
    
    # 5. 매크로 검증 (가장 먼저 수행 - 배열 크기 해석에 필요)
    macro_result = verifier.verify_macro(
        original_source=header_source,
        analysis_result=macros_data,
        context=context,
    )
    print(f"Macro: {macro_result.summary()}")
    
    # 6. 헤더(include) 검증
    header_result = verifier.verify_header(
        original_source=header_source,
        analysis_result=includes_data,
        context=context,
    )
    print(f"Header: {header_result.summary()}")
    
    # 7. 변수 검증 (매크로 컨텍스트 사용)
    variable_result = verifier.verify_variable(
        original_source=header_source,
        analysis_result=variables_data,
        context=context,  # 매크로 정보가 여기에 포함됨
    )
    print(f"Variable: {variable_result.summary()}")
    
    # 8. 전체 결과 출력
    results = {
        "macro": macro_result,
        "header": header_result,
        "variable": variable_result,
    }
    verifier.print_summary(results)
    
    return results


# ============================================================================
# 2. 함수 및 메타데이터 검증 (Function & Metadata Verification)
# ============================================================================
#
# 함수와 함수 관련 메타데이터를 입력으로 변수/SQL이 올바르게 추출되었는지 검증합니다.
# 이 검증은 _extracted.c 파일과 functions.jsonl, sql.jsonl을 비교합니다.
#

def example_function_extraction_verification():
    """
    예제 2: 함수 및 SQL 추출 검증
    
    입력:
    - extracted_code: _extracted.c 파일 내용 (SQL이 주석으로 대체된 코드)
    - functions_data: functions.jsonl에서 로드한 함수 정보
    - sql_data: sql.jsonl에서 로드한 SQL 정보
    - local_variables: 함수 내 로컬 변수 정보
    """
    from verification.verifier import ParsingVerifier
    
    # 1. 검증기 생성
    verifier = ParsingVerifier()
    
    # 2. 추출된 코드 (_extracted.c 내용)
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

int validate_input(char *input) {
    /* SQL: sql_003 - Validation query */
    return 0;
}
'''

    # 3. 함수 분석 결과
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
        {
            "name": "validate_input",
            "return_type": "int",
            "params": [{"name": "input", "type": "char *"}],
            "sql_ids": ["sql_003"],
            "local_variables": [],
        },
    ]
    
    # 4. SQL 분석 결과
    sql_data = [
        {"sql_id": "sql_001", "function": "process_balance_query", "sql_type": "SELECT"},
        {"sql_id": "sql_002", "function": "process_balance_query", "sql_type": "UPDATE"},
        {"sql_id": "sql_003", "function": "validate_input", "sql_type": "SELECT"},
    ]
    
    # 5. 컨텍스트 생성
    context = verifier.build_context(
        functions_data=functions_data,
        sql_data=sql_data,
    )
    
    # 6. SQL 추출 검증
    sql_extraction_result = verifier.verify_sql_extraction(
        extracted_code=extracted_code,
        analysis_result={
            "sql_ids": [s["sql_id"] for s in sql_data],
            "functions": functions_data,
            "local_variables": [
                var 
                for func in functions_data 
                for var in func.get("local_variables", [])
            ],
        },
        context=context,
    )
    
    print(f"SQL Extraction: {sql_extraction_result.summary()}")
    
    # 7. 이슈 상세 출력
    if sql_extraction_result.issues:
        print("\nIssues found:")
        for issue in sql_extraction_result.issues:
            print(f"  - [{issue.severity}] {issue.message}")
    
    return sql_extraction_result


# ============================================================================
# 3. SQL 메타데이터 검증 (SQL Metadata Verification)
# ============================================================================
#
# 함수별 추출된 SQL들을 입력으로 input, output, alias가 올바르게 처리되었는지 검증합니다.
#

def example_sql_metadata_verification():
    """
    예제 3: SQL 메타데이터 검증
    
    입력:
    - sql_content: 원본 SQL 구문
    - sql_metadata: sql.jsonl의 개별 엔트리 (input_host_vars, output_host_vars, alias 등)
    """
    from verification.verifier import ParsingVerifier
    
    # 1. 검증기 생성
    verifier = ParsingVerifier()
    
    # 2. 원본 SQL 구문
    sql_content = '''
SELECT
    a.acct_no,
    a.acct_nm AS account_name,
    b.balance_amt,
    CASE WHEN b.balance_amt > 1000000 THEN 'VIP' ELSE 'NORMAL' END AS grade
INTO
    :out_acct_no,
    :out_acct_nm,
    :out_balance_amt :ind_balance_amt,
    :out_grade
FROM
    ACCOUNT a
    INNER JOIN BALANCE b ON a.acct_no = b.acct_no
WHERE
    a.acct_no = :in_acct_no
    AND b.balance_dt = :in_balance_dt
'''

    # 3. SQL 메타데이터 분석 결과
    sql_metadata = {
        "sql_id": "sql_001",
        "function": "process_balance_query",
        "sql_type": "SELECT",
        "raw_content": sql_content,
        
        # 입력 호스트 변수
        "input_host_vars": [":in_acct_no", ":in_balance_dt"],
        
        # 출력 호스트 변수 (인디케이터 포함)
        "output_host_vars": [
            ":out_acct_no",
            ":out_acct_nm",
            ":out_balance_amt",
            ":out_grade",
        ],
        
        # 인디케이터 변수
        "indicator_vars": {
            ":out_balance_amt": ":ind_balance_amt",
        },
        
        # Alias 정보
        "aliases": [
            {"column": "a.acct_nm", "alias": "account_name"},
            {"column": "CASE WHEN b.balance_amt > 1000000 THEN 'VIP' ELSE 'NORMAL' END", "alias": "grade"},
        ],
        
        # MyBatis 변환 SQL
        "mybatis_sql": '''
SELECT
    a.acct_no,
    a.acct_nm AS account_name,
    b.balance_amt,
    CASE WHEN b.balance_amt > 1000000 THEN 'VIP' ELSE 'NORMAL' END AS grade
FROM
    ACCOUNT a
    INNER JOIN BALANCE b ON a.acct_no = b.acct_no
WHERE
    a.acct_no = #{inAcctNo, jdbcType=VARCHAR}
    AND b.balance_dt = #{inBalanceDt, jdbcType=VARCHAR}
''',
    }
    
    # 4. SQL 메타데이터 검증
    sql_result = verifier.verify_sql_metadata(
        sql_content=sql_content,
        analysis_result=sql_metadata,
    )
    
    print(f"SQL Metadata: {sql_result.summary()}")
    
    # 5. 상세 결과 출력
    if sql_result.issues:
        print("\nIssues found:")
        for issue in sql_result.issues:
            print(f"  - [{issue.severity}] {issue.category}: {issue.message}")
            if issue.expected:
                print(f"    Expected: {issue.expected}")
            if issue.actual:
                print(f"    Actual: {issue.actual}")
    
    return sql_result


# ============================================================================
# 전체 검증 (Full Verification from Directory)
# ============================================================================

def example_full_verification_from_directory():
    """
    예제 4: 디렉토리 기반 전체 검증
    
    출력 디렉토리의 모든 jsonl 파일을 로드하여 전체 검증을 수행합니다.
    """
    from verification.verifier import ParsingVerifier
    from pathlib import Path
    
    # 1. 검증기 생성
    verifier = ParsingVerifier()
    
    # 2. 파일 경로
    source_file = "test.sqc"
    extracted_file = "testoutput/test_extracted.c"
    output_dir = "testoutput"
    
    # 3. 소스 파일 읽기
    with open(source_file, 'r', encoding='utf-8') as f:
        original_source = f.read()
    
    with open(extracted_file, 'r', encoding='utf-8') as f:
        extracted_code = f.read()
    
    # 4. 전체 검증 수행
    results = verifier.verify_all(
        original_source=original_source,
        extracted_code=extracted_code,
        output_dir=output_dir,
    )
    
    # 5. 결과 요약 출력
    verifier.print_summary(results)
    
    # 6. JSON 형식으로 결과 저장
    import json
    
    results_json = {
        vtype: result.to_dict()
        for vtype, result in results.items()
    }
    
    with open("verification_results.json", 'w', encoding='utf-8') as f:
        json.dump(results_json, f, indent=2, ensure_ascii=False)
    
    return results


# ============================================================================
# 실행 예제
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Example 1: Header Section Verification")
    print("=" * 60)
    example_header_section_verification()
    
    print("\n" + "=" * 60)
    print("Example 2: Function & SQL Extraction Verification")
    print("=" * 60)
    example_function_extraction_verification()
    
    print("\n" + "=" * 60)
    print("Example 3: SQL Metadata Verification")
    print("=" * 60)
    example_sql_metadata_verification()
