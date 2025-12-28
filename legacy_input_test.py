"""
Legacy Input Test

.pc 파일을 입력받아 SQL을 추출하고 MyBatis 형식으로 변환한 결과를 
YAML 파일로 저장하는 테스트 스크립트입니다.

Usage:
    python legacy_input_test.py --input_file path/to/file.pc --save_as output.yaml
    
    # 또는 대화형 실행
    python legacy_input_test.py
"""

import argparse
import os
import sys
from typing import List, Dict, Any

# 현재 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sql_extractor import (
    SQLExtractor,
    MyBatisSQL,
    SQLCommentMarker,
)


def analyze_pc_file(input_file: str, save_as: str) -> Dict[str, Any]:
    """
    .pc 파일을 분석하고 결과를 YAML로 저장
    
    Args:
        input_file: Pro*C 파일 경로
        save_as: 결과 YAML 저장 경로
    
    Returns:
        분석 결과 딕셔너리
    """
    # 파일 읽기
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()
    
    print(f"[INFO] 입력 파일 로드: {input_file} ({len(code)} bytes)")
    
    # SQLExtractor 초기화
    extractor = SQLExtractor()
    
    # MyBatis 변환 실행
    result_code, mybatis_sqls = extractor.extract_with_mybatis_conversion(
        code=code,
        file_key=os.path.splitext(os.path.basename(input_file))[0]
    )
    
    print(f"[INFO] 추출된 SQL 수: {len(mybatis_sqls)}")
    
    # 결과 구성
    result = {
        'source_file': input_file,
        'total_sql_count': len(mybatis_sqls),
        'sql_statements': []
    }
    
    for sql in mybatis_sqls:
        sql_entry = {
            'id': sql.id,
            'mybatis_type': sql.mybatis_type,
            'converted_sql': sql.sql,
            'original_sql': sql.original_sql,
            'input_params': sql.input_params,
            'output_fields': sql.output_fields,
        }
        result['sql_statements'].append(sql_entry)
        
        # 각 SQL 출력
        print(f"  - {sql.id} ({sql.mybatis_type})")
    
    # YAML 저장
    save_result_yaml(result, save_as)
    
    # 변환된 코드도 저장 (옵션)
    code_output_path = save_as.replace('.yaml', '_commented.txt').replace('.yml', '_commented.txt')
    with open(code_output_path, 'w', encoding='utf-8') as f:
        f.write(result_code)
    print(f"[INFO] 주석 삽입된 코드 저장: {code_output_path}")
    
    return result


def save_result_yaml(result: Dict[str, Any], save_as: str):
    """결과를 YAML 파일로 저장"""
    try:
        import yaml
        
        # 멀티라인 문자열을 리터럴 스타일로 출력
        class LiteralStr(str):
            pass
        
        def literal_representer(dumper, data):
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        
        yaml.add_representer(LiteralStr, literal_representer)
        
        # SQL 문자열을 리터럴 스타일로 변환
        for sql_entry in result['sql_statements']:
            if sql_entry.get('converted_sql'):
                sql_entry['converted_sql'] = LiteralStr(sql_entry['converted_sql'])
            if sql_entry.get('original_sql'):
                sql_entry['original_sql'] = LiteralStr(sql_entry['original_sql'])
        
        # 디렉토리 생성
        os.makedirs(os.path.dirname(save_as) if os.path.dirname(save_as) else '.', exist_ok=True)
        
        with open(save_as, 'w', encoding='utf-8') as f:
            yaml.dump(result, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        print(f"[INFO] 결과 저장 완료: {save_as}")
        
    except ImportError:
        # YAML 없으면 JSON으로 대체
        import json
        json_path = save_as.replace('.yaml', '.json').replace('.yml', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 결과 저장 완료 (JSON): {json_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Pro*C 파일에서 SQL을 추출하고 MyBatis 형식으로 변환합니다.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  python legacy_input_test.py --input_file sample.pc --save_as output.yaml
  python legacy_input_test.py -i tests/samples/complex_test.pc -o result.yaml
        """
    )
    
    parser.add_argument(
        '--input_file', '-i',
        type=str,
        help='분석할 .pc 파일 경로'
    )
    
    parser.add_argument(
        '--save_as', '-o',
        type=str,
        help='결과를 저장할 YAML 파일 경로'
    )
    
    args = parser.parse_args()
    
    # 대화형 모드
    if not args.input_file:
        args.input_file = input("입력 파일 경로 (.pc): ").strip()
    
    if not args.save_as:
        default_output = os.path.splitext(args.input_file)[0] + '_analysis.yaml'
        args.save_as = input(f"저장 경로 [{default_output}]: ").strip() or default_output
    
    # 분석 실행
    try:
        result = analyze_pc_file(args.input_file, args.save_as)
        print(f"\n[SUCCESS] 분석 완료!")
        print(f"  - 추출된 SQL: {result['total_sql_count']}개")
        print(f"  - 결과 파일: {args.save_as}")
    except Exception as e:
        print(f"[ERROR] 분석 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
