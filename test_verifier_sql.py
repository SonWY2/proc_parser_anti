"""
SQL Metadata Verifier 테스트

test_sample_error의 SQL 데이터를 사용하여 SQL 메타데이터 검증 테스트를 수행합니다.
의도적으로 잘못된 분석 결과를 검증하여 에러가 올바르게 탐지되는지 확인합니다.

예상되는 에러:
- sql_001: input_host_vars 누락 (:in_cust_id)
- sql_001: output_host_vars 누락 (:ind_cust_name - 인디케이터)
- sql_001: mybatis_sql 변환 실패 (:in_cust_id가 #{} 형식으로 변환되지 않음)
"""

import json
from pathlib import Path

from verification.verifier import ParsingVerifier


def load_sql_jsonl(filepath: str):
    """sql.jsonl 파일을 로드하여 리스트로 반환"""
    sql_list = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                sql_list.append(json.loads(line))
    return sql_list


def test_sql_metadata_verification():
    """SQL 메타데이터 검증 테스트"""
    print("=" * 60)
    print("SQL Metadata Verification Test")
    print("=" * 60)
    
    # 1. 경로 설정
    base_dir = Path(__file__).parent / "verification" / "test_sample_error"
    sql_file = base_dir / "sql.jsonl"
    
    # 2. SQL 데이터 로드
    sql_list = load_sql_jsonl(str(sql_file))
    print(f"\nLoaded {len(sql_list)} SQL statements from {sql_file.name}")
    
    # 3. 검증기 생성
    verifier = ParsingVerifier()
    
    # 4. 함수별 SQL 그룹화
    sql_by_function = {}
    for sql in sql_list:
        func_name = sql.get("function", "unknown")
        if func_name not in sql_by_function:
            sql_by_function[func_name] = []
        sql_by_function[func_name].append(sql)
    
    print(f"Found {len(sql_by_function)} functions with SQL statements")
    
    # 5. 함수별 SQL 메타데이터 검증
    all_results = {}
    for func_name, func_sql_list in sql_by_function.items():
        print(f"\n--- Verifying function: {func_name} ({len(func_sql_list)} SQLs) ---")
        
        result = verifier.verify_function_sql_metadata(
            function_name=func_name,
            sql_list=func_sql_list,
        )
        all_results[func_name] = result
        
        # 결과 출력
        print(f"Status: {result.status.value}")
        print(f"Passed: {result.passed_items}/{result.total_items}")
        
        if result.issues:
            print("\nIssues found:")
            for issue in result.issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                print(f"  {icon} [{issue.severity}] {issue.message}")
                if issue.expected:
                    print(f"      Expected: {issue.expected}")
                if issue.actual:
                    print(f"      Actual: {issue.actual}")
    
    # 6. 전체 요약
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    total_errors = 0
    total_warnings = 0
    for func_name, result in all_results.items():
        errors = len(result.get_errors())
        warnings = len(result.get_warnings())
        total_errors += errors
        total_warnings += warnings
        
        status_icon = "✅" if errors == 0 else "❌"
        print(f"{status_icon} {func_name}: {result.passed_items}/{result.total_items} passed, {errors} errors, {warnings} warnings")
    
    print("-" * 60)
    if total_errors == 0:
        print(f"✅ All SQL metadata verifications passed! ({total_warnings} warnings)")
    else:
        print(f"❌ {total_errors} errors, {total_warnings} warnings found")
    print("=" * 60)
    
    return all_results


def test_individual_sql_verification():
    """개별 SQL 검증 테스트"""
    print("\n" + "=" * 60)
    print("Individual SQL Verification Test")
    print("=" * 60)
    
    verifier = ParsingVerifier()
    
    # 테스트 케이스: 올바른 분석 결과
    correct_sql = {
        "sql_id": "sql_test",
        "function": "test_function",
        "sql_type": "SELECT",
        "raw_content": "SELECT NAME INTO :out_name FROM USER WHERE ID = :in_id",
        "input_host_vars": [":in_id"],
        "output_host_vars": [":out_name"],
        "mybatis_sql": "SELECT NAME FROM USER WHERE ID = #{inId}",
    }
    
    print("\n[Test Case 1] Correct SQL analysis")
    result = verifier.verify_sql_metadata(
        sql_content=correct_sql["raw_content"],
        analysis_result=correct_sql,
    )
    print(f"Status: {result.status.value}")
    print(f"Issues: {len(result.issues)}")
    
    # 테스트 케이스: 잘못된 분석 결과
    wrong_sql = {
        "sql_id": "sql_wrong",
        "function": "test_function",
        "sql_type": "SELECT",
        "raw_content": "SELECT NAME INTO :out_name FROM USER WHERE ID = :in_id",
        "input_host_vars": [],  # 누락
        "output_host_vars": [],  # 누락
        "mybatis_sql": "SELECT NAME FROM USER WHERE ID = :in_id",  # 변환 안됨
    }
    
    print("\n[Test Case 2] Wrong SQL analysis (missing vars, unconverted mybatis)")
    result = verifier.verify_sql_metadata(
        sql_content=wrong_sql["raw_content"],
        analysis_result=wrong_sql,
    )
    print(f"Status: {result.status.value}")
    print(f"Issues: {len(result.issues)}")
    for issue in result.issues:
        print(f"  - [{issue.severity}] {issue.message}")


if __name__ == "__main__":
    # 메인 테스트 실행
    test_sql_metadata_verification()
    
    # 개별 SQL 테스트
    test_individual_sql_verification()
