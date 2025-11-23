import re
from plugin_interface import ParserPlugin

class BamCallPlugin(ParserPlugin):
    def __init__(self):
        # Captures: arguments inside BAMCALL(...)
        # Using DOTALL to match across lines
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
            "function": None # Will be resolved by core parser
        }
