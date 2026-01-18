"""
헤더 프로세서

헤더 파일 트리 구축, 파싱, 매크로 수집을 담당합니다.
"""
import os
from typing import Dict, List, Any, Set, Optional
from dataclasses import dataclass, field

try:
    from ..processor_interface import MetadataProcessor
except ImportError:
    from parsing.core.processor_interface import MetadataProcessor

# HeaderAnalyzer
try:
    from analysis.cpg import HeaderAnalyzer
except ImportError:
    from analysis.cpg.header_analyzer import HeaderAnalyzer

# header_parser 모듈
try:
    from parsing.header import HeaderParser, MacroExtractor, STPParser
except ImportError:
    from parsing.header.header_parser import HeaderParser
    from parsing.header.macro_extractor import MacroExtractor
    from parsing.header.stp_parser import STPParser


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


class HeaderProcessor(MetadataProcessor):
    """
    헤더 파일 처리를 담당하는 프로세서
    
    기능:
    - 재귀적 헤더 트리 구축
    - 헤더 파일 파싱 (매크로, STP, db_vars_info)
    - 매크로 테이블 관리
    - 병합된 정의 수집
    """
    
    def __init__(self, include_paths: Optional[List[str]] = None):
        """
        Args:
            include_paths: 헤더 파일 검색 경로 리스트
        """
        self.include_paths = include_paths or []
        self.header_analyzer = HeaderAnalyzer(self.include_paths)
        self.header_parser = HeaderParser()
        self.macro_extractor = MacroExtractor()
        self.stp_parser = STPParser()
        
        # 내부 상태
        self._visited_headers: Set[str] = set()
        self._macro_table: Dict[str, Any] = {}
        self._header_cache: Dict[str, Dict] = {}
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        헤더 처리 수행
        
        Args:
            context:
                - includes: include 요소 목록
                - source_dir: 소스 디렉토리
                - source_content: 소스 파일 내용
                - source_file: 소스 파일 경로
                
        Returns:
            - header_tree: HeaderEntry 목록 (to_dict 변환 전)
            - all_headers_flat: 평탄화된 헤더 목록
            - macro_table: 매크로 딕셔너리
            - merged_definitions: 병합된 정의
        """
        self._reset()
        
        includes = context.get('includes', [])
        source_dir = context.get('source_dir', '')
        source_content = context.get('source_content', '')
        source_file = context.get('source_file', '')
        
        # 1. 소스 파일의 매크로 추출
        source_macros = self.macro_extractor.extract(source_content)
        self._update_macro_table(source_macros, source_file)
        
        # 2. 헤더 트리 구축
        header_tree = self._build_header_tree(includes, source_dir)
        
        # 3. 병합된 정의 수집
        merged_definitions = self._collect_merged_definitions(header_tree)
        
        return {
            "header_tree": header_tree,
            "all_headers_flat": self._flatten_header_tree(header_tree),
            "macro_table": dict(self._macro_table),
            "merged_definitions": merged_definitions
        }
    
    def _reset(self):
        """내부 상태 초기화"""
        self._visited_headers.clear()
        self._macro_table.clear()
        # 캐시는 유지 (성능 최적화)
    
    def get_macro_table(self) -> Dict[str, Any]:
        """현재 매크로 테이블 반환"""
        return dict(self._macro_table)
    
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
