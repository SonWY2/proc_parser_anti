"""
BAMCALL 구문을 파싱하는 플러그인입니다.
BAMCALL(args) 형태의 호출을 감지하고 인자를 추출합니다.
"""
import re
from plugin_interface import ParserPlugin

class BamCallPlugin(ParserPlugin):
    def __init__(self):
        # 캡처: BAMCALL(...) 내부의 인자
        # 여러 줄에 걸쳐 매칭하기 위해 DOTALL 사용
        self._pattern = re.compile(r'BAMCALL\s*\((.*?)\);', re.DOTALL)

    @property
    def pattern(self):
        return self._pattern

    @property
    def element_type(self):
        return "bam_call"

    def parse(self, match, content):
        line_start, line_end = self.get_line_range(match, content)
        args = match.group(1).strip()
        
        return {
            "type": self.element_type,
            "args": args,
            "line_start": line_start,
            "line_end": line_end,
            "raw_content": match.group(0),
            "function": None # 코어 파서에 의해 해결됨
        }
