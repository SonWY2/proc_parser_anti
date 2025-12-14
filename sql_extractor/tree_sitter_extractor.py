"""
Tree-sitter 기반 SQL 추출기 모듈

tree-sitter-c를 사용하여 Pro*C 코드에서 EXEC SQL 블록을 추출합니다.
tree-sitter-c는 EXEC SQL을 ERROR 노드로 파싱하므로 이를 활용합니다.
"""

import logging
from typing import List, Optional
from dataclasses import dataclass

try:
    import tree_sitter
    import tree_sitter_c
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

logger = logging.getLogger(__name__)


@dataclass
class SQLBlock:
    """추출된 SQL 블록
    
    Attributes:
        text: SQL 구문 전체 텍스트
        start_byte: 시작 바이트 오프셋
        end_byte: 종료 바이트 오프셋
        start_line: 시작 라인 (1-indexed)
        end_line: 종료 라인 (1-indexed)
        containing_function: 포함된 함수명 (없으면 None)
    """
    text: str
    start_byte: int
    end_byte: int
    start_line: int
    end_line: int
    containing_function: Optional[str] = None


class TreeSitterSQLExtractor:
    """Tree-sitter 기반 SQL 추출기
    
    tree-sitter-c로 C 코드를 파싱하고,
    ERROR 노드에서 EXEC SQL 블록을 추출합니다.
    
    EXEC SQL은 표준 C 문법이 아니므로 tree-sitter-c가
    이를 ERROR 노드로 파싱합니다. 이 특성을 활용합니다.
    
    Example:
        extractor = TreeSitterSQLExtractor()
        blocks = extractor.extract_sql_blocks(source_code)
        
        for block in blocks:
            print(f"Line {block.start_line}: {block.text[:50]}...")
    """
    
    def __init__(self):
        """Tree-sitter 파서 초기화"""
        if not HAS_TREE_SITTER:
            raise ImportError(
                "tree-sitter and tree-sitter-c are required. "
                "Install with: pip install tree-sitter tree-sitter-c"
            )
        
        self.language = tree_sitter.Language(tree_sitter_c.language())
        self.parser = tree_sitter.Parser(self.language)
        logger.info("TreeSitterSQLExtractor initialized")
    
    def extract_sql_blocks(
        self, 
        source_code: str,
        functions: List[dict] = None
    ) -> List[SQLBlock]:
        """소스 코드에서 모든 EXEC SQL 블록 추출
        
        tree-sitter ERROR 노드 방식을 먼저 시도하고,
        결과가 없으면 정규식 기반 추출로 fallback합니다.
        
        Args:
            source_code: Pro*C 소스 코드
            functions: 함수 목록 (스코프 결정용)
                       각 함수는 {'name': str, 'line_start': int, 'line_end': int} 형태
        
        Returns:
            SQLBlock 목록
        """
        source_bytes = source_code.encode('utf8')
        tree = self.parser.parse(source_bytes)
        
        # 1차: ERROR 노드에서 EXEC SQL 찾기
        exec_sql_nodes = self._find_exec_sql_nodes(tree.root_node)
        logger.debug(f"Found {len(exec_sql_nodes)} EXEC SQL nodes via tree-sitter")
        
        sql_blocks = []
        
        if exec_sql_nodes:
            # tree-sitter 방식
            for node in exec_sql_nodes:
                try:
                    start, end = self._expand_sql_boundary(node, source_bytes)
                    text = source_bytes[start:end].decode('utf8')
                    
                    if not text.strip():
                        continue
                    
                    func_name = None
                    if functions:
                        func_name = self._determine_containing_function(node, functions)
                    
                    sql_blocks.append(SQLBlock(
                        text=text,
                        start_byte=start,
                        end_byte=end,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                        containing_function=func_name
                    ))
                except Exception as e:
                    logger.warning(f"Failed to extract SQL block: {e}")
                    continue
        
        # 2차: 정규식 fallback (tree-sitter가 결과 없을 때)
        if not sql_blocks:
            logger.debug("No SQL blocks from tree-sitter, using regex fallback")
            sql_blocks = self._extract_sql_blocks_regex(source_code, functions)
        
        return sql_blocks
    
    def _extract_sql_blocks_regex(
        self, 
        source_code: str, 
        functions: List[dict] = None
    ) -> List[SQLBlock]:
        """정규식 기반 SQL 블록 추출 (fallback)
        
        EXEC SQL ... ; 패턴을 찾아 SQL 블록을 추출합니다.
        """
        import re
        
        blocks = []
        
        # EXEC SQL ... ; 패턴 (여러 줄 가능)
        pattern = re.compile(
            r'(EXEC\s+SQL\s+[\s\S]*?;)',
            re.IGNORECASE | re.MULTILINE
        )
        
        for match in pattern.finditer(source_code):
            text = match.group(1)
            start_byte = match.start()
            end_byte = match.end()
            
            # 라인 번호 계산
            start_line = source_code[:start_byte].count('\n') + 1
            end_line = source_code[:end_byte].count('\n') + 1
            
            # 함수 스코프 결정
            func_name = None
            if functions:
                func_name = self._determine_containing_function_by_line(
                    start_line, functions
                )
            
            blocks.append(SQLBlock(
                text=text,
                start_byte=start_byte,
                end_byte=end_byte,
                start_line=start_line,
                end_line=end_line,
                containing_function=func_name
            ))
        
        logger.debug(f"Found {len(blocks)} SQL blocks via regex")
        return blocks
    
    def _determine_containing_function_by_line(
        self, 
        line_num: int, 
        functions: List[dict]
    ) -> Optional[str]:
        """라인 번호로 포함 함수 결정"""
        for func in functions:
            line_start = func.get('line_start', 0)
            line_end = func.get('line_end', 0)
            
            if line_start <= line_num <= line_end:
                return func.get('name') or func.get('function_name')
        
        return None

    
    def _find_exec_sql_nodes(self, node) -> List:
        """ERROR 노드 중 EXEC SQL 패턴을 찾음
        
        tree-sitter-c는 EXEC SQL 구문을 인식하지 못하고
        ERROR 노드로 파싱합니다. 이 ERROR 노드 중
        EXEC SQL로 시작하는 것을 찾습니다.
        
        Args:
            node: tree-sitter 노드
        
        Returns:
            EXEC SQL이 포함된 ERROR 노드 목록
        """
        results = []
        
        if node.type == 'ERROR':
            try:
                text = node.text.decode('utf8').strip()
                # EXEC SQL 또는 EXEC  SQL (공백 여러 개) 패턴 확인
                if text.upper().startswith('EXEC') and 'SQL' in text.upper():
                    results.append(node)
            except Exception:
                pass
        
        # 자식 노드 재귀 탐색
        for child in node.children:
            results.extend(self._find_exec_sql_nodes(child))
        
        return results
    
    def _expand_sql_boundary(
        self, 
        node, 
        source_bytes: bytes
    ) -> tuple[int, int]:
        """세미콜론까지 SQL 경계 확장
        
        ERROR 노드가 SQL 전체를 포함하지 않을 수 있으므로
        세미콜론까지 경계를 확장합니다.
        
        Args:
            node: tree-sitter 노드
            source_bytes: 소스 코드 바이트
        
        Returns:
            (start_byte, end_byte) 튜플
        """
        start = node.start_byte
        end = node.end_byte
        
        # 이미 세미콜론으로 끝나면 그대로 반환
        if end > 0 and source_bytes[end-1:end] == b';':
            return start, end
        
        # 세미콜론 찾기
        while end < len(source_bytes):
            char = source_bytes[end:end+1]
            if char == b';':
                end += 1
                break
            end += 1
        
        return start, end
    
    def _determine_containing_function(
        self, 
        sql_node, 
        functions: List[dict]
    ) -> Optional[str]:
        """SQL 노드가 속한 함수 찾기
        
        Args:
            sql_node: tree-sitter 노드
            functions: 함수 목록
        
        Returns:
            함수명 또는 None
        """
        sql_line = sql_node.start_point.row + 1
        
        for func in functions:
            line_start = func.get('line_start', 0)
            line_end = func.get('line_end', 0)
            
            if line_start <= sql_line <= line_end:
                return func.get('name') or func.get('function_name')
        
        return None
    
    def parse_tree(self, source_code: str):
        """소스 코드의 AST 반환 (디버깅용)
        
        Args:
            source_code: 소스 코드
        
        Returns:
            tree-sitter Tree 객체
        """
        source_bytes = source_code.encode('utf8')
        return self.parser.parse(source_bytes)
    
    def get_functions(self, source_code: str) -> List[dict]:
        """소스 코드에서 함수 목록 추출
        
        별도의 CParser를 사용하지 않고 tree-sitter로 직접 추출합니다.
        
        Args:
            source_code: 소스 코드
        
        Returns:
            함수 정보 목록
        """
        source_bytes = source_code.encode('utf8')
        tree = self.parser.parse(source_bytes)
        
        functions = []
        self._find_functions(tree.root_node, functions, source_bytes)
        
        return functions
    
    def _find_functions(
        self, 
        node, 
        functions: List[dict],
        source_bytes: bytes
    ):
        """함수 정의 노드 찾기"""
        if node.type == 'function_definition':
            func_name = self._get_function_name(node)
            if func_name:
                functions.append({
                    'name': func_name,
                    'line_start': node.start_point.row + 1,
                    'line_end': node.end_point.row + 1,
                })
        
        for child in node.children:
            self._find_functions(child, functions, source_bytes)
    
    def _get_function_name(self, node) -> Optional[str]:
        """함수 이름 추출"""
        declarator = node.child_by_field_name('declarator')
        if not declarator:
            return None
        
        # pointer_declarator 처리
        while declarator.type == 'pointer_declarator':
            declarator = declarator.child_by_field_name('declarator')
            if not declarator:
                return None
        
        if declarator.type == 'function_declarator':
            identifier = declarator.child_by_field_name('declarator')
            if identifier and identifier.type == 'identifier':
                return identifier.text.decode('utf8')
        
        return None


def get_tree_sitter_extractor() -> Optional[TreeSitterSQLExtractor]:
    """Tree-sitter SQL 추출기 인스턴스 반환
    
    tree-sitter가 없으면 None을 반환합니다.
    
    Returns:
        TreeSitterSQLExtractor 또는 None
    """
    if not HAS_TREE_SITTER:
        logger.warning("tree-sitter not available")
        return None
    
    try:
        return TreeSitterSQLExtractor()
    except Exception as e:
        logger.error(f"Failed to create TreeSitterSQLExtractor: {e}")
        return None
