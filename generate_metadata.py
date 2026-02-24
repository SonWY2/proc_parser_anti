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

from parsing.core.unified_metadata_generator import UnifiedMetadataGenerator
try:
    from infra.config import ArtifactConfigLoader
except ImportError:
    ArtifactConfigLoader = None


def main():
    # Redirect output to file for debugging
    log_file = open('internal_log.txt', 'w', encoding='utf-8')
    sys.stdout = log_file
    sys.stderr = log_file
    print("DEBUG: Script starting (internal log)...", flush=True)
    try:
        _real_main()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        log_file.close()

def _real_main():
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

    parser.add_argument(
        '-c', '--config',
        help='아티팩트 설정 JSONL 파일 경로'
    )
    
    parser.add_argument(
        '--jsonl-dir',
        help='메타데이터를 유형별 JSONL 파일로 저장할 디렉토리 경로 (예: variables.jsonl, functions.jsonl)'
    )
    
    args = parser.parse_args()
    print(f"DEBUG: Arguments parsed. Source: {args.source_file}", flush=True)
    
    # 소스 경로 존재 확인
    if not os.path.exists(args.source_file):
        print(f"오류: 경로를 찾을 수 없습니다: {args.source_file}")
        sys.exit(1)
    
    # include 경로 절대 경로 변환
    include_paths = [os.path.abspath(p) for p in args.include_paths]
    
    # 처리할 파일 목록 수집
    targets = []
    is_directory = os.path.isdir(args.source_file)
    
    if is_directory:
        # 디렉토리 모드: 재귀적으로 파일 검색
        if args.verbose:
            print(f"디렉토리 탐색 중: {args.source_file}")
            
        extensions = {'.pc', '.sqc', '.c'}
        for root, _, files in os.walk(args.source_file):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    file_path = os.path.join(root, file)
                    targets.append(file_path)
        
        if not targets:
            print("오류: 지정된 디렉토리에서 처리할 소스 파일(.pc, .sqc, .c)을 찾을 수 없습니다.")
            sys.exit(1)
            
        # 디렉토리 모드에서는 출력이 디렉토리여야 함
        # 확장자가 없거나 디렉토리로 끝나면 디렉토리로 간주
        output_dir = args.output
        if os.path.splitext(output_dir)[1]:
            # 사용자가 파일명을 입력했을 수 있음 -> 경고 후 부모 디렉토리 사용하거나 에러 처리
            # 여기서는 명확성을 위해 에러 처리
            print(f"오류: 입력이 디렉토리일 경우, 출력(-o)도 디렉토리여야 합니다: {output_dir}")
            sys.exit(1)
            
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
    else:
        # 단일 파일 모드
        targets.append(args.source_file)
        
        # 소스 파일 디렉토리를 include 경로에 추가 (단일 파일일 때만 명시적으로 추가)
        source_dir = os.path.dirname(os.path.abspath(args.source_file))
        if source_dir not in include_paths:
            include_paths.insert(0, source_dir)

    # -----------------------------------------------------------
    # Generator 인스턴스 생성 (캐시 공유를 위해 한 번만 생성)
    # -----------------------------------------------------------
    # Config 로딩
    artifact_configs = None
    if args.config:
        if not os.path.exists(args.config):
             print(f"오류: 설정 파일을 찾을 수 없습니다: {args.config}")
             sys.exit(1)
        
        if ArtifactConfigLoader:
             try:
                 artifact_configs = ArtifactConfigLoader.load(args.config)
                 if args.verbose:
                     print(f"설정 로드됨: {len(artifact_configs)}개 항목 ({args.config})")
             except Exception as e:
                 print(f"설정 파일 로드 실패: {e}")
                 sys.exit(1)
        else:
             print("경고: ArtifactConfigLoader를 사용할 수 없어 설정을 무시합니다.")

    # -----------------------------------------------------------
    # Generator 인스턴스 생성 (캐시 공유를 위해 한 번만 생성)
    # -----------------------------------------------------------
    generator = UnifiedMetadataGenerator(
        include_paths=include_paths,
        base_package=args.base_package,
        generate_artifacts=args.with_artifacts,
        artifact_configs=artifact_configs
    )

    # -----------------------------------------------------------
    # 공통 처리 함수
    # -----------------------------------------------------------
    def process_file(source_path, output_path):
        try:
            if args.verbose:
                print(f"분석 시작: {source_path}")
            
            metadata = generator.generate(source_path)
            
            # 저장
            if args.format == 'yaml':
                generator.save_yaml(metadata, output_path)
            else:
                generator.save_json(metadata, output_path, indent=args.indent)
            
            # JSONL 저장 (옵션)
            if args.jsonl_dir:
                # 디렉토리 모드인 경우 하위 폴더 생성
                if is_directory:
                    rel_dir = os.path.dirname(os.path.relpath(source_path, os.path.abspath(args.source_file)))
                    jsonl_output_dir = os.path.join(args.jsonl_dir, rel_dir) if rel_dir else args.jsonl_dir
                else:
                    jsonl_output_dir = args.jsonl_dir
                
                generator.save_jsonl(metadata, jsonl_output_dir)
                if args.verbose:
                    print(f"  JSONL 저장됨: {jsonl_output_dir}")
            
            if args.verbose:
                print(f"저장 완료: {output_path}")
                cached_count = len(generator._header_cache)
                print(f"  캐시된 헤더: {cached_count}개")
                
            return metadata
        except Exception as e:
            print(f"실패 ({source_path}): {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return None

    # -----------------------------------------------------------
    # 실행 루프
    # -----------------------------------------------------------
    success_count = 0
    total_count = len(targets)
    
    print(f"총 {total_count}개 파일 처리 예정...")
    
    for i, source_path in enumerate(targets):
        source_path = os.path.abspath(source_path)
        
        if is_directory:
            # 출력 파일명 생성: 입력 디렉토리 기준 상대 경로 유지
            rel_path = os.path.relpath(source_path, os.path.abspath(args.source_file))
            # 확장자 변경
            base_name = os.path.splitext(rel_path)[0]
            ext = '.yaml' if args.format == 'yaml' else '.json'
            output_file_name = base_name + ext
            
            final_output_path = os.path.join(args.output, output_file_name)
            
            # 하위 디렉토리 생성
            os.makedirs(os.path.dirname(final_output_path), exist_ok=True)
        else:
            final_output_path = args.output
            
        print(f"[{i+1}/{total_count}] {os.path.basename(source_path)} -> {final_output_path}")
        
        result = process_file(source_path, final_output_path)
        if result:
            success_count += 1
            
            # (옵션) 요약 정보 출력
            if not is_directory or args.verbose:
                summary = result.get('source_analysis', {}).get('summary', {})
                print(f"  완료: 요소 {summary.get('total_elements', 0)}개")
                if args.with_artifacts:
                    artifacts = result.get('generated_artifacts', {})
                    dao_count = 1 if 'dao' in artifacts else 0
                    print(f"  Artifacts: DAO {dao_count}개 생성됨")

    print()
    print(f"작업 완료: 성공 {success_count}/{total_count} 파일")
    
    if success_count < total_count:
        sys.exit(1)


if __name__ == '__main__':
    main()
