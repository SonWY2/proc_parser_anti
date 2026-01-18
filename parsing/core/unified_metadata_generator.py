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
import re
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
        macro_values = self._build_macro_value_map(macro_table)
        for var in variables:
            array_sizes = var.get('array_sizes', [])
            if not array_sizes:
                var['resolved_array_sizes'] = []
                continue
            resolved = []
            for size in array_sizes:
                if size is None:
                    resolved.append(None)
                elif isinstance(size, int):
                    resolved.append(size)
                elif isinstance(size, float):
                    resolved.append(int(size) if size.is_integer() else size)
                elif isinstance(size, str):
                    resolved.append(self._resolve_size_expression(size, macro_values))
                else:
                    resolved.append(size)
            var['resolved_array_sizes'] = resolved

    def _build_macro_value_map(self, macro_table: Dict[str, Any]) -> Dict[str, Any]:
        macro_values = {}
        for name, info in macro_table.items():
            value = info.get('value') if isinstance(info, dict) else info
            if isinstance(value, str):
                value = self._sanitize_macro_value(value)
                if value.isdigit():
                    value = int(value)
                else:
                    evaluated = self._eval_safe_expression(value)
                    if evaluated is not None:
                        value = evaluated
            if isinstance(value, (int, float)):
                macro_values[name] = value
        return macro_values

    def _sanitize_macro_value(self, value: str) -> str:
        cleaned = value.strip()
        if cleaned.startswith("#define"):
            parts = cleaned.split(None, 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return cleaned

    def _resolve_size_expression(self, size_expr: str, macro_values: Dict[str, Any]) -> Any:
        expr = size_expr.strip()
        if not expr:
            return size_expr
        if expr.isdigit():
            return int(expr)
        replaced = self._replace_macro_tokens(expr, macro_values)
        evaluated = self._eval_safe_expression(replaced)
        if evaluated is not None:
            return evaluated
        return size_expr

    def _replace_macro_tokens(self, expr: str, macro_values: Dict[str, Any]) -> str:
        def replacer(match: re.Match) -> str:
            token = match.group(0)
            if token in macro_values:
                return str(macro_values[token])
            return token
        return re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", replacer, expr)

    def _eval_safe_expression(self, expr: str) -> Optional[Any]:
        cleaned = expr.replace(' ', '')
        if not cleaned:
            return None
        if not re.fullmatch(r"[0-9+\-*/%().]+", cleaned):
            return None
        try:
            value = eval(cleaned, {"__builtins__": {}}, {})
        except Exception:
            return None
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, (int, float)):
            return value
        return None

    
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
