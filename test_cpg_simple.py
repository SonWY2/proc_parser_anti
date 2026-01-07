"""CPG 모듈 테스트 스크립트"""
import sys
sys.path.insert(0, '.')

from CPG import CPGBuilder

def test_cpg():
    builder = CPGBuilder()
    
    # 샘플 파일로 테스트
    cpg = builder.build_from_file('tests/samples/complex_test.pc')
    
    # 요약 출력
    print(builder.summary(cpg))
    
    # JSON 출력 테스트
    builder.export_json(cpg, 'tests/samples/cpg_output.json')
    
    print("\n테스트 완료!")

if __name__ == '__main__':
    test_cpg()
