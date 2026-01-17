"""
통합 메타데이터 생성기

Pro*C/SQC 파일에서 모든 분석 정보와 재귀적 헤더 정보를 포함한
통합 메타데이터 파일을 생성합니다.
"""
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict

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
    from .c_parser import CParser
    from .sql_converter import SQLConverter
except ImportError:
    from proc_parser.core import ProCParser
    from proc_parser.c_parser import CParser
    from proc_parser.sql_converter import SQLConverter

# CPG 모듈
try:
    from CPG import HeaderAnalyzer
except ImportError:
    from CPG.header_analyzer import HeaderAnalyzer

# header_parser 모듈
try:
    from header_parser import HeaderParser, MacroExtractor, STPParser
except ImportError:
    from header_parser.header_parser import HeaderParser
    from header_parser.macro_extractor import MacroExtractor
    from header_parser.stp_parser import STPParser

# OMM/DBIO/DAO 생성기
try:
    from omm_generator import OMMGenerator
    from dbio_generator import DBIOGenerator
    from dao_generator import DAOGenerator
except ImportError:
    OMMGenerator = None
    DBIOGenerator = None
    DAOGenerator = None

# shared_config
try:
    from shared_config import snake_to_camel, get_jdbc_type
except ImportError:
    def snake_to_camel(s): 
        parts = s.split('_')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])
    def get_jdbc_type(t): 
        return "VARCHAR"


@dataclass
class HeaderEntry:
    """헤더 정보 엔트리"""
    header_name: str
    is_system_header: bool = False
    resolved_path: Optional[str] = None
    found: bool = False
    not_found_reason: Optional[str] = None
    line_number: int = 0
    content: Optional[Dict] = None
    nested_includes: List['HeaderEntry'] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "header_name": self.header_name,
            "is_system_header": self.is_system_header,
            "resolved_path": self.resolved_path,
            "found": self.found,
            "not_found_reason": self.not_found_reason,
            "line_number": self.line_number,
            "content": self.content,
            "nested_includes": [h.to_dict() for h in self.nested_includes]
        }


class UnifiedMetadataGenerator:
    """
    Pro*C/SQC 파일에서 통합 메타데이터를 생성하는 클래스
    
    기존 모듈 활용:
    - ProCParser: 소스 코드 요소 추출
    - HeaderAnalyzer: 헤더 재귀 탐색 및 경로 해결
    - HeaderParser: 헤더 내용 파싱 (db_vars_info, structs 등)
    - MacroExtractor: 매크로 추출
    - OMMGenerator/DBIOGenerator: 아티팩트 생성 (선택)
    """
    
    VERSION = "1.0"
    
    def __init__(
        self, 
        include_paths: Optional[List[str]] = None,
        base_package: str = "com.example.dao",
        generate_artifacts: bool = False
    ):
        """
        Args:
            include_paths: 헤더 파일 검색 경로 리스트
            base_package: OMM/DBIO 생성 시 Java 패키지
            generate_artifacts: OMM/DBIO 아티팩트 생성 여부
        """
        self.include_paths = include_paths or []
        self.base_package = base_package
        self.generate_artifacts = generate_artifacts
        
        # 파서 초기화
        self.proc_parser = ProCParser()
        self.header_analyzer = HeaderAnalyzer(include_paths)
        self.header_parser = HeaderParser()
        self.macro_extractor = MacroExtractor()
        self.stp_parser = STPParser()
        
        # 아티팩트 생성기
        if generate_artifacts and OMMGenerator:
            self.omm_generator = OMMGenerator(base_package=f"{base_package}.dto")
            self.dbio_generator = DBIOGenerator(base_package=base_package)
            self.dao_generator = DAOGenerator(base_package=base_package)
        else:
            self.omm_generator = None
            self.dbio_generator = None
            self.dao_generator = None
        
        # 분석 중 방문한 헤더 추적 (순환 참조 방지)
        self._visited_headers: Set[str] = set()
        # 병합된 매크로 테이블
        self._macro_table: Dict[str, Any] = {}
        # 헤더 파싱 결과 캐시 (경로 -> 파싱 결과)
        self._header_cache: Dict[str, Dict] = {}
    
    def generate(self, source_file: str) -> Dict:
        """
        통합 메타데이터 생성 메인 진입점
        
        Args:
            source_file: Pro*C/SQC 소스 파일 경로
            
        Returns:
            통합 메타데이터 딕셔너리
        """
        self._visited_headers.clear()
        self._macro_table.clear()
        
        source_file = os.path.abspath(source_file)
        source_dir = os.path.dirname(source_file)
        
        # 1. 소스 파일 파싱
        elements = self.proc_parser.parse_file(source_file)
        
        # 2. elements 유형별 정리
        elements_by_type = self._organize_elements_by_type(elements)
        
        # 3. 소스 파일의 매크로 추출하여 테이블에 추가
        with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
            source_content = f.read()
        source_macros = self.macro_extractor.extract(source_content)
        self._update_macro_table(source_macros, source_file)
        
        # 4. include 정보에서 헤더 트리 구축
        includes = [e for e in elements if e['type'] == 'include']
        header_tree = self._build_header_tree(includes, source_dir)
        
        # 5. 변수 크기 매크로 해석
        if 'variables' in elements_by_type:
            self._resolve_variable_sizes(elements_by_type['variables'])
        
        # 6. SQL에 MyBatis 형식 추가 및 중복 감지
        if 'sql' in elements_by_type:
            self._add_mybatis_sql(elements_by_type['sql'])
            self._detect_sql_duplicates(elements_by_type['sql'])
        
        # 6.5. SQL 관계 수집 (Cursor, Dynamic SQL 등)
        sql_relationships = []
        if 'sql' in elements_by_type:
            sql_relationships = self._collect_sql_relationships(elements_by_type['sql'])

        # 7. 병합된 정의 수집
        merged_definitions = self._collect_merged_definitions(header_tree)
        
        # 8. 아티팩트 생성 (선택)
        generated_artifacts = {}
        if self.generate_artifacts:
            generated_artifacts = self._generate_artifacts(
                merged_definitions.get('db_vars_info', {}),
                elements_by_type.get('sql', [])
            )
        
        # 9. 요약 통계
        summary = self._create_summary(elements_by_type)
        summary['total_relationships'] = len(sql_relationships)
        
        # 10. 결과 조립
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
                "all_headers_flat": self._flatten_header_tree(header_tree)
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
    
    def _build_header_tree(
        self, 
        includes: List[Dict], 
        source_dir: str
    ) -> List[HeaderEntry]:
        """재귀적 헤더 트리 구축"""
        result = []
        
        for inc in includes:
            header_name = inc.get('path', '')
            is_system = inc.get('is_system', False)
            line_number = inc.get('line_start', 0)
            
            entry = HeaderEntry(
                header_name=header_name,
                is_system_header=is_system,
                line_number=line_number
            )
            
            if is_system:
                # 시스템 헤더는 탐색하지 않음
                entry.found = False
                entry.not_found_reason = "system_header"
            else:
                # 로컬 헤더 경로 해결
                resolved = self.header_analyzer.resolve_header_path(header_name, source_dir)
                
                if resolved and os.path.exists(resolved):
                    # 순환 참조 확인
                    if resolved in self._visited_headers:
                        entry.found = False
                        entry.not_found_reason = "circular_reference"
                    else:
                        self._visited_headers.add(resolved)
                        entry.resolved_path = resolved
                        entry.found = True
                        
                        # 헤더 내용 파싱
                        entry.content = self._parse_header_content(resolved)
                        
                        # 매크로 테이블 업데이트
                        if entry.content and 'macros' in entry.content:
                            self._update_macro_table(entry.content['macros'], header_name)
                        
                        # 중첩 includes 재귀 처리
                        nested_includes = entry.content.get('includes', []) if entry.content else []
                        if nested_includes:
                            header_dir = os.path.dirname(resolved)
                            entry.nested_includes = self._build_header_tree(
                                nested_includes, header_dir
                            )
                else:
                    entry.found = False
                    entry.not_found_reason = "not_found"
            
            result.append(entry)
        
        return result
    
    def _parse_header_content(self, header_path: str) -> Dict:
        """헤더 파일 내용 파싱 (캐시 지원)"""
        # 캐시 확인
        if header_path in self._header_cache:
            return self._header_cache[header_path]
        
        try:
            with open(header_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 매크로 추출
            macros = self.macro_extractor.extract(content)
            
            # STP 데이터 추출
            stp_data = self.stp_parser.parse(content)
            
            # db_vars_info (구조체 + STP)
            db_vars_info = self.header_parser.parse(content)
            
            # include 문 추출 (재귀용)
            includes = []
            include_infos = self.header_analyzer.extract_includes(content, header_path)
            for inc in include_infos:
                includes.append({
                    'type': 'include',
                    'path': inc.header_name,
                    'is_system': inc.is_system_header,
                    'line_start': inc.line_number
                })
            
            result = {
                "macros": macros,
                "stp_data": stp_data,
                "db_vars_info": db_vars_info,
                "includes": includes
            }
            
            # 캐시에 저장
            self._header_cache[header_path] = result
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def _update_macro_table(self, macros: Dict, source: str):
        """매크로 테이블 업데이트"""
        for name, value in macros.items():
            if name not in self._macro_table:
                self._macro_table[name] = {
                    "value": value,
                    "source": source
                }
    
    def _resolve_variable_sizes(self, variables: List[Dict]):
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
                        elif size in self._macro_table:
                            macro_val = self._macro_table[size]['value']
                            try:
                                resolved.append(int(macro_val))
                            except (ValueError, TypeError):
                                resolved.append(size)  # 해석 불가
                        else:
                            resolved.append(size)  # 미정의 매크로
                    else:
                        resolved.append(size)
                var['resolved_array_sizes'] = resolved
    
    def _add_mybatis_sql(self, sql_elements: List[Dict]):
        """SQL에 MyBatis 형식 추가"""
        import re
        
        for sql in sql_elements:
            normalized = sql.get('normalized_sql', '')
            if normalized:
                # :host_var → #{hostVar, jdbcType=VARCHAR}
                def replace_host_var(match):
                    var_name = match.group(1)
                    camel_name = snake_to_camel(var_name)
                    jdbc_type = get_jdbc_type("char")
                    return "#{" + camel_name + ", jdbcType=" + jdbc_type + "}"
                
                mybatis_sql = re.sub(r':(\w+)', replace_host_var, normalized)
                sql['mybatis_sql'] = mybatis_sql
    
    def _detect_sql_duplicates(self, sql_elements: List[Dict]):
        """
        SQL 중복 감지 - normalized_sql 완전 일치 기준
        
        각 SQL에 다음 필드 추가:
        - is_duplicate: 중복 여부
        - duplicate_group_id: 중복 그룹 ID (dup_001, dup_002, ...)
        - call_sites: 동일 SQL의 모든 호출 위치 목록
        """
        from collections import defaultdict
        
        # 1. normalized_sql 기준으로 그룹화
        sql_groups: Dict[str, List[Dict]] = defaultdict(list)
        
        for sql in sql_elements:
            normalized = sql.get('normalized_sql', '')
            if normalized:
                sql_groups[normalized].append(sql)
        
        # 2. 중복 그룹에 ID 할당 및 필드 추가
        dup_group_counter = 0
        
        for normalized_sql, group in sql_groups.items():
            is_duplicate = len(group) > 1
            
            if is_duplicate:
                dup_group_counter += 1
                group_id = f"dup_{dup_group_counter:03d}"
                
                # 모든 호출 위치 수집
                call_sites = []
                for sql in group:
                    call_sites.append({
                        "sql_id": sql.get('sql_id'),
                        "function": sql.get('function'),
                        "line_start": sql.get('line_start'),
                        "line_end": sql.get('line_end')
                    })
                
                # 각 SQL에 중복 정보 추가
                for sql in group:
                    sql['is_duplicate'] = True
                    sql['duplicate_group_id'] = group_id
                    sql['duplicate_count'] = len(group)
                    sql['call_sites'] = call_sites
                
                if self.generate_artifacts:
                    # 중복된 SQL의 경우 동일한 SQL ID 공유 필요성 검토
                    # 현재는 개별 SQL로 처리하되, 향후 개선 가능
                    pass
            else:
                # 중복이 아닌 경우
                for sql in group:
                    sql['is_duplicate'] = False
                    sql['duplicate_group_id'] = None
                    sql['duplicate_count'] = 1
                    sql['call_sites'] = [{
                        "sql_id": sql.get('sql_id'),
                        "function": sql.get('function'),
                        "line_start": sql.get('line_start'),
                        "line_end": sql.get('line_end')
                    }]
    
    def _collect_sql_relationships(self, sql_elements: List[Dict]) -> List[Dict]:
        """
        SQL 요소에서 관계 정보를 수집 (중복 제거)
        ProCParser가 이미 relationship 필드를 채웠다고 가정
        """
        relationships = {}
        
        for sql in sql_elements:
            rel = sql.get('relationship')
            if rel:
                rel_id = rel.get('relationship_id')
                if rel_id and rel_id not in relationships:
                    # 원본 관계 메타데이터 복원
                    relationships[rel_id] = {
                        "relationship_id": rel_id,
                        "relationship_type": rel.get('relationship_type'),
                        "metadata": rel.get('metadata'),
                        # sql_ids는 메타데이터에 없으므로 여기서 재구성하거나, 
                        # ProCParser가 넣어준 total_in_group 등을 활용
                    }
        
        # SQL ID 목록 재구성 (선택적)
        # relationship 필드에는 sql_ids 목록이 없으므로, 다시 순회하며 구성
        for rel_id in relationships:
            relationships[rel_id]['sql_ids'] = []
            
        for sql in sql_elements:
            rel = sql.get('relationship')
            if rel:
                rel_id = rel.get('relationship_id')
                if rel_id in relationships:
                    relationships[rel_id]['sql_ids'].append(sql.get('sql_id'))
        
        # Dictionary -> List 변환
        return list(relationships.values())

    def _collect_merged_definitions(self, header_tree: List[HeaderEntry]) -> Dict:
        """모든 헤더에서 정의 병합"""
        all_macros = dict(self._macro_table)
        all_structs = {}
        all_db_vars_info = {}
        
        def collect_recursive(headers: List[HeaderEntry]):
            for h in headers:
                if h.content:
                    # structs (db_vars_info에서 추출)
                    if 'db_vars_info' in h.content:
                        for struct_name, struct_info in h.content['db_vars_info'].items():
                            if struct_name not in all_db_vars_info:
                                all_db_vars_info[struct_name] = struct_info
                                all_structs[struct_name] = {
                                    "source": h.header_name,
                                    "fields": struct_info
                                }
                
                # 재귀
                if h.nested_includes:
                    collect_recursive(h.nested_includes)
        
        collect_recursive(header_tree)
        
        return {
            "all_macros": all_macros,
            "all_structs": all_structs,
            "db_vars_info": all_db_vars_info
        }
    
    def _flatten_header_tree(self, headers: List[HeaderEntry], depth: int = 1) -> List[Dict]:
        """헤더 트리를 평탄화"""
        result = []
        
        for h in headers:
            entry = {
                "header_name": h.header_name,
                "depth": depth,
                "found": h.found
            }
            if not h.found and h.not_found_reason:
                entry["reason"] = h.not_found_reason
            result.append(entry)
            
            # 재귀
            if h.nested_includes:
                result.extend(self._flatten_header_tree(h.nested_includes, depth + 1))
        
        return result
    
    def _generate_artifacts(self, db_vars_info: Dict, sql_elements: List[Dict]) -> Dict:
        """OMM/DBIO/DAO 아티팩트 생성"""
        artifacts = {}
        
        # OMM 생성
        if self.omm_generator and db_vars_info:
            omm_artifacts = {}
            for struct_name, struct_info in db_vars_info.items():
                try:
                    content = self.omm_generator.generate(struct_info, struct_name)
                    omm_artifacts[struct_name] = {
                        "content": content,
                        "class_name": struct_name.replace('_t', '').title().replace('_', ''),
                        "package": f"{self.base_package}.dto"
                    }
                except Exception as e:
                    omm_artifacts[struct_name] = {"error": str(e)}
            artifacts["omm"] = omm_artifacts
        
        # DBIO (XML) & DAO (Java) 생성
        if self.dbio_generator and self.dao_generator and sql_elements:
            try:
                # SQL 요소를 변환
                sql_calls = []
                for i, sql in enumerate(sql_elements):
                    sql_calls.append({
                        "name": sql.get('sql_id', f'sql_{i+1}'),
                        "sql_type": sql.get('sql_type', 'select').lower(),
                        "parsed_sql": sql.get('normalized_sql', sql.get('raw_sql', '')),
                        "input_vars": sql.get('input_host_vars', []),
                        "output_vars": sql.get('output_host_vars', [])
                    })
                
                # DBIO 생성
                dbio_content = self.dbio_generator.generate(sql_calls, {}, "GeneratedDao")
                artifacts["dbio"] = {
                    "content": dbio_content,
                    "namespace": f"{self.base_package}.GeneratedDao"
                }
                
                # DAO 생성
                dao_content = self.dao_generator.generate(sql_calls, {}, "GeneratedDao")
                artifacts["dao"] = {
                    "content": dao_content,
                    "interface_name": "GeneratedDao",
                    "package": self.base_package
                }
                
            except Exception as e:
                artifacts["dbio"] = {"error": str(e)}
                artifacts["dao"] = {"error": str(e)}
        
        return artifacts
    
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

