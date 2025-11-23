from patterns import *
from c_parser import CParser
from sql_converter import SQLConverter
from plugins.bam_call import BamCallPlugin
import re

class ProCParser:
    def __init__(self):
        self.c_parser = CParser()
        self.sql_converter = SQLConverter()
        # Initialize plugins
        # In a real system, this could be dynamic loading
        self.plugins = [
            BamCallPlugin()
        ]

    def parse_file(self, file_path):
        """
        Main parsing method for a single file.
        """
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            
        elements = []
        
        # We need a version of content for C parsing where Pro*C constructs are blanked out
        # to avoid syntax errors in Tree-sitter
        c_parsing_content = list(content)
        
        # Track covered regions for unknown detection
        # List of boolean, True if covered
        covered_map = [False] * len(content)
        
        def mark_covered(start, end):
            for i in range(start, end):
                covered_map[i] = True
        
        def blank_out(start, end):
            for i in range(start, end):
                if c_parsing_content[i] != '\n':
                    c_parsing_content[i] = ' '
            mark_covered(start, end)

        # 1. Extract Pro*C specific elements (SQL, Macros, etc.) using Regex
        
        # Includes
        for match in PATTERN_INCLUDE.finditer(content):
            elements.append({
                "type": "include",
                "path": match.group(2),
                "is_system": match.group(1) == '<',
                "line_start": content.count('\n', 0, match.start()) + 1,
                "line_end": content.count('\n', 0, match.end()) + 1,
                "raw_content": match.group(0),
                "function": None # Usually global
            })
            mark_covered(match.start(), match.end())
            
        # Macros
        for match in PATTERN_MACRO.finditer(content):
            elements.append({
                "type": "macro",
                "name": match.group(1),
                "value": match.group(2),
                "line_start": content.count('\n', 0, match.start()) + 1,
                "line_end": content.count('\n', 0, match.end()) + 1,
                "raw_content": match.group(0),
                "function": None
            })
            mark_covered(match.start(), match.end())

        # SQL Blocks
        for match in PATTERN_SQL.finditer(content):
            raw_sql = match.group(0)
            normalized_data = self.sql_converter.normalize_sql(raw_sql)
            
            element = {
                "type": "sql",
                "line_start": content.count('\n', 0, match.start()) + 1,
                "line_end": content.count('\n', 0, match.end()) + 1,
                "raw_content": raw_sql,
                "function": None # Will be filled later by scope resolution
            }
            element.update(normalized_data)
            elements.append(element)
            
            # Blank out SQL for C parser
            blank_out(match.start(), match.end())

        # Plugins (e.g., BAMCALL)
        for plugin in self.plugins:
            for match in plugin.pattern.finditer(content):
                element = plugin.parse(match, content)
                elements.append(element)
                blank_out(match.start(), match.end())

        # Comments
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

        # 2. Extract C elements using Tree-sitter
        c_source = "".join(c_parsing_content)
        c_elements = self.c_parser.parse(c_source)
        
        # Mark C elements as covered?
        # Tree-sitter elements might overlap or be nested.
        # We should map them back to original content indices if possible.
        # But tree-sitter gives row/col. We need to convert to index.
        # For simplicity, we might skip exact coverage marking for C elements 
        # OR we can calculate indices from line numbers.
        
        # Helper to convert line/col to index
        line_indices = [0]
        for i, char in enumerate(content):
            if char == '\n':
                line_indices.append(i + 1)
        
        def get_index(row, col):
            if row >= len(line_indices): return len(content)
            return line_indices[row] + col

        # 3. Merge and Resolve Scope
        # First, separate functions from other C elements
        functions = [e for e in c_elements if e['type'] == 'function']
        
        # Add all C elements to main list
        elements.extend(c_elements)
        
        # Mark coverage for C elements
        # Note: Tree-sitter ranges are 0-indexed for row
        # Our elements use 1-indexed line_start/end.
        # We need the raw node info or re-calculate.
        # Since we don't have raw node here easily, we might need to rely on line numbers?
        # Or we can just accept that C elements are "covered" by virtue of being parsed.
        # BUT, unknown detection needs to know what is NOT covered.
        # So we should mark them.
        
        # Let's assume C parser covers the lines it reports.
        for el in c_elements:
            # This is rough coverage (whole lines). 
            # Ideally we want exact byte ranges.
            # For now, let's skip marking C elements for "unknown" detection 
            # because C parser covers "valid C code".
            # Anything not covered by Regex OR C Parser is unknown.
            # But we need to know WHERE C elements are.
            
            # If we can't easily get byte range, we can approximate.
            # Or we can update CParser to return byte ranges.
            pass

        # Sort by start line
        elements.sort(key=lambda x: x['line_start'])
        
        # Resolve Scope
        for el in elements:
            if el['type'] == 'function': continue 
            if el.get('function'): continue 
            
            for func in functions:
                if func['line_start'] <= el['line_start'] and func['line_end'] >= el['line_end']:
                    el['function'] = func['name']
                    break
        
        # 4. Unknown Element Detection
        # We need to mark C elements as covered.
        # Since we don't have byte ranges from CParser yet, let's update CParser later or approximate.
        # Approximation: Mark lines covered by C elements as covered.
        for el in c_elements:
            start_line = el['line_start'] - 1
            end_line = el['line_end'] - 1
            
            start_idx = line_indices[start_line] if start_line < len(line_indices) else len(content)
            # End index is tricky without col.
            # Let's assume full lines for simplicity or improve CParser.
            # Improving CParser is better.
            
            # For now, let's just mark the whole lines as covered.
            if start_line < len(line_indices):
                s = line_indices[start_line]
                e = line_indices[end_line+1] if end_line+1 < len(line_indices) else len(content)
                mark_covered(s, e)

        # Find uncovered regions
        unknowns = []
        current_start = -1
        
        for i in range(len(content)):
            if not covered_map[i]:
                char = content[i]
                if not char.isspace(): # Ignore whitespace
                    if current_start == -1:
                        current_start = i
                else:
                    # Whitespace. If we were tracking an unknown, keep tracking?
                    # No, whitespace breaks unknowns? Or whitespace is part of unknown?
                    # Usually whitespace is part of unknown block.
                    pass
            else:
                if current_start != -1:
                    # End of unknown block
                    # Check if it's just whitespace/semicolons
                    raw = content[current_start:i]
                    if raw.strip() and raw.strip() != ';':
                        unknowns.append({
                            "type": "unknown",
                            "line_start": content.count('\n', 0, current_start) + 1,
                            "line_end": content.count('\n', 0, i) + 1,
                            "raw_content": raw,
                            "function": None # Scope resolution for unknowns?
                        })
                    current_start = -1
        
        # Check trailing unknown
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

        # Resolve scope for unknowns
        for el in unknowns:
             for func in functions:
                if func['line_start'] <= el['line_start'] and func['line_end'] >= el['line_end']:
                    el['function'] = func['name']
                    break
        
        elements.extend(unknowns)
        elements.sort(key=lambda x: x['line_start'])
        
        return elements

