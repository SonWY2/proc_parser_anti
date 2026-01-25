"""
LLM 기반 SQL Metadata Verifier 테스트

test_sample_error의 SQL 데이터를 사용하여 LLM 기반 SQL 메타데이터 검증 테스트를 수행합니다.
"""

import json
from pathlib import Path

from verification.verifier.llm_client import LLMClient
from verification.verifier.plugins.llm_sql_metadata_verifier import LLMSQLMetadataVerifier
from verification.verifier.types import VerificationInput, VerificationType

# ==========================================
# LLM 설정 (여기에 정보를 입력하세요)
# ==========================================
API_KEY = ""       # OpenAI API Key 또는 환경변수에 설정되어 있으면 빈칸 유지
MODEL_NAME = ""    # 예: "gpt-4o-mini", "o1-mini" 등 (빈칸이면 기본값 사용)
ENDPOINT = ""      # 예: "https://api.openai.com/v1" (빈칸이면 기본값 사용)
# ==========================================


def load_sql_jsonl(filepath: str):
    """sql.jsonl 파일을 로드하여 리스트로 반환"""
    sql_list = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                sql_list.append(json.loads(line))
    return sql_list


def test_llm_sql_metadata_verification():
    """LLM 기반 SQL 메타데이터 검증 테스트"""
    print("=" * 60)
    print("LLM-Based SQL Metadata Verification Test")
    print("=" * 60)
    
    # 1. LLM 클라이언트 확인
    llm_client = LLMClient(
        api_key=API_KEY or None,
        model=MODEL_NAME or None,
        endpoint=ENDPOINT or None
    )
    print(f"\nLLM Configuration:")
    print(f"  - API Key configured: {llm_client.is_configured}")
    print(f"  - Model: {llm_client.model_name}")
    print(f"  - Endpoint: {llm_client.endpoint}")
    
    if not llm_client.is_configured:
        print("\n⚠️ OPENAI_API_KEY not set. Please set the environment variable.")
        print("   Example: set OPENAI_API_KEY=your-api-key")
        return
    
    # 2. 경로 설정
    base_dir = Path(__file__).parent / "verification" / "test_sample_error"
    sql_file = base_dir / "sql.jsonl"
    
    # 3. SQL 데이터 로드
    sql_list = load_sql_jsonl(str(sql_file))
    print(f"\nLoaded {len(sql_list)} SQL statements from {sql_file.name}")
    
    # 4. LLM 검증기 생성
    verifier = LLMSQLMetadataVerifier(llm_client)
    
    # 5. 각 SQL에 대해 검증
    all_results = []
    for sql_metadata in sql_list:
        sql_id = sql_metadata.get("sql_id", "unknown")
        raw_sql = sql_metadata.get("raw_content", "")
        
        print(f"\n--- Verifying SQL: {sql_id} ---")
        print(f"SQL Type: {sql_metadata.get('sql_type')}")
        print(f"Raw SQL: {raw_sql[:80]}...")
        
        # 검증 입력 생성
        input_data = VerificationInput(
            verification_type=VerificationType.SQL_METADATA,
            original_source=raw_sql,
            analysis_result=sql_metadata,
        )
        
        # LLM 검증 수행
        result = verifier.verify(input_data)
        all_results.append((sql_id, result))
        
        # 결과 출력
        print(f"Status: {result.status.value}")
        print(f"Passed: {result.passed_items}/{result.total_items}")
        
        if result.issues:
            print("\nIssues found:")
            for issue in result.issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                print(f"  {icon} [{issue.category}] {issue.message}")
                if issue.expected:
                    print(f"      Expected: {issue.expected}")
                if issue.actual:
                    print(f"      Actual: {issue.actual}")
        
        # LLM 원본 응답 (디버그용)
        if result.details.get("raw_response"):
            print(f"\n[LLM Raw Response]\n{result.details['raw_response'][:500]}...")
    
    # 6. 전체 요약
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    total_errors = 0
    total_warnings = 0
    for sql_id, result in all_results:
        errors = len(result.get_errors())
        warnings = len(result.get_warnings())
        total_errors += errors
        total_warnings += warnings
        
        status_icon = "✅" if errors == 0 else "❌"
        print(f"{status_icon} {sql_id}: {result.passed_items}/{result.total_items} passed, {errors} errors, {warnings} warnings")
    
    print("-" * 60)
    if total_errors == 0:
        print(f"✅ All SQL metadata verifications passed! ({total_warnings} warnings)")
    else:
        print(f"❌ {total_errors} errors, {total_warnings} warnings found")
    print("=" * 60)


def test_single_sql_with_llm():
    """단일 SQL에 대한 LLM 검증 테스트"""
    print("\n" + "=" * 60)
    print("Single SQL LLM Verification Test")
    print("=" * 60)
    
    llm_client = LLMClient(
        api_key=API_KEY or None,
        model=MODEL_NAME or None,
        endpoint=ENDPOINT or None
    )
    
    if not llm_client.is_configured:
        print("\n⚠️ OPENAI_API_KEY not set. Skipping test.")
        return
    
    # 테스트 케이스: 일부러 잘못된 분석 결과
    raw_sql = """SELECT CUST_NM, CUST_ADDR AS address
INTO :out_cust_name :ind_cust_name, :out_cust_addr
FROM CUSTOMER
WHERE CUST_ID = :in_cust_id AND STATUS = :in_status"""
    
    metadata = {
        "sql_id": "test_sql_001",
        "function": "get_customer",
        "sql_type": "SELECT",
        "raw_content": raw_sql,
        "input_host_vars": [":in_cust_id"],  # 누락: :in_status
        "output_host_vars": [":out_cust_name"],  # 누락: :ind_cust_name, :out_cust_addr
        "aliases": [],  # 누락: address alias
        "mybatis_sql": "SELECT CUST_NM, CUST_ADDR AS address FROM CUSTOMER WHERE CUST_ID = :in_cust_id AND STATUS = :in_status",  # 변환 안됨
    }
    
    print(f"\n[Test Case] Intentionally wrong metadata")
    print(f"Raw SQL:\n{raw_sql}")
    print(f"\nMetadata (with errors):")
    print(f"  input_host_vars: {metadata['input_host_vars']} (missing :in_status)")
    print(f"  output_host_vars: {metadata['output_host_vars']} (missing :ind_cust_name, :out_cust_addr)")
    print(f"  aliases: {metadata['aliases']} (missing 'address')")
    print(f"  mybatis_sql: host vars not converted to #{{varName}}")
    
    # LLM 검증
    print("\nCalling LLM for verification...")
    response = llm_client.verify_sql_metadata(raw_sql, metadata)
    
    if response.success:
        print(f"\n[LLM Response]\n{response.content}")
    else:
        print(f"\n[Error] {response.error}")


if __name__ == "__main__":
    # LLM 기반 테스트 실행
    test_llm_sql_metadata_verification()
    
    # 단일 테스트
    test_single_sql_with_llm()
