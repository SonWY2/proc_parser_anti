"""
Pro*C 파서의 핵심 로직을 담당하는 모듈입니다.
Pro*C 파일을 읽어 SQL, C 코드, 매크로 등 다양한 요소를 추출하고
플러그인을 통해 관계를 분석합니다.
"""
from .patterns import *
from .c_parser import CParser
from .sql_converter import SQLConverter
from .plugins.bam_call import BamCallPlugin
from .plugins.cursor_relationship import CursorRelationshipPlugin
from .plugins.dynamic_sql_relationship import DynamicSQLRelationshipPlugin
from .plugins.transaction_relationship import TransactionRelationshipPlugin
from .plugins.array_dml_relationship import ArrayDMLRelationshipPlugin
from .plugins.naming_convention import SnakeToCamelPlugin
import re

class ProCParser:
    def __init__(self):
        self.c_parser = CParser()
        # 네이밍 컨벤션 플러그인 초기화
        self.naming_convention = SnakeToCamelPlugin()
        self.sql_converter = SQLConverter(naming_convention=self.naming_convention)
        
        # 코드 요소 플러그인 초기화
        self.plugins = [
            BamCallPlugin()
        ]
        
        # SQL 관계 플러그인 초기화
        self.sql_relationship_plugins = [
            CursorRelationshipPlugin(),
            DynamicSQLRelationshipPlugin(),
            TransactionRelationshipPlugin(),
            ArrayDMLRelationshipPlugin()
        ]

    def parse_file(self, file_path, external_macros: dict = None):
        """
        단일 파일을 파싱하는 메인 메서드입니다.
        
        Args:
            file_path: 파싱할 Pro*C 파일 경로
            external_macros: 외부에서 주입할 매크로 딕셔너리 (예: {"MAX_SIZE": "100"})
                             파일 내 매크로보다 우선순위가 낮음 (파일 매크로가 덮어씀)
        
        Returns:
            파싱된 요소 목록
        """
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
                "function": None, # 나중에 스코프 해결로 채워짐
                "relationship": None  # 관계 플러그인에 의해 채워짐
            }
            element.update(normalized_data)
            elements.append(element)
            sql_id_counter += 1
            
            # C 파서를 위해 SQL 공백 처리
            blank_out(match.start(), match.end())

        # 플러그인 (예: BAMCALL)
        for plugin in self.plugins:
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
        
        # 행/열을 인덱스로 변환하는 헬퍼
        line_indices = [0]
        for i, char in enumerate(content):
            if char == '\n':
                line_indices.append(i + 1)
        
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
        
        for plugin in self.sql_relationship_plugins:
            try:
                if plugin.can_handle(sql_elements):
                    rels = plugin.extract_relationships(sql_elements, elements)
                    all_relationships.extend(rels)
            except Exception as e:
                # 오류를 로깅하지만 다른 플러그인으로 계속 진행
                print(f"Warning: Relationship plugin {plugin.__class__.__name__} failed: {e}")
        
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
        
        return elements
