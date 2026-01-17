"""
Docstring Enricher 플러그인 모듈입니다.
함수 정의 위의 주석을 docstring으로 추출하고 raw_content에 포함시킵니다.
"""
from typing import Dict, List
from ..interfaces import ElementEnricherPlugin
import re


class DocstringEnricherPlugin(ElementEnricherPlugin):
    """
    함수 정의 위의 주석을 docstring으로 추출하여 함수 요소를 보강합니다.
    
    이 플러그인은:
    - 함수 시작 라인 바로 위에 있는 연속된 주석들을 찾습니다
    - 블록 주석(/* */)과 라인 주석(//)을 모두 지원합니다
    - docstring 필드를 추가하고 raw_content에 docstring을 포함시킵니다
    """
    
    # 주석과 함수 사이의 최대 허용 간격 (줄 수)
    MAX_GAP = 2
    
    # 주석 패턴
    PATTERN_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)
    PATTERN_LINE_COMMENT = re.compile(r'//[^\n]*')
    
    def can_handle(self, element: Dict) -> bool:
        """함수 타입의 요소만 처리합니다."""
        return element.get('type') == 'function'
    
    def enrich(self, element: Dict, all_elements: List[Dict], content: str) -> Dict:
        """
        함수 요소에 docstring을 추가하고 raw_content를 업데이트합니다.
        
        Args:
            element: 함수 요소 딕셔너리
            all_elements: 모든 추출된 요소 목록
            content: 원본 파일 내용
            
        Returns:
            docstring이 추가된 함수 요소
        """
        func_start_line = element.get('line_start', 0)
        
        # 파일 내용에서 주석 정보 수집
        comments = self._collect_comments(content)
        
        # 함수 위의 docstring 추출
        docstring = self._get_preceding_docstring(func_start_line, comments)
        
        # 요소 업데이트
        element['docstring'] = docstring
        
        # raw_content에 docstring 포함
        if docstring:
            original_raw_content = element.get('raw_content', '')
            element['raw_content'] = docstring + '\n' + original_raw_content
        
        return element
    
    def _collect_comments(self, content: str) -> List[Dict]:
        """
        파일 내용에서 모든 주석을 수집합니다.
        
        Args:
            content: 파일 전체 내용
            
        Returns:
            주석 정보 리스트 [{'start_line': int, 'end_line': int, 'text': str}, ...]
        """
        comments = []
        
        # 블록 주석 수집
        for match in self.PATTERN_BLOCK_COMMENT.finditer(content):
            start_line = content.count('\n', 0, match.start()) + 1
            end_line = content.count('\n', 0, match.end()) + 1
            comments.append({
                'start_line': start_line,
                'end_line': end_line,
                'text': match.group(0)
            })
        
        # 라인 주석 수집
        for match in self.PATTERN_LINE_COMMENT.finditer(content):
            line_num = content.count('\n', 0, match.start()) + 1
            comments.append({
                'start_line': line_num,
                'end_line': line_num,
                'text': match.group(0)
            })
        
        return comments
    
    def _get_preceding_docstring(self, func_start_line: int, comments: List[Dict]) -> str:
        """
        함수 정의 바로 위에 있는 연속된 주석들을 docstring으로 추출합니다.
        
        Args:
            func_start_line: 함수 정의가 시작하는 라인 번호
            comments: 수집된 주석 정보 리스트
            
        Returns:
            연속된 주석들을 합친 docstring, 없으면 None
        """
        if not comments:
            return None
        
        preceding_comments = []
        expected_end_line = func_start_line
        
        # 주석을 end_line 기준으로 역순 정렬하여 함수 위에서부터 탐색
        sorted_comments = sorted(comments, key=lambda c: c['end_line'], reverse=True)
        
        for comment in sorted_comments:
            # 주석의 끝 라인이 함수 시작 라인보다 이전이어야 함
            if comment['end_line'] >= func_start_line:
                continue
            
            # 주석과 다음 요소(함수 또는 이전 주석) 사이의 간격 체크
            gap = expected_end_line - comment['end_line']
            if gap <= self.MAX_GAP:
                preceding_comments.append(comment)
                expected_end_line = comment['start_line']
            else:
                break
        
        if not preceding_comments:
            return None
        
        # 순서를 원래대로 복원 (위에서 아래로)
        preceding_comments.reverse()
        
        # 주석들을 줄바꿈으로 연결
        docstring_parts = [c['text'] for c in preceding_comments]
        return '\n'.join(docstring_parts)
