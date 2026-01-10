"""LLM Verifier 간단 테스트"""
from llm_verifier import LLMVerifier

def test_basic_verification():
    verifier = LLMVerifier()
    
    source = """
EXEC SQL SELECT * FROM users;
EXEC SQL INSERT INTO logs VALUES (:id);
"""
    result = [
        {'sql_id': 'sql_1', 'sql_type': 'SELECT', 'line_start': 2, 'line_end': 2},
        {'sql_id': 'sql_2', 'sql_type': 'INSERT', 'line_start': 3, 'line_end': 3}
    ]
    
    res = verifier.verify('sql_extraction', source, result)
    
    print("=" * 50)
    print("LLM Verifier 테스트 결과")
    print("=" * 50)
    print(f"Summary: {res.summary()}")
    print(f"Static checks: {len(res.static_checks)}")
    print(f"LLM checks: {len(res.llm_checks)}")
    print(f"Feedbacks: {len(res.feedbacks)}")
    print()
    print("Static Check Details:")
    for check in res.static_checks:
        print(f"  - [{check.status.value}] {check.name}: {check.message}")
    print()
    print("Report Preview:")
    print(res.report_markdown[:500])
    print("=" * 50)

if __name__ == "__main__":
    test_basic_verification()
