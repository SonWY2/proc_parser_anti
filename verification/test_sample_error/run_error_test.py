import os
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

from verification.verifier import ParsingVerifier

def run_error_test():
    # 1. 경로 설정
    base_dir = Path(__file__).parent
    source_file = base_dir / "sample.sqc"
    extracted_file = base_dir / "sample_extracted.c"
    output_dir = base_dir
    
    # 2. 파일 로드
    with open(source_file, 'r', encoding='utf-8') as f:
        original_source = f.read()
    
    with open(extracted_file, 'r', encoding='utf-8') as f:
        extracted_code = f.read()
        
    # 3. 검증기 실행
    print(f"Running error verification for: {source_file.name}")
    verifier = ParsingVerifier()
    
    results = verifier.verify_all(
        original_source=original_source,
        extracted_code=extracted_code,
        output_dir=str(output_dir)
    )
    
    # 4. 결과 요약
    verifier.print_summary(results)
    
    # 5. 상세 에러 확인 (필요시)
    print("\nDetailed Errors Found:")
    print("-" * 40)
    for vtype, result in results.items():
        if result.issues:
            print(f"\n[{vtype.upper()}] Issues:")
            for issue in result.issues:
                color = "❌" if issue.severity == "error" else "⚠️"
                print(f"  {color} {issue.message}")
                if issue.expected: print(f"    Expected: {issue.expected}")
                if issue.actual: print(f"    Actual: {issue.actual}")
                if issue.line_number: print(f"    Line: {issue.line_number}")

if __name__ == "__main__":
    run_error_test()
