"""
Java 코드 파싱 유틸리티

LLM 응답에서 메소드, import 구문 등을 추출하는 파서.
"""

import re
from typing import List, Optional, Tuple

from .types import ExtractedMethod


class JavaParser:
    """Java 코드 파싱 유틸리티 클래스."""
    
    # import 구문 패턴 (static import 포함)
    IMPORT_PATTERN = re.compile(
        r'^\s*import\s+(static\s+)?([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*(?:\.\*)?)\s*;',
        re.MULTILINE
    )
    
    # package 선언 패턴
    PACKAGE_PATTERN = re.compile(
        r'^\s*package\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*;',
        re.MULTILINE
    )
    
    # 메소드 시그니처 시작 패턴
    # 접근제한자, static, final, synchronized 등 modifier + 반환타입 + 메소드명 + (
    METHOD_MODIFIERS = r'(?:public|private|protected|static|final|synchronized|native|abstract|strictfp|\s)*'
    RETURN_TYPE = r'(?:void|[a-zA-Z_][a-zA-Z0-9_<>\[\], ]*)'
    
    # class 선언 패턴
    CLASS_PATTERN = re.compile(
        r'(?:public|private|protected|static|final|abstract|\s)*\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        re.MULTILINE
    )
    
    def extract_imports(self, code: str) -> List[str]:
        """코드에서 모든 import 구문 추출.
        
        Args:
            code: Java 소스 코드
            
        Returns:
            import 구문 리스트 (전체 구문 포함, 예: "import java.util.List;")
        """
        imports = []
        for match in self.IMPORT_PATTERN.finditer(code):
            # 전체 매칭 문자열에서 앞뒤 공백 제거
            import_stmt = match.group(0).strip()
            imports.append(import_stmt)
        return imports
    
    def extract_package_declaration(self, code: str) -> Optional[str]:
        """package 선언 추출.
        
        Args:
            code: Java 소스 코드
            
        Returns:
            package 선언 문자열 또는 None
        """
        match = self.PACKAGE_PATTERN.search(code)
        if match:
            return match.group(0).strip()
        return None
    
    def extract_method_by_name(self, code: str, method_name: str) -> Optional[ExtractedMethod]:
        """지정된 이름의 메소드 블럭 추출.
        
        중괄호 깊이 추적을 통해 메소드의 시작과 끝을 찾음.
        문자열 리터럴과 주석 내의 중괄호는 무시.
        
        Args:
            code: Java 소스 코드
            method_name: 추출할 메소드 이름
            
        Returns:
            ExtractedMethod 객체 또는 None
        """
        # 메소드 시그니처 찾기
        # 패턴: (modifiers) (return_type) method_name (
        method_pattern = re.compile(
            rf'({self.METHOD_MODIFIERS})\s*({self.RETURN_TYPE})\s+({re.escape(method_name)})\s*\(',
            re.MULTILINE
        )
        
        match = method_pattern.search(code)
        if not match:
            return None
        
        # 메소드 시작 위치 (시그니처 시작)
        method_start = match.start()
        
        # 시그니처 추출 (괄호 닫힘까지)
        signature_end = self._find_matching_paren(code, match.end() - 1)
        if signature_end == -1:
            return None
            
        signature = code[method_start:signature_end + 1].strip()
        
        # 시그니처 이후 { 찾기 (throws 절 고려)
        brace_start = code.find('{', signature_end)
        if brace_start == -1:
            return None
        
        # 메소드 본문 끝 찾기 (중괄호 매칭)
        brace_end = self._find_matching_brace(code, brace_start)
        if brace_end == -1:
            return None
        
        # 전체 메소드 코드
        method_body = code[method_start:brace_end + 1]
        
        # 라인 번호 계산
        start_line = code[:method_start].count('\n') + 1
        end_line = code[:brace_end + 1].count('\n') + 1
        
        return ExtractedMethod(
            name=method_name,
            signature=signature,
            body=method_body,
            start_line=start_line,
            end_line=end_line
        )
    
    def extract_class_body_insertion_point(self, skeleton: str) -> int:
        """클래스 본문에 메소드를 삽입할 위치 반환.
        
        클래스의 마지막 닫는 중괄호 바로 앞에 삽입할 위치를 찾음.
        
        Args:
            skeleton: 클래스 스켈레톤 코드
            
        Returns:
            삽입 위치 인덱스 (-1 if not found)
        """
        # class 선언 찾기
        class_match = self.CLASS_PATTERN.search(skeleton)
        if not class_match:
            return -1
        
        # class 시작 { 찾기
        brace_start = skeleton.find('{', class_match.end())
        if brace_start == -1:
            return -1
        
        # 대응하는 } 찾기
        brace_end = self._find_matching_brace(skeleton, brace_start)
        if brace_end == -1:
            return -1
        
        # } 바로 앞이 삽입 위치
        return brace_end
    
    def _find_matching_paren(self, code: str, start: int) -> int:
        """괄호 () 매칭 위치 찾기.
        
        Args:
            code: 소스 코드
            start: 시작 '(' 위치
            
        Returns:
            대응하는 ')' 위치 또는 -1
        """
        if start >= len(code) or code[start] != '(':
            return -1
        
        depth = 1
        i = start + 1
        in_string = False
        string_char = None
        in_comment = False
        in_line_comment = False
        
        while i < len(code) and depth > 0:
            char = code[i]
            prev_char = code[i - 1] if i > 0 else ''
            next_char = code[i + 1] if i + 1 < len(code) else ''
            
            # 라인 주석 처리
            if in_line_comment:
                if char == '\n':
                    in_line_comment = False
                i += 1
                continue
            
            # 블록 주석 처리
            if in_comment:
                if char == '*' and next_char == '/':
                    in_comment = False
                    i += 2
                    continue
                i += 1
                continue
            
            # 주석 시작
            if char == '/' and next_char == '/':
                in_line_comment = True
                i += 2
                continue
            if char == '/' and next_char == '*':
                in_comment = True
                i += 2
                continue
            
            # 문자열 처리
            if in_string:
                if char == string_char and prev_char != '\\':
                    in_string = False
                i += 1
                continue
            
            if char in '"\'':
                in_string = True
                string_char = char
                i += 1
                continue
            
            # 괄호 카운팅
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            
            i += 1
        
        return i - 1 if depth == 0 else -1
    
    def _find_matching_brace(self, code: str, start: int) -> int:
        """중괄호 {} 매칭 위치 찾기.
        
        문자열, 주석 내의 중괄호는 무시.
        
        Args:
            code: 소스 코드
            start: 시작 '{' 위치
            
        Returns:
            대응하는 '}' 위치 또는 -1
        """
        if start >= len(code) or code[start] != '{':
            return -1
        
        depth = 1
        i = start + 1
        in_string = False
        string_char = None
        in_comment = False
        in_line_comment = False
        
        while i < len(code) and depth > 0:
            char = code[i]
            prev_char = code[i - 1] if i > 0 else ''
            next_char = code[i + 1] if i + 1 < len(code) else ''
            
            # 라인 주석 처리
            if in_line_comment:
                if char == '\n':
                    in_line_comment = False
                i += 1
                continue
            
            # 블록 주석 처리
            if in_comment:
                if char == '*' and next_char == '/':
                    in_comment = False
                    i += 2
                    continue
                i += 1
                continue
            
            # 주석 시작
            if char == '/' and next_char == '/':
                in_line_comment = True
                i += 2
                continue
            if char == '/' and next_char == '*':
                in_comment = True
                i += 2
                continue
            
            # 문자열 처리
            if in_string:
                if char == string_char and prev_char != '\\':
                    in_string = False
                i += 1
                continue
            
            if char in '"\'':
                in_string = True
                string_char = char
                i += 1
                continue
            
            # 중괄호 카운팅
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
            
            i += 1
        
        return i - 1 if depth == 0 else -1
    
    def deduplicate_imports(self, imports: List[str]) -> List[str]:
        """import 구문 중복 제거 및 정렬.
        
        Args:
            imports: import 구문 리스트
            
        Returns:
            중복 제거 및 정렬된 import 리스트
        """
        # 중복 제거
        unique = list(dict.fromkeys(imports))
        
        # 정렬: java.* -> javax.* -> 기타 (알파벳순)
        def sort_key(imp: str):
            # import 키워드 제거하고 정렬
            clean = imp.replace('import ', '').replace('static ', '').replace(';', '').strip()
            if clean.startswith('java.'):
                return (0, clean)
            elif clean.startswith('javax.'):
                return (1, clean)
            else:
                return (2, clean)
        
        return sorted(unique, key=sort_key)
