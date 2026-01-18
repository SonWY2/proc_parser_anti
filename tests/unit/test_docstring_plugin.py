"""
Docstring 추출 플러그인 테스트 스크립트
"""
import sys
sys.path.insert(0, r'd:\workspace\proc_parser_antigravity\proc_parser')

from proc_parser import ProCParser

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
        print(f"Docstring 존재: True (길이: {len(docstring)}자)")
        # raw_content에 docstring이 포함되어 있는지 확인
        raw_content = func.get('raw_content', '')
        if docstring in raw_content:
            print("raw_content에 docstring 포함: True ✓")
        else:
            print("raw_content에 docstring 포함: False ✗")
    else:
        print("Docstring 존재: False")
    print("-" * 80)
