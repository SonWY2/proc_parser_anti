"""
Docstring 추출 기능 테스트 스크립트
"""
import sys
sys.path.insert(0, r'd:\workspace\proc_parser_antigravity\proc_parser')

from parsing.core import ProCParser

parser = ProCParser()
elements = parser.parse_file(r'd:\workspace\proc_parser_antigravity\proc_parser\sample_input\enterprise_complex_sql.pc')

functions = [e for e in elements if e['type'] == 'function']

print(f"총 {len(functions)}개의 함수 발견\n")
print("=" * 80)

for func in functions:
    print(f"함수명: {func['name']}")
    print(f"라인: {func['line_start']} - {func['line_end']}")
    docstring = func.get('docstring')
    if docstring:
        # 첫 100자만 출력
        preview = docstring[:200] + "..." if len(docstring) > 200 else docstring
        print(f"Docstring:\n{preview}")
    else:
        print("Docstring: (없음)")
    print("-" * 80)
