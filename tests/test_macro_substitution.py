"""
매크로 상수 치환 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proc_parser import ProCParser

def test_macro_substitution():
    """매크로 상수 치환 테스트"""
    print("=== 매크로 상수 치환 테스트 ===\n")
    
    # 테스트용 Pro*C 코드 작성
    test_code = '''
#define MAX_SIZE 100
#define BUFFER_LEN 256
#define COLS 50

int matrix[MAX_SIZE][COLS];
char buffer[BUFFER_LEN];
float values[10][20][30];
int undefined_macro[UNKNOWN_SIZE];
    '''
    
    # 임시 파일 생성
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pc', delete=False) as f:
        f.write(test_code)
        temp_path = f.name
    
    try:
        parser = ProCParser()
        
        # 테스트 1: 파일 내 매크로만 사용
        print("1. 파일 내 매크로만 사용:")
        result = parser.parse_file(temp_path)
        vars = [e for e in result if e['type'] == 'variable']
        
        for v in vars:
            if v.get('array_sizes'):
                print(f"   {v['name']}: {v['array_sizes']} -> {v.get('resolved_array_sizes')}")
        print()
        
        # 테스트 2: 외부 매크로 주입
        print("2. 외부 매크로 주입 (UNKNOWN_SIZE=999):")
        external_macros = {"UNKNOWN_SIZE": "999"}
        result = parser.parse_file(temp_path, external_macros=external_macros)
        vars = [e for e in result if e['type'] == 'variable']
        
        for v in vars:
            if v.get('array_sizes'):
                print(f"   {v['name']}: {v['array_sizes']} -> {v.get('resolved_array_sizes')}")
        print()
        
        # 테스트 3: 파일 매크로가 외부 매크로를 덮어쓰는지 확인
        print("3. 파일 매크로 우선순위 테스트 (MAX_SIZE=999 주입, 파일에서 100으로 정의):")
        external_macros = {"MAX_SIZE": "999"}
        result = parser.parse_file(temp_path, external_macros=external_macros)
        vars = [e for e in result if e['type'] == 'variable' and e.get('name') == 'matrix']
        
        for v in vars:
            print(f"   {v['name']}: {v['array_sizes']} -> {v.get('resolved_array_sizes')}")
            expected = ['100', '50']  # 파일 매크로가 우선
            if v.get('resolved_array_sizes') == expected:
                print("   ✓ 파일 매크로가 외부 매크로를 정상적으로 덮어씀")
            else:
                print(f"   ✗ 예상: {expected}")
        print()
        
        # 결과 확인
        print("=== 테스트 완료 ===")
        
    finally:
        os.unlink(temp_path)


if __name__ == "__main__":
    test_macro_substitution()
