"""
Pro*C to Java 변환 CLI 스크립트

사용법:
    # 전체 변환 (skeleton + functions)
    python convert_to_java.py original_source.sqc -o ./output/
    
    # skeleton만 생성
    python convert_to_java.py original_source.sqc --skeleton-only
    
    # 특정 함수만 변환
    python convert_to_java.py original_source.sqc --function tlfb000m_main
    
    # 메타데이터 JSON 직접 입력
    python convert_to_java.py --metadata output.json -o ./output/
"""

import argparse
import json
import sys
from pathlib import Path

# 모듈 경로 설정
sys.path.insert(0, str(Path(__file__).parent))

from conversion import (
    ProcToJavaConverter,
    ConversionConfig,
)
from conversion.plugins import (
    NamingConventionPlugin,
    SpringAnnotationPlugin,
)


def load_metadata(source_file: str) -> dict:
    """
    소스 파일에서 메타데이터 생성 또는 JSON 파일 로드
    """
    path = Path(source_file)
    
    if path.suffix == ".json":
        # JSON 파일 직접 로드
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Pro*C 파일에서 메타데이터 생성
        from parsing.core import UnifiedMetadataGenerator
        
        generator = UnifiedMetadataGenerator()
        return generator.generate(str(path))


def create_llm_client():
    """LLM 클라이언트 생성"""
    try:
        from validation.llm import LLMClient
        client = LLMClient()
        if not client.is_configured:
            print("Warning: LLM not configured. Set up .env file with API keys.")
            return None
        return client
    except ImportError:
        print("Error: validation.llm module not found")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Pro*C to Java (Spring+MyBatis) Converter"
    )
    
    # 입력 옵션
    parser.add_argument(
        "source",
        nargs="?",
        help="Pro*C/SQC source file or metadata JSON file"
    )
    parser.add_argument(
        "--metadata", "-m",
        help="Path to metadata JSON file (alternative to source)"
    )
    
    # 출력 옵션
    parser.add_argument(
        "--output", "-o",
        default="./output/java/",
        help="Output directory for generated Java files"
    )
    
    # 변환 모드
    parser.add_argument(
        "--skeleton-only",
        action="store_true",
        help="Generate only class skeleton (no function implementations)"
    )
    parser.add_argument(
        "--function", "-f",
        help="Convert only specific function by name"
    )
    parser.add_argument(
        "--prompt-only",
        action="store_true",
        help="Generate prompts only, print to stdout"
    )
    parser.add_argument(
        "--export-prompts",
        help="Export prompts to markdown files in sequence to the specified directory"
    )
    
    # 설정 옵션
    parser.add_argument(
        "--package",
        default="com.example.service",
        help="Java package name"
    )
    parser.add_argument(
        "--suffix",
        default="Service",
        help="Class name suffix"
    )
    parser.add_argument(
        "--no-spring",
        action="store_true",
        help="Disable Spring annotations"
    )
    parser.add_argument(
        "--mapper-package",
        default="com.example.mapper",
        help="MyBatis mapper package"
    )
    
    args = parser.parse_args()
    
    # 입력 파일 결정
    input_file = args.metadata or args.source
    if not input_file:
        parser.print_help()
        sys.exit(1)
    
    print(f"Loading metadata from: {input_file}")
    metadata = load_metadata(input_file)
    
    # 설정 생성
    config = ConversionConfig(
        package_name=args.package,
        class_name_suffix=args.suffix,
        use_spring_annotations=not args.no_spring,
        mybatis_mapper_package=args.mapper_package,
    )

    # 프롬프트 파일 내보내기 모드
    if args.export_prompts:
        from conversion import PromptExporter
        exporter = PromptExporter(config)
        output_dir = args.export_prompts
        
        print(f"Exporting prompts to: {output_dir}")
        
        if args.function:
            # 특정 함수 프롬프트 내보내기
            try:
                path = exporter.export_function_prompt(
                    metadata, 
                    args.function, 
                    str(Path(output_dir) / f"{args.function}.md")
                )
                print(f"Exported function prompt: {path}")
            except Exception as e:
                print(f"Error exporting prompt: {e}")
                sys.exit(1)
        
        elif args.skeleton_only:
            # 스켈레톤 프롬프트만 내보내기
            path = exporter.export_skeleton_prompt(
                metadata, 
                str(Path(output_dir) / "00_skeleton.md")
            )
            print(f"Exported skeleton prompt: {path}")
            
        else:
            # 전체 내보내기
            result = exporter.export_all(metadata, output_dir)
            print(f"Exported all prompts. see index: {result['index']}")
            
        return
    
    # 프롬프트만 출력하는 모드 (stdout)
    if args.prompt_only:
        from conversion import PromptBuilder
        builder = PromptBuilder(config)
        
        if args.function:
            # 특정 함수 프롬프트
            functions = metadata.get("source_analysis", {}).get("elements_by_type", {}).get("functions", [])
            func = next((f for f in functions if f.get("name") == args.function), None)
            if func:
                from conversion.types import PromptContext
                context = PromptContext(
                    source_file=metadata.get("metadata", {}).get("source_file", ""),
                    metadata=metadata,
                    config=config,
                )
                prompt = builder.build_function_prompt(func, context)
            else:
                print(f"Function '{args.function}' not found")
                sys.exit(1)
        else:
            # 스켈레톤 프롬프트
            prompt = builder.build_skeleton_prompt(metadata)
        
        print("\n" + "="*60)
        print("GENERATED PROMPT:")
        print("="*60)
        print(prompt)
        return
    
    # LLM 클라이언트 생성
    llm_client = create_llm_client()
    if not llm_client:
        print("Cannot proceed without LLM client. Use --prompt-only to generate prompts.")
        sys.exit(1)
    
    # 변환기 생성 및 플러그인 등록
    converter = ProcToJavaConverter(llm_client, config)
    converter.register_plugin(NamingConventionPlugin())
    if not args.no_spring:
        converter.register_plugin(SpringAnnotationPlugin())
    
    # 변환 실행
    if args.skeleton_only:
        print("Generating class skeleton...")
        result = converter.convert_skeleton_only(metadata)
        java_code = result.java_code
        class_name = result.class_name
    elif args.function:
        print(f"Converting function: {args.function}")
        result = converter.convert_single_function(metadata, args.function)
        java_code = result.java_code
        class_name = args.function
    else:
        print("Converting entire file...")
        result = converter.convert(metadata)
        java_code = result.full_java_code
        class_name = result.skeleton.class_name
        
        # 통계 출력
        print(f"\nConversion Statistics:")
        print(f"  Total functions: {result.total_functions}")
        print(f"  Converted: {result.converted_functions}")
        print(f"  Skipped: {len(result.skipped_functions)}")
        if result.errors:
            print(f"  Errors: {len(result.errors)}")
            for err in result.errors:
                print(f"    - {err}")
    
    # 출력
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"{class_name}.java"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(java_code)
    
    print(f"\nOutput written to: {output_file}")


if __name__ == "__main__":
    main()
