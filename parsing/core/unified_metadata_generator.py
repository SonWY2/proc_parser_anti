"""
통합 메타데이터 생성기

Pro*C/SQC 파일에서 모든 분석 정보와 재귀적 헤더 정보를 포함한
통합 메타데이터 파일을 생성합니다.

이 모듈은 Main Logic + Processor 패턴을 따릅니다:
- UnifiedMetadataGenerator: 메인 오케스트레이터
- HeaderProcessor: 헤더 처리
- SQLProcessor: SQL 처리
- ArtifactProcessor: 아티팩트 생성
"""
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

# 직접 실행 시 경로 설정
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)

# proc_parser 디렉토리와 상위 디렉토리 모두 path에 추가
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# proc_parser 내부 모듈 import (모듈/직접 실행 모두 지원)
try:
    from .core import ProCParser
except ImportError:
    from parsing.core.core import ProCParser

# 프로세서 모듈
try:
    from .processors import HeaderProcessor, SQLProcessor, ArtifactProcessor
    from .processors.header_processor import HeaderEntry
except ImportError:
    from parsing.core.processors import HeaderProcessor, SQLProcessor, ArtifactProcessor
    from parsing.core.processors.header_processor import HeaderEntry

# infra.config
try:
    from infra.config import ArtifactConfig, ArtifactConfigLoader
except ImportError:
    ArtifactConfig = None
    ArtifactConfigLoader = None


class UnifiedMetadataGenerator:
    """
    Pro*C/SQC 파일에서 통합 메타데이터를 생성하는 클래스
    
    이 클래스는 오케스트레이터 역할을 하며, 실제 처리는 
    각 전문 프로세서에게 위임합니다:
    - HeaderProcessor: 헤더 재귀 탐색 및 매크로 수집
    - SQLProcessor: MyBatis 변환, 중복 감지, 관계 수집
    - ArtifactProcessor: OMM/DBIO/DAO 생성
    """
    
    VERSION = "1.1"
    
    def __init__(
        self, 
        include_paths: Optional[List[str]] = None,
        base_package: str = "com.example.dao",
        generate_artifacts: bool = False,
        artifact_configs: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            include_paths: 헤더 파일 검색 경로 리스트
            base_package: OMM/DBIO 생성 시 Java 패키지 (기본값)
            generate_artifacts: OMM/DBIO 아티팩트 생성 여부
            artifact_configs: 파일별 아티팩트 설정 (파일명 -> ArtifactConfig)
        """
        self.include_paths = include_paths or []
        self.base_package = base_package
        self.generate_artifacts = generate_artifacts
        self.artifact_configs = artifact_configs or {}
        
        # 파서 초기화
        self.proc_parser = ProCParser()
        
        # 프로세서 초기화
        self.header_processor = HeaderProcessor(include_paths)
        self.sql_processor = SQLProcessor()
        self.artifact_processor = ArtifactProcessor(base_package)
    
    def generate(self, source_file: str) -> Dict:
        """
        통합 메타데이터 생성 메인 진입점
        
        Args:
            source_file: Pro*C/SQC 소스 파일 경로
            
        Returns:
            통합 메타데이터 딕셔너리
        """
        source_file = os.path.abspath(source_file)
        source_dir = os.path.dirname(source_file)
        
        # 1. 소스 파일 파싱
        elements = self.proc_parser.parse_file(source_file)
        
        # 2. elements 유형별 정리
        elements_by_type = self._organize_elements_by_type(elements)
        
        # 3. 소스 파일 내용 읽기
        with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
            source_content = f.read()
        
        # 4. 헤더 처리 (HeaderProcessor)
        includes = [e for e in elements if e['type'] == 'include']
        header_result = self.header_processor.process({
            'includes': includes,
            'source_dir': source_dir,
            'source_content': source_content,
            'source_file': source_file
        })
        
        header_tree = header_result['header_tree']
        macro_table = header_result['macro_table']
        merged_definitions = header_result['merged_definitions']
        
        # 5. 변수 크기 매크로 해석
        if 'variables' in elements_by_type:
            self._resolve_variable_sizes(elements_by_type['variables'], macro_table)
        
        # 6. SQL 처리 (SQLProcessor)
        sql_result = {"sql_elements": [], "sql_relationships": []}
        if 'sql' in elements_by_type:
            sql_result = self.sql_processor.process({
                'sql_elements': elements_by_type['sql']
            })
        
        sql_relationships = sql_result.get('sql_relationships', [])
        
        # 7. 아티팩트 생성 (ArtifactProcessor) - 선택
        generated_artifacts = {}
        if self.generate_artifacts:
            # Config 결정
            file_id = os.path.splitext(os.path.basename(source_file))[0]
            config = self.artifact_configs.get(file_id)
            if config is None and ArtifactConfig:
                config = ArtifactConfig(id=file_id, base_package=self.base_package)
            
            artifact_result = self.artifact_processor.process({
                'db_vars_info': merged_definitions.get('db_vars_info', {}),
                'sql_elements': elements_by_type.get('sql', []),
                'global_variables': elements_by_type.get('variables', []),
                'source_file_name': source_file,
                'artifact_config': config
            })
            generated_artifacts = artifact_result.get('artifacts', {})
        
        # 8. 요약 통계
        summary = self._create_summary(elements_by_type)
        summary['total_relationships'] = len(sql_relationships)
        
        # 9. 결과 조립
        result = {
            "metadata": {
                "version": self.VERSION,
                "generated_at": datetime.now().isoformat(),
                "source_file": os.path.basename(source_file),
                "source_file_path": source_file
            },
            "source_analysis": {
                "summary": summary,
                "elements_by_type": elements_by_type,
                "sql_relationships": sql_relationships
            },
            "header_tree": {
                "direct_includes": [h.to_dict() for h in header_tree],
                "all_headers_flat": header_result['all_headers_flat']
            },
            "merged_definitions": merged_definitions
        }
        
        if generated_artifacts:
            result["generated_artifacts"] = generated_artifacts
        
        return result
    
    def _organize_elements_by_type(self, elements: List[Dict]) -> Dict[str, List[Dict]]:
        """elements를 유형별로 분류"""
        by_type = {}
        
        for el in elements:
            el_type = el.get('type', 'unknown')
            
            # 복수형 키 사용
            key_map = {
                'function': 'functions',
                'sql': 'sql',
                'variable': 'variables',
                'include': 'includes',
                'macro': 'macros',
                'struct': 'structs',
                'comment': 'comments',
                'function_prototype': 'function_prototypes',
                'preprocessor': 'preprocessor_directives',
                'unknown': 'unknown'
            }
            
            key = key_map.get(el_type, el_type + 's')
            
            if key not in by_type:
                by_type[key] = []
            by_type[key].append(el)
        
        return by_type
    
    def _resolve_variable_sizes(self, variables: List[Dict], macro_table: Dict):
        """변수의 배열 크기 매크로 해석"""
        for var in variables:
            if 'array_sizes' in var:
                resolved = []
                for size in var['array_sizes']:
                    if isinstance(size, int):
                        resolved.append(size)
                    elif isinstance(size, str):
                        if size.isdigit():
                            resolved.append(int(size))
                        elif size in macro_table:
                            macro_val = macro_table[size]['value']
                            try:
                                resolved.append(int(macro_val))
                            except (ValueError, TypeError):
                                resolved.append(size)  # 해석 불가
                        else:
                            resolved.append(size)  # 미정의 매크로
                    else:
                        resolved.append(size)
                var['resolved_array_sizes'] = resolved
    
    def _create_summary(self, elements_by_type: Dict) -> Dict:
        """요약 통계 생성"""
        total = sum(len(v) for v in elements_by_type.values())
        by_type = {k: len(v) for k, v in elements_by_type.items()}
        
        return {
            "total_elements": total,
            "by_type": by_type
        }
    
    def save_json(self, metadata: Dict, output_path: str, indent: int = 2):
        """JSON 파일로 저장"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=indent)
    
    def save_yaml(self, metadata: Dict, output_path: str):
        """YAML 파일로 저장"""
        try:
            import yaml
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(metadata, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        except ImportError:
            raise ImportError("PyYAML이 설치되어 있지 않습니다. 'pip install pyyaml' 실행 필요")
    
    def save_jsonl(self, metadata: Dict, output_dir: str):
        """
        메타데이터를 유형별 JSONL 파일로 저장
        
        Args:
            metadata: generate()에서 생성된 메타데이터 딕셔너리
            output_dir: JSONL 파일들을 저장할 디렉토리 경로
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 소스 파일 정보를 각 항목에 추가하기 위한 메타 정보
        source_info = metadata.get('metadata', {})
        source_file = source_info.get('source_file', '')
        source_file_path = source_info.get('source_file_path', '')
        
        # 저장할 데이터 매핑: (파일명, 데이터 경로)
        elements_by_type = metadata.get('source_analysis', {}).get('elements_by_type', {})
        
        export_mapping = {
            'variables': elements_by_type.get('variables', []),
            'functions': elements_by_type.get('functions', []),
            'sql': elements_by_type.get('sql', []),
            'includes': elements_by_type.get('includes', []),
            'macros': elements_by_type.get('macros', []),
            'structs': elements_by_type.get('structs', []),
            'comments': elements_by_type.get('comments', []),
            'function_prototypes': elements_by_type.get('function_prototypes', []),
            'preprocessor_directives': elements_by_type.get('preprocessor_directives', []),
            'headers': metadata.get('header_tree', {}).get('all_headers_flat', []),
        }
        
        # 각 유형별로 JSONL 파일 생성
        for type_name, items in export_mapping.items():
            if not items:
                continue
                
            output_path = os.path.join(output_dir, f'{type_name}.jsonl')
            with open(output_path, 'w', encoding='utf-8') as f:
                for item in items:
                    # 각 항목에 소스 파일 정보 추가
                    enriched_item = {
                        '_source_file': source_file,
                        '_source_file_path': source_file_path,
                        **item
                    }
                    f.write(json.dumps(enriched_item, ensure_ascii=False) + '\n')
        
        # 추출된 소스 파일 생성 (_extracted.c)
        self._save_extracted_source(metadata, output_dir)
    
    def _save_extracted_source(self, metadata: Dict, output_dir: str):
        """
        분석 완료된 요소들을 공백으로 치환한 소스 파일 생성
        
        Args:
            metadata: generate()에서 생성된 메타데이터 딕셔너리
            output_dir: 출력 디렉토리 경로
        """
        source_info = metadata.get('metadata', {})
        source_file = source_info.get('source_file', '')
        source_file_path = source_info.get('source_file_path', '')
        
        if not source_file_path or not os.path.exists(source_file_path):
            return
        
        # 원본 소스 읽기
        with open(source_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source_content = f.read()
        
        # 문자 배열로 변환 (수정 가능)
        content_chars = list(source_content)
        
        # 모든 요소에서 byte_start/byte_end 또는 line_start/line_end 수집
        elements_by_type = metadata.get('source_analysis', {}).get('elements_by_type', {})
        
        # 라인 인덱스 계산
        line_indices = [0]
        for i, char in enumerate(source_content):
            if char == '\n':
                line_indices.append(i + 1)
        
        def blank_out_range(start_idx: int, end_idx: int):
            """범위를 공백으로 치환 (줄바꿈 유지)"""
            for i in range(start_idx, min(end_idx, len(content_chars))):
                if content_chars[i] != '\n':
                    content_chars[i] = ' '
        
        # 각 요소 유형별로 공백 처리
        # functions, structs는 제외 - 내부에 파싱되지 않은 요소를 확인할 수 있도록
        exclude_from_blanking = {'unknown', 'functions', 'structs'}
        for type_name, items in elements_by_type.items():
            if type_name in exclude_from_blanking:
                continue
            
            for item in items:
                # byte_start/byte_end가 있으면 사용
                if item.get('byte_start') is not None and item.get('byte_end') is not None:
                    blank_out_range(item['byte_start'], item['byte_end'])
                # 없으면 line_start/line_end로 계산
                elif item.get('line_start') is not None and item.get('line_end') is not None:
                    start_line = item['line_start'] - 1  # 0-indexed
                    end_line = item['line_end'] - 1
                    
                    if start_line < len(line_indices):
                        start_idx = line_indices[start_line]
                        end_idx = (line_indices[end_line + 1] 
                                   if end_line + 1 < len(line_indices) 
                                   else len(source_content))
                        blank_out_range(start_idx, end_idx)
        
        # 파일명 생성
        source_name = os.path.splitext(source_file)[0]
        extracted_filename = f"{source_name}_extracted.c"
        output_path = os.path.join(output_dir, extracted_filename)
        
        # 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(''.join(content_chars))


if __name__ == "__main__":
    import argparse
    
    # 기본 샘플 파일 경로
    default_source = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "sample_input", "original_source.sqc"
    )
    
    parser = argparse.ArgumentParser(description="통합 메타데이터 생성기")
    parser.add_argument("source_file", nargs="?", default=default_source, 
                        help="분석할 Pro*C/SQC 파일 (기본: sample_input/original_source.sqc)")
    parser.add_argument("-o", "--output", default=None, help="출력 파일 경로")
    parser.add_argument("--format", choices=["json", "yaml"], default="json", help="출력 포맷")
    
    args = parser.parse_args()
    
    print(f"소스 파일: {args.source_file}")
    
    # 생성기 초기화
    generator = UnifiedMetadataGenerator(
        include_paths=[os.path.dirname(args.source_file)]
    )
    
    # 메타데이터 생성
    metadata = generator.generate(args.source_file)
    
    # 요약 출력
    summary = metadata.get("source_analysis", {}).get("summary", {})
    print(f"분석 완료: {summary.get('total_elements', 0)}개 요소")
    print(f"유형별: {summary.get('by_type', {})}")
    
    # SQL 중복 정보 출력
    sql_list = metadata.get("source_analysis", {}).get("elements_by_type", {}).get("sql", [])
    dup_count = sum(1 for s in sql_list if s.get("is_duplicate", False))
    if dup_count > 0:
        print(f"중복 SQL: {dup_count}개")
    
    # 출력 파일 저장
    if args.output:
        if args.format == "yaml":
            generator.save_yaml(metadata, args.output)
        else:
            generator.save_json(metadata, args.output)
        print(f"저장 완료: {args.output}")
    else:
        # 출력 파일 미지정 시 콘솔에 JSON 일부 출력
        print("\n=== 메타데이터 미리보기 ===")
        print(json.dumps(metadata.get("metadata", {}), ensure_ascii=False, indent=2))
        print("\n(전체 출력은 -o 옵션으로 파일 저장 필요)")
