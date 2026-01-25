"""
LLM 기반 Verifier 통합 테스트

모든 LLM 검증기(Header, SQL Extraction, SQL Metadata)를 테스트합니다.
"""

import json
from pathlib import Path

from verification.verifier.llm_client import LLMClient
from verification.verifier.plugins.llm_header_verifier import LLMHeaderVerifier
from verification.verifier.plugins.llm_sql_extraction_verifier import LLMSQLExtractionVerifier
from verification.verifier.plugins.llm_sql_metadata_verifier import LLMSQLMetadataVerifier
from verification.verifier.types import VerificationInput, VerificationType

# ==========================================
# LLM 설정 (여기에 정보를 입력하세요)
# ==========================================
API_KEY = ""       # OpenAI API Key
MODEL_NAME = ""    # 예: "gpt-4o-mini", "o1-mini"
ENDPOINT = ""      # 예: "https://api.openai.com/v1"
# ==========================================


def get_llm_client():
    """LLM 클라이언트 생성"""
    return LLMClient(
        api_key=API_KEY or None,
        model=MODEL_NAME or None,
        endpoint=ENDPOINT or None
    )


def test_header_verification():
    """1) 헤더 섹션 검증 테스트 - 변수/매크로/헤더 파싱"""
    print("=" * 60)
    print("1. LLM Header Section Verification Test")
    print("=" * 60)
    
    llm_client = get_llm_client()
    if not llm_client.is_configured:
        print("⚠️ OPENAI_API_KEY not set. Skipping.")
        return
    
    # 테스트 데이터
    header_source = '''
#include <stdio.h>
#include <string.h>
#include <sqlca.h>

#define MAX_SIZE 256
#define ERROR_CODE -1

EXEC SQL BEGIN DECLARE SECTION;
    char in_acct_no[11];
    char in_balance_dt[9];
    long out_balance;
    short ind_balance;
EXEC SQL END DECLARE SECTION;
'''

    # 의도적으로 일부 누락된 분석 결과
    analysis_result = {
        "macros": [
            {"name": "MAX_SIZE", "value": "256"},
            # ERROR_CODE 누락
        ],
        "includes": [
            {"path": "stdio.h", "is_system": True},
            {"path": "string.h", "is_system": True},
            # sqlca.h 누락
        ],
        "variables": [
            {"name": "in_acct_no", "type": "char", "array_size": "11"},
            {"name": "in_balance_dt", "type": "char", "array_size": "9"},
            {"name": "out_balance", "type": "int"},  # 잘못된 타입 (long -> int)
            # ind_balance 누락
        ]
    }
    
    print("\n[Test Case] Header with intentional errors")
    print(f"Source has: 2 macros, 3 includes, 4 variables")
    print(f"Analysis has: 1 macro, 2 includes, 3 variables (with errors)")
    
    verifier = LLMHeaderVerifier(llm_client)
    input_data = VerificationInput(
        verification_type=VerificationType.HEADER,
        original_source=header_source,
        analysis_result=analysis_result
    )
    
    print("\nCalling LLM for verification...")
    result = verifier.verify(input_data)
    
    print(f"\nStatus: {result.status.value}")
    print(f"Passed: {result.passed_items}/{result.total_items}")
    
    if result.issues:
        print("\nIssues found:")
        for issue in result.issues:
            icon = "❌" if issue.severity == "error" else "⚠️"
            print(f"  {icon} [{issue.category}] {issue.message}")


def test_sql_extraction_verification():
    """2) SQL 추출 검증 테스트 - 함수/SQL 추출"""
    print("\n" + "=" * 60)
    print("2. LLM SQL Extraction Verification Test")
    print("=" * 60)
    
    llm_client = get_llm_client()
    if not llm_client.is_configured:
        print("⚠️ OPENAI_API_KEY not set. Skipping.")
        return
    
    # 추출된 코드 (_extracted.c)
    extracted_code = '''
int process_account(char *acct_no) {
    int result = 0;
    char buffer[256];
    
    /* SQL: sql_001 - SELECT account info */
    
    if (result == 0) {
        /* SQL: sql_002 - UPDATE last access */
    }
    
    // 미추출된 SQL이 남아있는 경우
    EXEC SQL COMMIT;
    
    return result;
}
'''

    # 분석 결과
    analysis_result = {
        "functions": [
            {
                "name": "process_account",
                "sql_ids": ["sql_001", "sql_002"],
                "local_variables": [
                    {"name": "result", "type": "int"},
                    {"name": "buffer", "type": "char", "array_size": "256"}
                ]
            }
        ],
        "sql_ids": ["sql_001", "sql_002"],  # sql_003 (COMMIT) 누락
    }
    
    print("\n[Test Case] Extracted code with unextracted COMMIT")
    
    verifier = LLMSQLExtractionVerifier(llm_client)
    input_data = VerificationInput(
        verification_type=VerificationType.SQL_EXTRACTION,
        original_source=extracted_code,
        analysis_result=analysis_result
    )
    
    print("\nCalling LLM for verification...")
    result = verifier.verify(input_data)
    
    print(f"\nStatus: {result.status.value}")
    print(f"Passed: {result.passed_items}/{result.total_items}")
    
    if result.issues:
        print("\nIssues found:")
        for issue in result.issues:
            icon = "❌" if issue.severity == "error" else "⚠️"
            print(f"  {icon} [{issue.category}] {issue.message}")


def test_sql_metadata_verification():
    """3) SQL 메타데이터 검증 테스트 - input/output/alias"""
    print("\n" + "=" * 60)
    print("3. LLM SQL Metadata Verification Test")
    print("=" * 60)
    
    llm_client = get_llm_client()
    if not llm_client.is_configured:
        print("⚠️ OPENAI_API_KEY not set. Skipping.")
        return
    
    raw_sql = """SELECT CUST_NM, CUST_ADDR AS address
INTO :out_cust_name :ind_cust_name, :out_cust_addr
FROM CUSTOMER
WHERE CUST_ID = :in_cust_id AND STATUS = :in_status"""

    # 의도적으로 누락/오류가 있는 메타데이터
    metadata = {
        "sql_id": "sql_001",
        "input_host_vars": [":in_cust_id"],  # :in_status 누락
        "output_host_vars": [":out_cust_name"],  # :ind_cust_name, :out_cust_addr 누락
        "aliases": [],  # address alias 누락
        "mybatis_sql": "SELECT CUST_NM, CUST_ADDR AS address FROM CUSTOMER WHERE CUST_ID = :in_cust_id AND STATUS = :in_status",
    }
    
    print("\n[Test Case] SQL metadata with missing variables and unconverted mybatis")
    
    verifier = LLMSQLMetadataVerifier(llm_client)
    input_data = VerificationInput(
        verification_type=VerificationType.SQL_METADATA,
        original_source=raw_sql,
        analysis_result=metadata
    )
    
    print("\nCalling LLM for verification...")
    result = verifier.verify(input_data)
    
    print(f"\nStatus: {result.status.value}")
    print(f"Passed: {result.passed_items}/{result.total_items}")
    
    if result.issues:
        print("\nIssues found:")
        for issue in result.issues:
            icon = "❌" if issue.severity == "error" else "⚠️"
            print(f"  {icon} [{issue.category}] {issue.message}")


def run_all_tests():
    """모든 LLM 검증 테스트 실행"""
    print("\n" + "=" * 60)
    print("LLM Verifier Comprehensive Test Suite")
    print("=" * 60)
    
    llm_client = get_llm_client()
    print(f"\nLLM Configuration:")
    print(f"  - API Key configured: {llm_client.is_configured}")
    print(f"  - Model: {llm_client.model_name}")
    print(f"  - Endpoint: {llm_client.endpoint}")
    
    if not llm_client.is_configured:
        print("\n⚠️ OPENAI_API_KEY not set.")
        print("   Set API_KEY variable at the top of this file or environment variable.")
        return
    
    # 1. 헤더 섹션 검증
    test_header_verification()
    
    # 2. SQL 추출 검증
    test_sql_extraction_verification()
    
    # 3. SQL 메타데이터 검증
    test_sql_metadata_verification()
    
    print("\n" + "=" * 60)
    print("All Tests Completed")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
