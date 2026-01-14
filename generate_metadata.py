#!/usr/bin/env python
"""
통합 메타데이터 생성 CLI 스크립트

Pro*C/SQC 파일에서 모든 분석 정보와 재귀적 헤더 정보를 포함한
통합 메타데이터 파일을 생성합니다.

사용법:
    python generate_metadata.py sample.pc -o output.json
    python generate_metadata.py sample.pc -o output.yaml --format yaml
    python generate_metadata.py sample.pc -o output.json --include-paths ./headers ./common
    python generate_metadata.py sample.pc -o output.json --with-artifacts
"""
import argparse
import os
import sys

# proc_parser 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from proc_parser.unified_metadata_generator import UnifiedMetadataGenerator


def main():
    parser = argparse.ArgumentParser(
        description='Pro*C/SQC 파일에서 통합 메타데이터 생성',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python generate_metadata.py sample.pc -o output.json
  python generate_metadata.py sample.pc -o output.yaml --format yaml
  python generate_metadata.py sample.pc -o output.json --include-paths ./headers
  python generate_metadata.py sample.pc -o output.json --with-artifacts
        """
    )
    
    parser.add_argument(
        'source_file',
        help='분석할 Pro*C/SQC 소스 파일 경로'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='출력 파일 경로 (예: output.json 또는 output.yaml)'
    )
    
    parser.add_argument(
        '--format',
        choices=['json', 'yaml'],
        default='json',
        help='출력 포맷 (기본: json)'
    )
    
    parser.add_argument(
        '--include-paths',
        nargs='+',
        default=[],
        help='헤더 파일 검색 경로 (여러 개 지정 가능)'
    )
    
    parser.add_argument(
        '--base-package',
        default='com.example.dao',
        help='OMM/DBIO 생성 시 Java 패키지 (기본: com.example.dao)'
    )
    
    parser.add_argument(
        '--with-artifacts',
        action='store_true',
        help='OMM/DBIO 아티팩트 포함 생성'
    )
    
    parser.add_argument(
        '--indent',
        type=int,
        default=2,
        help='JSON 들여쓰기 (기본: 2)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='상세 출력'
    )
    
    args = parser.parse_args()
    
    # 소스 파일 존재 확인
    if not os.path.exists(args.source_file):
        print(f"오류: 소스 파일을 찾을 수 없습니다: {args.source_file}")
        sys.exit(1)
    
    # include 경로 절대 경로 변환
    include_paths = [os.path.abspath(p) for p in args.include_paths]
    
    # 소스 파일 디렉토리도 include 경로에 추가
    source_dir = os.path.dirname(os.path.abspath(args.source_file))
    if source_dir not in include_paths:
        include_paths.insert(0, source_dir)
    
    if args.verbose:
        print(f"소스 파일: {args.source_file}")
        print(f"출력 파일: {args.output}")
        print(f"출력 포맷: {args.format}")
        print(f"Include 경로: {include_paths}")
        print(f"아티팩트 생성: {args.with_artifacts}")
        print()
    
    try:
        # 메타데이터 생성기 초기화
        generator = UnifiedMetadataGenerator(
            include_paths=include_paths,
            base_package=args.base_package,
            generate_artifacts=args.with_artifacts
        )
        
        if args.verbose:
            print("분석 시작...")
        
        # 메타데이터 생성
        metadata = generator.generate(args.source_file)
        
        if args.verbose:
            summary = metadata.get('source_analysis', {}).get('summary', {})
            print(f"분석 완료: {summary.get('total_elements', 0)}개 요소")
            print(f"유형별: {summary.get('by_type', {})}")
            print()
        
        # 출력 파일 저장
        output_path = args.output
        
        if args.format == 'yaml':
            generator.save_yaml(metadata, output_path)
        else:
            generator.save_json(metadata, output_path, indent=args.indent)
        
        print(f"메타데이터 저장 완료: {output_path}")
        
        # 요약 출력
        summary = metadata.get('source_analysis', {}).get('summary', {})
        header_count = len(metadata.get('header_tree', {}).get('all_headers_flat', []))
        print(f"  - 총 요소: {summary.get('total_elements', 0)}개")
        print(f"  - 헤더 파일: {header_count}개")
        
        if args.with_artifacts:
            artifacts = metadata.get('generated_artifacts', {})
            omm_count = len(artifacts.get('omm', {}))
            print(f"  - OMM 아티팩트: {omm_count}개")
        
    except FileNotFoundError as e:
        print(f"오류: 파일을 찾을 수 없습니다: {e}")
        sys.exit(1)
    except ImportError as e:
        print(f"오류: 필요한 모듈이 없습니다: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"오류: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
