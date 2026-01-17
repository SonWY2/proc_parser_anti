"""
중복 main 함수 제거 플러그인

병합된 전체 코드에서 Main 또는 _main을 포함하는 메소드가 2개 이상이면 마지막만 유지.
스켈레톤에 있는 main 메소드도 포함하여 검사.
"""

import re
from typing import List, Tuple

from . import register_plugin
from .base import MergePlugin, PluginPhase, PluginTarget


@register_plugin
class MainDeduplicatorPlugin(MergePlugin):
    """중복 main 함수 제거 플러그인.
    
    병합된 전체 코드에서 Main 또는 _main 텍스트를 포함하는 메소드가 2개 이상 존재할 경우,
    마지막 main 함수만 남기고 나머지를 삭제.
    
    스켈레톤에 있는 main 메소드도 검사 대상에 포함됨.
    """
    
    name = "main_deduplicator"
    priority = 200  # 코드 조립 후 실행 (process_code 단계)
    description = "중복 main 함수 제거 (마지막만 유지)"
    phase = PluginPhase.POST_MERGE
    target = PluginTarget.CODE
    
    # main 함수 시그니처 패턴 (Main 또는 _main 포함)
    # 메소드 시그니처: (modifiers) (return_type) methodName(
    METHOD_PATTERN = re.compile(
        r'(?:(?:public|private|protected|static|final|synchronized|native|abstract|strictfp)\s+)*'
        r'(?:void|[a-zA-Z_][a-zA-Z0-9_<>\[\], ]*)\s+'
        r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
        re.MULTILINE
    )
    
    # main 함수 이름 패턴
    MAIN_NAME_PATTERN = re.compile(r'(Main|_main)', re.IGNORECASE)
    
    def is_main_method_name(self, method_name: str) -> bool:
        """메소드 이름이 main 함수인지 확인."""
        return bool(self.MAIN_NAME_PATTERN.search(method_name))
    
    def find_all_methods(self, code: str) -> List[Tuple[str, int, int]]:
        """코드에서 모든 메소드를 찾아 (이름, 시작위치, 끝위치) 반환.
        
        Returns:
            [(method_name, start_index, end_index), ...]
        """
        methods = []
        
        for match in self.METHOD_PATTERN.finditer(code):
            method_name = match.group(1)
            sig_start = match.start()
            
            # 메소드 본문 끝 찾기 (중괄호 매칭)
            brace_start = code.find('{', match.end())
            if brace_start == -1:
                continue
            
            brace_end = self._find_matching_brace(code, brace_start)
            if brace_end == -1:
                continue
            
            # 어노테이션 포함하여 시작 위치 조정
            actual_start = self._find_method_start_with_annotations(code, sig_start)
            
            methods.append((method_name, actual_start, brace_end + 1))
        
        return methods
    
    def _find_method_start_with_annotations(self, code: str, sig_start: int) -> int:
        """시그니처 앞의 어노테이션까지 포함한 시작 위치 반환."""
        # sig_start 앞으로 거슬러 올라가며 어노테이션 찾기
        pos = sig_start - 1
        while pos >= 0 and code[pos] in ' \t\n\r':
            pos -= 1
        
        # 어노테이션 패턴 검사 (@ 시작)
        while pos >= 0:
            line_start = code.rfind('\n', 0, pos + 1) + 1
            line = code[line_start:pos + 1].strip()
            
            if line.startswith('@'):
                pos = line_start - 1
                while pos >= 0 and code[pos] in ' \t\n\r':
                    pos -= 1
            else:
                break
        
        # 다음 줄의 시작으로 조정
        return code.find('\n', pos) + 1 if pos >= 0 else sig_start
    
    def _find_matching_brace(self, code: str, start: int) -> int:
        """중괄호 매칭 위치 찾기."""
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
            
            if in_line_comment:
                if char == '\n':
                    in_line_comment = False
                i += 1
                continue
            
            if in_comment:
                if char == '*' and next_char == '/':
                    in_comment = False
                    i += 2
                    continue
                i += 1
                continue
            
            if char == '/' and next_char == '/':
                in_line_comment = True
                i += 2
                continue
            if char == '/' and next_char == '*':
                in_comment = True
                i += 2
                continue
            
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
            
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
            
            i += 1
        
        return i - 1 if depth == 0 else -1
    
    def process_code(self, code: str) -> str:
        """병합된 코드에서 중복 main 함수 제거.
        
        Args:
            code: 병합된 전체 Java 코드
            
        Returns:
            중복 main이 제거된 코드
        """
        # 모든 메소드 찾기
        all_methods = self.find_all_methods(code)
        
        # main 메소드 필터링
        main_methods = [
            (name, start, end) 
            for name, start, end in all_methods 
            if self.is_main_method_name(name)
        ]
        
        # 2개 이상일 때만 처리
        if len(main_methods) <= 1:
            return code
        
        # 마지막 main을 제외한 나머지 삭제 (뒤에서부터 삭제해야 인덱스 안 깨짐)
        methods_to_remove = main_methods[:-1]
        methods_to_remove.sort(key=lambda x: x[1], reverse=True)
        
        result = code
        for name, start, end in methods_to_remove:
            # 메소드 앞뒤 공백/개행 정리
            while start > 0 and result[start - 1] in ' \t':
                start -= 1
            while end < len(result) and result[end] in ' \t\n\r':
                end += 1
            
            result = result[:start] + result[end:]
        
        return result
