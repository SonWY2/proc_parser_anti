"""
SQL 추출기 메인 모듈

Pro*C/SQLC 코드에서 SQL 문을 추출하고 분해하는 SQLExtractor 클래스를 제공합니다.
Tree-sitter 기반 추출과 규칙 기반 타입 결정을 사용합니다.
"""

import re
import os
import logging
from typing import Dict, List, Optional, Any, Tuple, Callable

from .types import SqlType, ExtractedSQL, HostVariable, HostVariableType, VariableDirection
from .config import SQLExtractorConfig
from .registry import SQLTypeRegistry, HostVariableRegistry
from .tree_sitter_extractor import TreeSitterSQLExtractor, SQLBlock, get_tree_sitter_extractor

# 신규 모듈
from .mybatis_converter import MyBatisConverter, MyBatisSQL, default_input_formatter, default_output_formatter
from .sql_id_generator import SQLIdGenerator
from .comment_marker import SQLCommentMarker, default_comment_formatter
from .cursor_merger import CursorMerger, CursorGroup, MergedCursorSQL
from .dynamic_sql_extractor import DynamicSQLExtractor, DynamicSQL

logger = logging.getLogger(__name__)


class SQLExtractor:
    """SQL 관련 코드 분해
    
    Tree-sitter 기반 SQL 추출과 규칙 기반 타입 결정을 사용합니다.
    
    기존 SQLExtractor 클래스와 동일한 인터페이스를 제공합니다:
    - decompose_declare_section()
    - decompose_sql()
    - create_sql_commented_version()
    - map_sql_to_functions()
    
    새로운 기능:
    - 규칙 기반 SQL 타입 결정 (SQLTypeRegistry)
    - 규칙 기반 호스트 변수 추출 (HostVariableRegistry)
    - Tree-sitter 기반 정확한 SQL 블록 추출
    
    Example:
        extractor = SQLExtractor()
        
        # DB2 규칙 추가
        extractor.sql_type_registry.load_db2_rules()
        
        # SQL 분해
        code, sqls = extractor.decompose_sql(code, "program", {})
    """
    
    def __init__(
        self,
        file_manager: Any = None,
        code_analyzer: Any = None,
        config: SQLExtractorConfig = None
    ):
        """SQLExtractor 초기화
        
        Args:
            file_manager: 파일 관리자 (기존 호환성)
            code_analyzer: 코드 분석기 (기존 호환성)
            config: SQL 추출기 설정
        """
        self.file_manager = file_manager
        self.code_analyzer = code_analyzer
        self.config = config or SQLExtractorConfig()
        
        # Tree-sitter 추출기 초기화
        self.tree_sitter_extractor = get_tree_sitter_extractor()
        self.use_tree_sitter = self.tree_sitter_extractor is not None
        
        if self.use_tree_sitter:
            logger.info("SQLExtractor: Tree-sitter 기반 추출 사용")
        else:
            logger.warning("SQLExtractor: Tree-sitter 없음, 정규식 fallback 사용")
        
        # 규칙 레지스트리 초기화
        self.sql_type_registry = SQLTypeRegistry()
        self.sql_type_registry.load_defaults()
        
        # config를 전달하여 PARSER_MODE 설정 적용
        self.host_var_registry = HostVariableRegistry(config=self.config)
        self.host_var_registry.load_defaults()
        
        # 파서 모드 로깅
        parser_mode = self.config.PARSER_MODE
        logger.info(
            f"SQLExtractor initialized: "
            f"{self.sql_type_registry.rule_count} SQL type rules, "
            f"{self.host_var_registry.rule_count} host variable rules, "
            f"parser_mode={parser_mode}"
        )
        
        # MyBatis 변환 관련 컴포넌트 (지연 초기화)
        self._mybatis_converter: Optional[MyBatisConverter] = None
        self._id_generator: Optional[SQLIdGenerator] = None
        self._comment_marker: Optional[SQLCommentMarker] = None
        self._cursor_merger: Optional[CursorMerger] = None
        self._dynamic_sql_extractor: Optional[DynamicSQLExtractor] = None
    
    def decompose_declare_section(
        self, code: str, file_key: str, program_dict: Dict
    ) -> str:
        """DECLARE SECTION 분해
        
        Args:
            code: 소스 코드
            file_key: 파일 키 (프로그램명)
            program_dict: 프로그램 정보 딕셔너리
        
        Returns:
            DECLARE SECTION이 제거된 코드
        """
        matches = list(
            re.finditer(
                r"EXEC SQL BEGIN DECLARE SECTION;([\s\S]*?)EXEC SQL END DECLARE SECTION;",
                code,
            )
        )
        
        result_code = code
        if matches:
            program_dict["declare_section_files"] = []
            
            for i, m in enumerate(matches):
                output_path = self._get_output_path()
                file_path = os.path.join(
                    output_path,
                    file_key,
                    "sql",
                    f"declare_section_{i}.c",
                )
                
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(m.group(0))
                
                program_dict["declare_section_files"].append(file_path)
                result_code = self._find_and_replace(result_code, m.group(0), "")
        
        return result_code
    
    def decompose_sql(
        self, code: str, file_key: str, program_dict: Dict, variables: List[Dict] = None
    ) -> str:
        """SQL 문 분해
        
        Args:
            code: 소스 코드
            file_key: 파일 키 (프로그램명)
            program_dict: 프로그램 정보 딕셔너리
            variables: 변수 목록 (기존 호환성)
        
        Returns:
            SQL이 sql_call()로 대체된 코드
        """
        asis_sqls = []
        result_code = code
        
        # Tree-sitter 또는 정규식으로 SQL 추출
        if self.use_tree_sitter:
            sql_blocks = self._extract_with_tree_sitter(code)
        else:
            sql_blocks = self._extract_with_regex(code)
        
        name_count = {"select": 0, "insert": 0, "update": 0, "delete": 0}
        
        for i, block in enumerate(sql_blocks):
            # SQL 타입 결정 (규칙 기반)
            result = self.sql_type_registry.determine_type(block.text)
            sql_type = result.value
            
            if sql_type == "include":
                result_code = self._find_and_replace(result_code, block.text, "")
                continue
            
            sql_id = f"sql_{i}"
            sql_name = self._generate_sql_name(sql_type, name_count)
            
            # 호스트 변수 추출
            host_vars = self.host_var_registry.extract_all(block.text)
            input_vars, output_vars = self.host_var_registry.classify_by_direction(
                block.text, sql_type
            )
            
            asis_sqls.append({
                "id": sql_id,
                "sql": block.text.lstrip(),
                "sql_type": sql_type,
                "name": sql_name,
                "line_start": block.start_line,
                "line_end": block.end_line,
                "function_name": block.containing_function,
                "host_variables": [v.get('raw', '') for v in host_vars],
                "input_vars": [v.get('raw', '') for v in input_vars],
                "output_vars": [v.get('raw', '') for v in output_vars],
                "metadata": result.metadata if result.metadata else {},
            })
            
            # SQL 호출로 교체
            indent = self._get_indent(block.text)
            replacement = (
                indent + self.config.SQL_CALL_FORMAT.format(
                    sql_id=sql_id, sql_name=sql_name
                ) + "\n"
            )
            result_code = self._find_and_replace(result_code, block.text, replacement)
        
        # SQL 호출 정보 저장
        if asis_sqls:
            self._save_sql_calls(asis_sqls, file_key)
        
        return result_code
    
    def _extract_with_tree_sitter(self, code: str) -> List[SQLBlock]:
        """Tree-sitter로 SQL 추출"""
        # 함수 목록 먼저 추출
        functions = self.tree_sitter_extractor.get_functions(code)
        return self.tree_sitter_extractor.extract_sql_blocks(code, functions)
    
    def _extract_with_regex(self, code: str) -> List[SQLBlock]:
        """정규식으로 SQL 추출 (fallback)
        
        개선: 주석 내 EXEC SQL 제외, 문자열 내 세미콜론 고려
        """
        import re
        
        blocks = []
        
        # C 주석 영역 찾기
        comment_ranges = []
        for match in re.finditer(r'/\*[\s\S]*?\*/', code):
            comment_ranges.append((match.start(), match.end()))
        for match in re.finditer(r'//[^\n]*', code):
            comment_ranges.append((match.start(), match.end()))
        
        def is_in_comment(pos):
            for start, end in comment_ranges:
                if start <= pos < end:
                    return True
            return False
        
        def find_sql_end(start_pos):
            """문자열 리터럴을 고려하여 세미콜론 찾기"""
            in_string = False
            quote_char = None
            i = start_pos
            
            while i < len(code):
                char = code[i]
                
                if char in ("'", '"'):
                    if not in_string:
                        in_string = True
                        quote_char = char
                    elif char == quote_char:
                        if i > 0 and code[i-1] != '\\':
                            if i + 1 < len(code) and code[i+1] == char:
                                i += 1
                            else:
                                in_string = False
                
                if char == ';' and not in_string:
                    return i + 1
                
                i += 1
            return -1
        
        # EXEC SQL 시작점 찾기
        for match in re.finditer(r'EXEC\s+SQL\b', code, re.IGNORECASE):
            start_pos = match.start()
            
            # 주석 내에 있으면 스킵
            if is_in_comment(start_pos):
                continue
            
            # 세미콜론까지 찾기
            end_pos = find_sql_end(start_pos)
            if end_pos == -1:
                continue
            
            text = code[start_pos:end_pos]
            if not text.strip():
                continue
            
            start_line = code[:start_pos].count('\n') + 1
            end_line = code[:end_pos].count('\n') + 1
            
            blocks.append(SQLBlock(
                text=text,
                start_byte=start_pos,
                end_byte=end_pos,
                start_line=start_line,
                end_line=end_line,
                containing_function=None
            ))
        
        return blocks
    
    def create_sql_commented_version(self, code: str, file_key: str) -> str:
        """SQL 구문을 주석으로 표시한 버전 생성"""
        result_code = code
        
        if self.use_tree_sitter:
            sql_blocks = self._extract_with_tree_sitter(code)
        else:
            sql_blocks = self._extract_with_regex(code)
        
        name_count = {"select": 0, "insert": 0, "update": 0, "delete": 0}
        sql_counter = 0
        
        for block in sql_blocks:
            try:
                result = self.sql_type_registry.determine_type(block.text)
                sql_type = result.value
                
                if sql_type == "include":
                    result_code = self._find_and_replace(result_code, block.text, "")
                    continue
                
                indent = self._get_indent(block.text)
                sql_id = f"sql_{sql_counter}"
                
                comment = self.config.SQL_COMMENT_FORMAT.format(
                    sql_id=sql_id, 
                    sql_type=sql_type.upper(), 
                    desc="설명 없음"
                )
                
                result_code = self._find_and_replace(
                    result_code, block.text, indent + comment
                )
                sql_counter += 1
                
            except Exception as e:
                logger.warning(f"SQL 주석 처리 실패: {e}")
                indent = self._get_indent(block.text)
                sql_id = f"sql_{sql_counter}"
                comment = self.config.SQL_COMMENT_FORMAT.format(
                    sql_id=sql_id, sql_type="UNKNOWN", desc="설명 없음"
                )
                result_code = self._find_and_replace(
                    result_code, block.text, indent + comment
                )
                sql_counter += 1
        
        return result_code
    
    def map_sql_to_functions(
        self, file_key: str, funcs: List[Dict]
    ) -> Dict[str, Optional[str]]:
        """각 SQL이 어느 함수에서 사용되는지 매핑"""
        sql_to_function_map = {}
        output_path = self._get_output_path()
        
        # 함수 파일들 스캔
        for func in funcs:
            func_name = func.get("function_name") or func.get("name")
            if not func_name:
                continue
                
            func_file_path = os.path.join(
                output_path, file_key, "func", f"func_{func_name}.c"
            )
            
            if not os.path.exists(func_file_path):
                continue
            
            try:
                with open(func_file_path, "r", encoding="utf-8") as f:
                    func_code = f.read()
                
                sql_call_pattern = r'sql_call\("(sql_\d+)",\s*"[^"]+"\);'
                for sql_id in re.findall(sql_call_pattern, func_code):
                    sql_to_function_map[sql_id] = func_name
                    
            except Exception as e:
                logger.warning(f"함수 파일 읽기 실패: {func_file_path}: {e}")
        
        # 클래스 파일 스캔
        class_file_path = os.path.join(output_path, file_key, f"{file_key}.c")
        
        if os.path.exists(class_file_path):
            try:
                with open(class_file_path, "r", encoding="utf-8") as f:
                    class_code = f.read()
                
                sql_call_pattern = r'sql_call\("(sql_\d+)",\s*"[^"]+"\);'
                for sql_id in re.findall(sql_call_pattern, class_code):
                    if sql_id not in sql_to_function_map:
                        sql_to_function_map[sql_id] = None
                        
            except Exception as e:
                logger.warning(f"클래스 파일 읽기 실패: {class_file_path}: {e}")
        
        return sql_to_function_map
    
    def _generate_sql_name(self, sql_type: str, name_count: Dict) -> str:
        """SQL 이름 생성"""
        if sql_type in name_count:
            name = f"{sql_type}_{name_count[sql_type]}"
            name_count[sql_type] += 1
            return name
        elif sql_type == "declare_cursor":
            name = f"select_{name_count.get('select', 0)}"
            name_count['select'] = name_count.get('select', 0) + 1
            return name
        else:
            return f"sql_{sum(name_count.values())}"
    
    def _get_indent(self, text: str) -> str:
        """텍스트에서 들여쓰기 추출"""
        match = re.match(r"^[\s]*", text)
        return match.group(0) if match else ""
    
    def _get_output_path(self) -> str:
        """출력 경로 반환"""
        if self.file_manager and hasattr(self.file_manager, 'output_path'):
            return self.file_manager.output_path
        return getattr(self.config, 'OUTPUT_PATH', './output')
    
    def _find_and_replace(self, text: str, old: str, new: str) -> str:
        """문자열 찾아 바꾸기"""
        if self.code_analyzer and hasattr(self.code_analyzer, 'find_and_replace'):
            return self.code_analyzer.find_and_replace(text, old, new)
        return text.replace(old, new, 1)
    
    def _save_sql_calls(self, sql_data: List[Dict], file_key: str):
        """SQL 호출 정보 저장"""
        output_path = self._get_output_path()
        sql_yaml_path = os.path.join(output_path, file_key, "sql", "sql_calls.yaml")
        
        os.makedirs(os.path.dirname(sql_yaml_path), exist_ok=True)
        
        try:
            import yaml
            
            class LiteralStr(str):
                pass
            
            def literal_representer(dumper, data):
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            
            yaml.add_representer(LiteralStr, literal_representer)
            
            for item in sql_data:
                if 'sql' in item and item['sql']:
                    item['sql'] = LiteralStr(item['sql'])
            
            with open(sql_yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(sql_data, f, allow_unicode=True, default_flow_style=False)
                
        except ImportError:
            import json
            with open(sql_yaml_path.replace('.yaml', '.json'), 'w', encoding='utf-8') as f:
                json.dump(sql_data, f, ensure_ascii=False, indent=2)
    
    # =========================================================================
    # MyBatis 변환 관련 메서드
    # =========================================================================
    
    def get_mybatis_converter(
        self,
        input_formatter: Callable[[str], str] = None,
        output_formatter: Callable[[str], str] = None
    ) -> MyBatisConverter:
        """MyBatis 변환기 반환 (지연 초기화)"""
        if self._mybatis_converter is None or input_formatter or output_formatter:
            self._mybatis_converter = MyBatisConverter(
                input_formatter=input_formatter,
                output_formatter=output_formatter
            )
        return self._mybatis_converter
    
    def get_id_generator(self) -> SQLIdGenerator:
        """SQL ID 생성기 반환 (지연 초기화)"""
        if self._id_generator is None:
            self._id_generator = SQLIdGenerator()
        return self._id_generator
    
    def get_comment_marker(
        self,
        formatter: Callable = None,
        template: str = None
    ) -> SQLCommentMarker:
        """주석 마커 반환 (지연 초기화)"""
        if self._comment_marker is None or formatter or template:
            if template:
                self._comment_marker = SQLCommentMarker(format_template=template)
            elif formatter:
                self._comment_marker = SQLCommentMarker(formatter=formatter)
            else:
                self._comment_marker = SQLCommentMarker()
        return self._comment_marker
    
    def get_cursor_merger(self) -> CursorMerger:
        """커서 병합기 반환 (지연 초기화)"""
        if self._cursor_merger is None:
            self._cursor_merger = CursorMerger()
        return self._cursor_merger
    
    def get_dynamic_sql_extractor(self) -> DynamicSQLExtractor:
        """동적 SQL 추출기 반환 (지연 초기화)"""
        if self._dynamic_sql_extractor is None:
            self._dynamic_sql_extractor = DynamicSQLExtractor()
        return self._dynamic_sql_extractor
    
    def extract_with_mybatis_conversion(
        self,
        code: str,
        file_key: str,
        input_formatter: Callable[[str], str] = None,
        output_formatter: Callable[[str], str] = None,
        comment_template: str = None
    ) -> Tuple[str, List[MyBatisSQL]]:
        """
        SQL을 추출하고 MyBatis 형식으로 변환
        
        Args:
            code: 소스 코드
            file_key: 파일 키
            input_formatter: 입력 변수 포맷터 (기본: #{varName})
            output_formatter: 출력 변수 포맷터 (기본: varName)
            comment_template: 주석 템플릿 (기본: /* sql extracted: {sql_id} */)
        
        Returns:
            (주석이 삽입된 코드, MyBatisSQL 목록) 튜플
        """
        # 컴포넌트 초기화
        converter = self.get_mybatis_converter(input_formatter, output_formatter)
        id_gen = self.get_id_generator()
        id_gen.reset()  # 파일별로 ID 리셋
        
        marker = self.get_comment_marker(template=comment_template)
        cursor_merger = self.get_cursor_merger()
        
        result_code = code
        mybatis_sqls = []
        
        # SQL 블록 추출
        if self.use_tree_sitter:
            sql_blocks = self._extract_with_tree_sitter(code)
        else:
            sql_blocks = self._extract_with_regex(code)
        
        # 커서 그룹 찾기
        block_dicts = [{
            'sql': b.text,
            'text': b.text,
            'sql_type': self.sql_type_registry.determine_type(b.text).value,
            'line_start': b.start_line,
            'line_end': b.end_line,
            'function_name': b.containing_function,
        } for b in sql_blocks]
        
        cursor_groups = cursor_merger.find_cursor_groups(block_dicts)
        merged_cursor_names = set()
        for group in cursor_groups:
            merged_cursor_names.add(group.cursor_name)
        
        for block in sql_blocks:
            # SQL 타입 결정
            result = self.sql_type_registry.determine_type(block.text)
            sql_type = result.value
            
            # INCLUDE, DECLARE_SECTION 등은 스킵
            if sql_type in ["include", "declare_section_begin", "declare_section_end"]:
                result_code = self._find_and_replace(result_code, block.text, "")
                continue
            
            # 커서 관련 문은 병합 처리 (OPEN/FETCH/CLOSE는 스킵)
            if sql_type in ["open", "close", "fetch_into"]:
                # 커서 이름이 병합 대상인지 확인
                is_merged = any(name.upper() in block.text.upper() for name in merged_cursor_names)
                if is_merged:
                    # 주석만 남기고 제거
                    comment = marker.mark("cursor_op", sql_type, function_name=block.containing_function)
                    indent = self._get_indent(block.text)
                    result_code = self._find_and_replace(result_code, block.text, indent + comment + "\n")
                    continue
            
            # ID 생성
            sql_id = id_gen.generate_id(sql_type)
            
            # 호스트 변수 추출
            input_vars, output_vars = self.host_var_registry.classify_by_direction(
                block.text, sql_type
            )
            input_var_strs = [v.get('raw', '') for v in input_vars]
            output_var_strs = [v.get('raw', '') for v in output_vars]
            
            # DECLARE CURSOR는 커서 병합 결과 사용
            if sql_type == "declare_cursor":
                for group in cursor_groups:
                    if group.declare_sql.get('sql', '') == block.text or group.declare_sql.get('text', '') == block.text:
                        merged = cursor_merger.merge(group)
                        mybatis_sql = converter.convert_sql(
                            sql=merged.merged_sql,
                            sql_type=sql_type,
                            sql_id=sql_id,
                            input_vars=merged.input_vars,
                            output_vars=merged.output_vars
                        )
                        mybatis_sqls.append(mybatis_sql)
                        break
                else:
                    # 병합 대상 아닌 경우 일반 처리
                    mybatis_sql = converter.convert_sql(
                        sql=block.text,
                        sql_type=sql_type,
                        sql_id=sql_id,
                        input_vars=input_var_strs,
                        output_vars=output_var_strs
                    )
                    mybatis_sqls.append(mybatis_sql)
            else:
                # 일반 SQL 변환
                mybatis_sql = converter.convert_sql(
                    sql=block.text,
                    sql_type=sql_type,
                    sql_id=sql_id,
                    input_vars=input_var_strs,
                    output_vars=output_var_strs
                )
                mybatis_sqls.append(mybatis_sql)
            
            # 주석 삽입 및 원본 교체
            comment = marker.mark(
                sql_id, sql_type, 
                function_name=block.containing_function,
                line_start=block.start_line
            )
            indent = self._get_indent(block.text)
            replacement = indent + comment + "\n"
            result_code = self._find_and_replace(result_code, block.text, replacement)
        
        return result_code, mybatis_sqls
    
    def extract_dynamic_sql(
        self,
        variable_name: str,
        c_elements: List[Dict],
        before_line: int,
        function_name: Optional[str] = None
    ) -> Optional[DynamicSQL]:
        """동적 SQL 추출 (strncpy/sprintf 추적)"""
        extractor = self.get_dynamic_sql_extractor()
        return extractor.extract_dynamic_sql(
            variable_name, c_elements, before_line, function_name
        )
