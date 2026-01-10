"""
Pro*C 파서의 핵심 로직을 담당하는 모듈입니다.
Pro*C 파일을 읽어 SQL, C 코드, 매크로 등 다양한 요소를 추출하고
플러그인을 통해 관계를 분석합니다.
"""
from .patterns import *
from .c_parser import CParser
from .sql_converter import SQLConverter

# Pro*C 전용 플러그인 (proc_parser에 유지)
from .plugins.bam_call import BamCallPlugin
from .plugins.naming_convention import SnakeToCamelPlugin
from .plugins.docstring_enricher import DocstringEnricherPlugin

import re
import os
import sys

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config.logger import logger

# SQL 관계 플러그인 (sql_extractor에서 import)
try:
    from sql_extractor.plugins import (
        CursorRelationshipPlugin,
        DynamicSQLRelationshipPlugin,
        TransactionRelationshipPlugin,
        ArrayDMLRelationshipPlugin,
    )
    HAS_SQL_RELATIONSHIP_PLUGINS = True
except ImportError:
    HAS_SQL_RELATIONSHIP_PLUGINS = False
    CursorRelationshipPlugin = None
    DynamicSQLRelationshipPlugin = None
    TransactionRelationshipPlugin = None
    ArrayDMLRelationshipPlugin = None
    logger.warning("sql_extractor.plugins 사용 불가 - SQL 관계 분석 비활성화")

# sql_extractor 어댑터 (선택적 import)
try:
    from sql_extractor import ProcParserSQLAdapter
    HAS_SQL_EXTRACTOR = True
except ImportError:
    HAS_SQL_EXTRACTOR = False
    ProcParserSQLAdapter = None


class ProCParser:
    def __init__(self):
        logger.debug("ProCParser 초기화 시작")
        self.c_parser = CParser()
        
        # 플러그인 딕셔너리 (카테고리별 리스트)
        self.plugins = {
            # 네이밍 변환 플러그인
            "naming": [
                SnakeToCamelPlugin()
            ],
            # 코드 요소 추출 플러그인 (정규식 기반)
            "code_element": [
                BamCallPlugin()
            ],
            # SQL 관계 분석 플러그인 (sql_extractor에서 로드)
            "sql_relationship": self._init_sql_relationship_plugins(),
            # 요소 보강 플러그인
            "element_enricher": [
                DocstringEnricherPlugin()
            ],
            # SQL 변환 플러그인 (sql_extractor 연계)
            "sql_transform": self._init_sql_transform_plugins(),
        }
        
        # 편의를 위한 단축 속성 (하위 호환성)
        self.naming_convention = self.plugins["naming"][0] if self.plugins["naming"] else None
        self.sql_converter = SQLConverter(naming_convention=self.naming_convention)
        
        # sql_extractor 어댑터 초기화 (가능한 경우)
        self.sql_adapter = ProcParserSQLAdapter() if HAS_SQL_EXTRACTOR else None
        self.use_sql_extractor = HAS_SQL_EXTRACTOR
        
        # 플러그인 로깅
        total_plugins = sum(len(v) for v in self.plugins.values())
        logger.debug(f"ProCParser 초기화 완료 (플러그인: {total_plugins}개, sql_extractor={HAS_SQL_EXTRACTOR})")
    
    def _init_sql_relationship_plugins(self):
        """SQL 관계 플러그인 초기화 (sql_extractor에서 로드)"""
        if not HAS_SQL_RELATIONSHIP_PLUGINS:
            return []
        
        plugins = []
        if CursorRelationshipPlugin:
            plugins.append(CursorRelationshipPlugin())
        if DynamicSQLRelationshipPlugin:
            plugins.append(DynamicSQLRelationshipPlugin())
        if TransactionRelationshipPlugin:
            plugins.append(TransactionRelationshipPlugin())
        if ArrayDMLRelationshipPlugin:
            plugins.append(ArrayDMLRelationshipPlugin())
        
        logger.debug(f"SQL 관계 플러그인 {len(plugins)}개 로드 완료")
        return plugins
    
    def _init_sql_transform_plugins(self):
        """SQL 변환 플러그인 초기화 (sql_extractor에서 로드)"""
        plugins = []
        try:
            from sql_extractor.transform_plugins import CommentRemovalPlugin
            plugins.append(CommentRemovalPlugin())
            logger.debug("CommentRemovalPlugin 로드 완료")
        except ImportError:
            logger.debug("sql_extractor.transform_plugins 사용 불가")
        return plugins

    def parse_file(self, file_path, external_macros: dict = None,
                   output_dir: str = None, create_debug_file: bool = False):
        """
        단일 파일을 파싱하는 메인 메서드입니다.
        
        Args:
            file_path: 파싱할 Pro*C 파일 경로
            external_macros: 외부에서 주입할 매크로 딕셔너리 (예: {"MAX_SIZE": "100"})
                             파일 내 매크로보다 우선순위가 낮음 (파일 매크로가 덮어씀)
            output_dir: 디버깅 파일 출력 디렉토리 (create_debug_file=True 시 필수)
            create_debug_file: True이면 SQL을 주석으로 치환한 디버깅 파일 생성
        
        Returns:
            파싱된 요소 목록
        """
        logger.info(f"파일 파싱 시작: {file_path}")
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # 외부 매크로로 매크로 테이블 초기화
        macro_table = dict(external_macros) if external_macros else {}
            
        elements = []
        
        # Tree-sitter의 구문 오류를 방지하기 위해 Pro*C 구문을 공백으로 처리한
        # C 파싱용 콘텐츠 버전을 생성합니다.
        c_parsing_content = list(content)
        
        # 알 수 없는 요소 감지를 위해 커버된 영역 추적
        # Boolean 리스트, 커버된 경우 True
        covered_map = [False] * len(content)
        
        def mark_covered(start, end):
            for i in range(start, end):
                covered_map[i] = True
        
        def blank_out(start, end):
            for i in range(start, end):
                if c_parsing_content[i] != '\n':
                    c_parsing_content[i] = ' '
            mark_covered(start, end)

        # 행/열을 인덱스로 변환하는 헬퍼 (미리 계산)
        line_indices = [0]
        for i, char in enumerate(content):
            if char == '\n':
                line_indices.append(i + 1)

        # 1. Regex를 사용하여 Pro*C 특정 요소(SQL, 매크로 등) 추출
        
        # 인클루드
        for match in PATTERN_INCLUDE.finditer(content):
            elements.append({
                "type": "include",
                "path": match.group(2),
                "is_system": match.group(1) == '<',
                "line_start": content.count('\n', 0, match.start()) + 1,
                "line_end": content.count('\n', 0, match.end()) + 1,
                "raw_content": match.group(0),
                "function": None # 대개 전역
            })
            mark_covered(match.start(), match.end())
            
        # 매크로
        for match in PATTERN_MACRO.finditer(content):
            macro_name = match.group(1)
            macro_value = match.group(2)
            
            elements.append({
                "type": "macro",
                "name": macro_name,
                "value": macro_value,
                "line_start": content.count('\n', 0, match.start()) + 1,
                "line_end": content.count('\n', 0, match.end()) + 1,
                "raw_content": match.group(0),
                "function": None
            })
            mark_covered(match.start(), match.end())
            
            # 매크로 테이블에 추가 (파일 매크로가 외부 매크로를 덮어씀)
            if macro_value is not None:
                macro_table[macro_name] = macro_value.strip()

        # SQL 블록
        if self.use_sql_extractor and self.sql_adapter:
            # sql_extractor 사용 (고급 파싱)
            self.sql_adapter.reset_counter()
            sql_elements = self.sql_adapter.extract_sql_elements_as_dicts(content)
            
            for el in sql_elements:
                el['function'] = None  # 스코프 해결 전
                el['relationship'] = None  # 관계 플러그인이 채움
                elements.append(el)
                
                # C 파서를 위해 SQL 공백 처리 (라인 기반)
                start_line = el.get('line_start', 1) - 1
                end_line = el.get('line_end', 1) - 1
                if start_line < len(line_indices) and end_line < len(line_indices):
                    start_idx = line_indices[start_line] if start_line < len(line_indices) else 0
                    end_idx = line_indices[end_line + 1] if end_line + 1 < len(line_indices) else len(content)
                    blank_out(start_idx, end_idx)
                elif el.get('byte_start') is not None and el.get('byte_end') is not None:
                    blank_out(el['byte_start'], el['byte_end'])
        else:
            # 기존 정규식 기반 SQL 추출 (fallback)
            sql_id_counter = 1
            for match in PATTERN_SQL.finditer(content):
                raw_sql = match.group(0)
                normalized_data = self.sql_converter.normalize_sql(raw_sql)
                
                element = {
                    "type": "sql",
                    "sql_id": f"sql_{sql_id_counter:03d}",
                    "line_start": content.count('\n', 0, match.start()) + 1,
                    "line_end": content.count('\n', 0, match.end()) + 1,
                    "raw_content": raw_sql,
                    "function": None,
                    "relationship": None
                }
                element.update(normalized_data)
                elements.append(element)
                sql_id_counter += 1
                
                blank_out(match.start(), match.end())

        # 코드 요소 플러그인 (예: BAMCALL)
        for plugin in self.plugins["code_element"]:
            for match in plugin.pattern.finditer(content):
                element = plugin.parse(match, content)
                elements.append(element)
                blank_out(match.start(), match.end())

        # 주석
        for match in PATTERN_COMMENT_SINGLE.finditer(content):
            elements.append({
                "type": "comment",
                "is_multiline": False,
                "line_start": content.count('\n', 0, match.start()) + 1,
                "line_end": content.count('\n', 0, match.end()) + 1,
                "raw_content": match.group(0),
                "function": None
            })
            mark_covered(match.start(), match.end())
            
        for match in PATTERN_COMMENT_MULTI.finditer(content):
            elements.append({
                "type": "comment",
                "is_multiline": True,
                "line_start": content.count('\n', 0, match.start()) + 1,
                "line_end": content.count('\n', 0, match.end()) + 1,
                "raw_content": match.group(0),
                "function": None
            })
            mark_covered(match.start(), match.end())

        # 2. Tree-sitter를 사용하여 C 요소 추출
        c_source = "".join(c_parsing_content)
        c_elements = self.c_parser.parse(c_source)
        
        # 2.5. 요소 보강 플러그인 실행
        for plugin in self.plugins["element_enricher"]:
            for el in c_elements:
                try:
                    if plugin.can_handle(el):
                        plugin.enrich(el, c_elements, content)
                except Exception as e:
                    logger.warning(f"Element enricher plugin {plugin.__class__.__name__} failed: {e}")
        
        def get_index(row, col):
            if row >= len(line_indices): return len(content)
            return line_indices[row] + col

        # 3. 병합 및 스코프 해결
        # 먼저 함수를 다른 C 요소와 분리
        functions = [e for e in c_elements if e['type'] == 'function']
        
        # 모든 C 요소를 메인 리스트에 추가
        elements.extend(c_elements)

        # 시작 라인 기준 정렬
        elements.sort(key=lambda x: x['line_start'])
        
        # DECLARE SECTION 범위 추출
        declare_sections = []
        for match in PATTERN_DECLARE_SECTION.finditer(content):
            start_line = content.count('\n', 0, match.start()) + 1
            end_line = content.count('\n', 0, match.end()) + 1
            declare_sections.append((start_line, end_line))
        
        # 스코프 해결
        for el in elements:
            if el['type'] == 'function': continue 
            if el.get('function'): continue 
            
            for func in functions:
                if func['line_start'] <= el['line_start'] and func['line_end'] >= el['line_end']:
                    el['function'] = func['name']
                    break
        
        # 변수 스코프 분류
        for el in elements:
            if el['type'] != 'variable':
                continue
            
            # 스코프 분류 우선순위:
            # 1. declare_section: DECLARE SECTION 내부
            # 2. static: storage_class가 static인 경우
            # 3. global: 함수 외부에 선언된 경우
            # 4. local: 함수 내부에 선언된 경우
            
            is_in_declare_section = any(
                start <= el['line_start'] <= end 
                for start, end in declare_sections
            )
            
            if is_in_declare_section:
                el['scope'] = 'declare_section'
            elif el.get('storage_class') == 'static':
                if el.get('function'):
                    el['scope'] = 'static_local'
                else:
                    el['scope'] = 'static'
            elif el.get('function') is None:
                el['scope'] = 'global'
            else:
                el['scope'] = 'local'
        
        # 배열 크기 매크로 치환
        for el in elements:
            if el['type'] != 'variable':
                continue
            
            array_sizes = el.get('array_sizes', [])
            if not array_sizes:
                el['resolved_array_sizes'] = []
                continue
            
            resolved = []
            for size in array_sizes:
                if size is None:
                    resolved.append(None)
                elif size in macro_table:
                    resolved.append(macro_table[size])
                else:
                    resolved.append(size)  # 숫자 리터럴이거나 정의되지 않은 매크로
            el['resolved_array_sizes'] = resolved
        
        # 3.5. SQL 관계 추출
        # SQL 요소에 대해 관계 플러그인 실행
        sql_elements = [e for e in elements if e['type'] == 'sql']
        all_relationships = []
        
        for plugin in self.plugins["sql_relationship"]:
            try:
                if plugin.can_handle(sql_elements):
                    rels = plugin.extract_relationships(sql_elements, elements)
                    all_relationships.extend(rels)
            except Exception as e:
                # 오류를 로깅하지만 다른 플러그인으로 계속 진행
                logger.warning(f"Relationship plugin {plugin.__class__.__name__} failed: {e}")
        
        # 관계 정보를 SQL 요소에 다시 주입
        for rel in all_relationships:
            for i, sql_id in enumerate(rel['sql_ids']):
                for el in sql_elements:
                    if el.get('sql_id') == sql_id:
                        el['relationship'] = {
                            'relationship_id': rel['relationship_id'],
                            'relationship_type': rel['relationship_type'],
                            'sequence_in_group': i + 1,
                            'total_in_group': len(rel['sql_ids']),
                            'metadata': rel.get('metadata', {})
                        }
                        break
        
        # 4. 알 수 없는 요소 감지
        for el in c_elements:
            start_line = el['line_start'] - 1
            end_line = el['line_end'] - 1
            
            start_idx = line_indices[start_line] if start_line < len(line_indices) else len(content)
            
            # 지금은 전체 라인을 커버된 것으로 표시.
            if start_line < len(line_indices):
                s = line_indices[start_line]
                e = line_indices[end_line+1] if end_line+1 < len(line_indices) else len(content)
                mark_covered(s, e)

        # 커버되지 않은 영역 찾기
        unknowns = []
        current_start = -1
        
        for i in range(len(content)):
            if not covered_map[i]:
                char = content[i]
                if not char.isspace(): # 공백 무시
                    if current_start == -1:
                        current_start = i
            else:
                if current_start != -1:
                    # 알 수 없는 블록의 끝
                    # 공백/세미콜론만 있는지 확인
                    raw = content[current_start:i]
                    if raw.strip() and raw.strip() != ';':
                        unknowns.append({
                            "type": "unknown",
                            "line_start": content.count('\n', 0, current_start) + 1,
                            "line_end": content.count('\n', 0, i) + 1,
                            "raw_content": raw,
                            "function": None
                        })
                    current_start = -1
        
        # 후행 알 수 없는 요소 확인
        if current_start != -1:
            raw = content[current_start:]
            if raw.strip() and raw.strip() != ';':
                unknowns.append({
                    "type": "unknown",
                    "line_start": content.count('\n', 0, current_start) + 1,
                    "line_end": content.count('\n', 0, len(content)) + 1,
                    "raw_content": raw,
                    "function": None
                })

        # 알 수 없는 요소에 대한 스코프 해결
        for el in unknowns:
             for func in functions:
                if func['line_start'] <= el['line_start'] and func['line_end'] >= el['line_end']:
                    el['function'] = func['name']
                    break
        
        elements.extend(unknowns)
        elements.sort(key=lambda x: x['line_start'])
        
        # 디버깅 파일 생성
        if create_debug_file:
            self._create_debug_file(content, elements, file_path, output_dir)
        
        sql_count = len([e for e in elements if e['type'] == 'sql'])
        func_count = len([e for e in elements if e['type'] == 'function'])
        logger.success(f"파일 파싱 완료: {file_path} (요소: {len(elements)}개, SQL: {sql_count}, 함수: {func_count})")
        
        return elements
    
    def _generate_sql_marker(self, sql_element: dict) -> str:
        """
        SQL 요소에 대한 디버깅 마커 주석 생성
        
        Format: /* @SQL_EXTRACTED: {sql_id} | TYPE: {sql_type} | IN: {inputs} | OUT: {outputs} */
        
        Args:
            sql_element: SQL 요소 딕셔너리
            
        Returns:
            주석 문자열
        """
        sql_id = sql_element.get('sql_id', 'unknown')
        sql_type = sql_element.get('sql_type', 'UNKNOWN')
        
        input_vars = sql_element.get('input_host_vars', [])
        output_vars = sql_element.get('output_host_vars', [])
        
        # 변수 목록 축약 (너무 길면 잘라냄)
        inputs_str = ', '.join(input_vars[:5])
        if len(input_vars) > 5:
            inputs_str += f", ... (+{len(input_vars) - 5})"
        
        outputs_str = ', '.join(output_vars[:5])
        if len(output_vars) > 5:
            outputs_str += f", ... (+{len(output_vars) - 5})"
        
        # 마커 생성
        parts = [f"@SQL_EXTRACTED: {sql_id}", f"TYPE: {sql_type}"]
        if inputs_str:
            parts.append(f"IN: {inputs_str}")
        if outputs_str:
            parts.append(f"OUT: {outputs_str}")
        
        return f"/* {' | '.join(parts)} */"
    
    def _create_debug_file(self, original_content: str, elements: list, 
                          source_file_path: str, output_dir: str):
        """
        SQL을 주석으로 치환한 디버깅 파일 생성
        
        Args:
            original_content: 원본 파일 내용
            elements: 파싱된 요소 리스트
            source_file_path: 원본 파일 경로
            output_dir: 출력 디렉토리
        """
        if not output_dir:
            print("Warning: output_dir not specified. Debug file not created.")
            return
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        
        # 원본 내용을 라인 단위로 분리
        lines = original_content.split('\n')
        
        # 치환 정보 수집: [(start_line, end_line, marker), ...]
        replacements = []
        
        # 1. SQL 요소 처리
        sql_elements = [e for e in elements if e.get('type') == 'sql']
        for sql in sql_elements:
            start_line = sql.get('line_start', 1) - 1  # 0-indexed
            end_line = sql.get('line_end', 1) - 1
            marker = self._generate_sql_marker(sql)
            replacements.append((start_line, end_line, marker))
        
        # 2. 플러그인 요소 처리 (get_marker가 있는 경우)
        for plugin in self.plugins:
            plugin_elements = [e for e in elements if e.get('type') == plugin.element_type]
            for el in plugin_elements:
                marker = plugin.get_marker(el)
                if marker:  # 마커가 None이 아닌 경우만 치환
                    start_line = el.get('line_start', 1) - 1
                    end_line = el.get('line_end', 1) - 1
                    replacements.append((start_line, end_line, marker))
        
        # 역순으로 치환 (뒤에서부터 처리해야 인덱스가 꼬이지 않음)
        replacements.sort(key=lambda x: x[0], reverse=True)
        
        for start_line, end_line, marker in replacements:
            if start_line < len(lines):
                # 원래 줄의 들여쓰기 유지
                original_indent = ''
                if start_line < len(lines):
                    leading_spaces = len(lines[start_line]) - len(lines[start_line].lstrip())
                    original_indent = lines[start_line][:leading_spaces]
                
                # 해당 라인들을 마커로 치환
                marker_with_indent = original_indent + marker
                lines[start_line:end_line + 1] = [marker_with_indent]
        
        # 파일명 생성
        source_basename = os.path.basename(source_file_path)
        source_name, _ = os.path.splitext(source_basename)
        debug_filename = f"{source_name}_sql_extracted.c"
        debug_file_path = os.path.join(output_dir, debug_filename)
        
        # 파일 저장
        with open(debug_file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"Debug file created: {debug_file_path}")
