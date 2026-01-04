"""CPG 모듈 재귀 헤더 분석 테스트"""
import sys
import os

# CPG 모듈의 부모 디렉토리 (proc_parser) 추가
cpg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(cpg_dir)
sys.path.insert(0, parent_dir)

from CPG import CPGBuilder

def test_recursive_header():
    """main.c -> sub.h -> common.h 체인 테스트"""
    
    test_dir = os.path.dirname(os.path.abspath(__file__))
    include_path = os.path.join(test_dir, 'includes')
    main_file = os.path.join(test_dir, 'main.c')
    
    print("=" * 60)
    print("CPG 재귀 헤더 분석 테스트")
    print("=" * 60)
    print(f"테스트 파일: {main_file}")
    print(f"Include 경로: {include_path}")
    print()
    
    # CPGBuilder 생성 (include_paths 지정)
    builder = CPGBuilder(
        include_paths=[include_path],
        verbose=True
    )
    
    # 재귀적 헤더 분석
    print("\n--- 재귀적 헤더 분석 시작 ---\n")
    cpg = builder.build_from_file(main_file, follow_includes=True)
    
    # 결과 확인
    print("\n--- 분석 결과 ---\n")
    print(builder.summary(cpg))
    
    # 해결된 헤더 경로 출력
    print("\n--- 해결된 헤더 경로 ---")
    for header, path in builder.header_analyzer.resolved_paths.items():
        print(f"  {header} -> {path}")
    
    # 검증
    print("\n--- 검증 ---")
    resolved = builder.header_analyzer.resolved_paths
    
    # sub.h가 해결되었는지 확인
    if 'sub.h' in resolved:
        print("[PASS] sub.h 경로 해결됨")
    else:
        print("[FAIL] sub.h 경로 해결 실패")
    
    # common.h가 includes 폴더에서 해결되었는지 확인
    if 'common.h' in resolved:
        if 'includes' in resolved['common.h']:
            print("[PASS] common.h가 includes 폴더에서 해결됨")
        else:
            print("[FAIL] common.h가 잘못된 위치에서 해결됨")
    else:
        print("[FAIL] common.h 경로 해결 실패")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    test_recursive_header()
