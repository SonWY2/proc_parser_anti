import logging
import tree_sitter
try:
    import tree_sitter_c
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Set

logger = logging.getLogger(__name__)

@dataclass
class SqlCallInfo:
    node: any
    sql_id: str
    arg2: str
    start_byte: int
    end_byte: int
    scope_id: str  # Unique ID for the scope (e.g., node ID of the compound_statement)
    is_absorbed: bool = False  # Mark if this call is merged into a cursor block

class SqlCallExtractor:
    """
    Extracts `sql_call(arg1, arg2)` from C code and groups cursor operations.
    Replaces extracted regions with comments.
    """

    def __init__(self):
        if not HAS_TREE_SITTER:
             raise ImportError("tree-sitter and tree-sitter-c are required.")
        
        self.language = tree_sitter.Language(tree_sitter_c.language())
        self.parser = tree_sitter.Parser()
        self.parser.set_language(self.language)

    def process(self, code: str) -> Tuple[str, List[Dict]]:
        """
        Main entry point.
        Returns:
            Tuple[str, List[Dict]]: (Modified code, List of extracted items)
        """
        source_bytes = code.encode('utf8')
        tree = self.parser.parse(source_bytes)
        
        # 1. Find all sql_call occurrences
        all_calls = self._find_all_sql_calls(tree.root_node, source_bytes)
        
        # 2. Group cursor operations (declare...close)
        final_blocks = self._group_and_filter(all_calls)
        
        # 3. Replace ranges in source code
        modified_code = self._replace_ranges(source_bytes, final_blocks)
        
        # 4. Prepare result list
        extracted_items = []
        for block in final_blocks:
            extracted_items.append({
                "sql_id": block['sql_id'],
                "raw_text": block['raw_text'],
                "is_cursor": block['is_cursor']
            })
            
        return modified_code, extracted_items

    def _find_all_sql_calls(self, root_node, source_bytes: bytes) -> List[SqlCallInfo]:
        """Traverse the tree and find all sql_call expressions."""
        calls = []
        
        # Define a query to find function calls
        query = self.language.query("""
        (call_expression
            function: (identifier) @func_name
            arguments: (argument_list 
                (string_literal) @arg1 
                (string_literal) @arg2
            )
        )
        """)
        
        captures = query.captures(root_node)
        
        # Group captures by call_expression node to handle multiple captures per node safely
        # Note: tree-sitter query captures returns a list of (node, capture_name) tuples
        # We need to process them carefully.
        
        # A simpler approach without complex query grouping, 
        # since we want to enforce "sql_call" name check specifically.
        
        self._recursive_find_calls(root_node, source_bytes, calls)
        return calls

    def _recursive_find_calls(self, node, source_bytes: bytes, calls: List[SqlCallInfo]):
        if node.type == 'call_expression':
            func_node = node.child_by_field_name('function')
            if func_node and func_node.type == 'identifier':
                func_name = source_bytes[func_node.start_byte:func_node.end_byte].decode('utf8')
                if func_name == 'sql_call':
                    args_node = node.child_by_field_name('arguments')
                    if args_node:
                        # sql_call should have 2 arguments: string literal, string literal
                        args = []
                        for i in range(args_node.child_count):
                            child = args_node.child(i)
                            if child.type == 'string_literal':
                                # Extract string content (remove quotes)
                                text = source_bytes[child.start_byte:child.end_byte].decode('utf8')
                                val = text.strip('"')
                                args.append(val)
                        
                        if len(args) >= 2:
                            # Determine scope (parent block)
                            scope_node = self._get_scope_node(node)
                            scope_id = str(scope_node.id) if scope_node else "global"
                            
                            calls.append(SqlCallInfo(
                                node=node,
                                sql_id=args[0],
                                arg2=args[1],
                                start_byte=node.start_byte,
                                end_byte=node.end_byte,
                                scope_id=scope_id
                            ))
                            
        for child in node.children:
            self._recursive_find_calls(child, source_bytes, calls)

    def _get_scope_node(self, node):
        """Find the nearest enclosing scope (compound_statement)."""
        curr = node.parent
        while curr:
            if curr.type == 'compound_statement':
                return curr
            curr = curr.parent
        return None

    def _group_and_filter(self, calls: List[SqlCallInfo]) -> List[Dict]:
        """
        Groups declare_cursor...close blocks.
        Returns a list of dicts representing the final blocks to extract.
        """
        final_blocks = []
        absorbed_indices = set()
        
        i = 0
        while i < len(calls):
            if i in absorbed_indices:
                i += 1
                continue
                
            current_call = calls[i]
            
            # Check for declare_cursor
            if "declare_cursor" in current_call.arg2.lower():
                # Look ahead for matching close in the same scope
                match_close_idx = -1
                for j in range(i + 1, len(calls)):
                    candidate = calls[j]
                    if candidate.scope_id == current_call.scope_id:
                        if "close" in candidate.arg2.lower():
                            match_close_idx = j
                            break
                        # Important: if we encounter another declare_cursor in the same scope before a close,
                        # it might be an error or nested/sequential structure. 
                        # For now, we just search for the first CLOSE.
                
                if match_close_idx != -1:
                    # Found a pair
                    close_call = calls[match_close_idx]
                    
                    # Absorb everything between i and match_close_idx (inclusive)
                    # Note: We only absorb "sql_call"s. Code between them is implicitly included in the range.
                    # But wait, the replaced range will be from start of declare to end of close.
                    # We should mark intermediate calls as absorbed so they don't get extracted separately.
                    
                    for k in range(i, match_close_idx + 1):
                        absorbed_indices.add(k)
                        
                    start_byte = current_call.start_byte
                    end_byte = close_call.end_byte
                    
                    final_blocks.append({
                        "sql_id": current_call.sql_id,
                        "raw_text": None, # Filled later
                        "is_cursor": True,
                        "start_byte": start_byte,
                        "end_byte": end_byte,
                        "node": current_call.node # For sorting if needed
                    })
                else:
                    # unmatched declare_cursor, treat as single
                    final_blocks.append({
                        "sql_id": current_call.sql_id,
                        "raw_text": None,
                        "is_cursor": False,
                        "start_byte": current_call.start_byte,
                        "end_byte": current_call.end_byte,
                         "node": current_call.node
                    })
            else:
                # Normal call (or unmatched close, open, fetch etc)
                final_blocks.append({
                    "sql_id": current_call.sql_id,
                    "raw_text": None,
                    "is_cursor": False,
                    "start_byte": current_call.start_byte,
                    "end_byte": current_call.end_byte,
                     "node": current_call.node
                })
            
            i += 1
            
        return final_blocks

    def _replace_ranges(self, source_bytes: bytes, blocks: List[Dict]) -> str:
        """
        Replaces ranges in source code with comments.
        Populates 'raw_text' in blocks.
        """
        # Sort blocks by start_byte reversed to replace from end
        sorted_blocks = sorted(blocks, key=lambda x: x['start_byte'], reverse=True)
        
        # Working with bytearray for mutability
        result_bytes = bytearray(source_bytes)
        
        for block in sorted_blocks:
            start = block['start_byte']
            end = block['end_byte']
            
            # semi-colon handling: try to include the trailing semicolon if present
            # The node.end_byte usually ends after )
            # We peek ahead for ;
            
            # Simple heuristic: scan formatted whitespace until ;
            current_end = end
            while current_end < len(result_bytes):
                char = chr(result_bytes[current_end])
                if char.isspace():
                    current_end += 1
                elif char == ';':
                    current_end += 1 # Include semicolon
                    end = current_end
                    break
                else:
                    break
            
            original_text = result_bytes[start:end].decode('utf8')
            block['raw_text'] = original_text
            
            # Replacement comment
            extract_comment = f"/* [EXTRACTED] {block['sql_id']} */"
            
            # Replace
            result_bytes[start:end] = extract_comment.encode('utf8')
            
        return result_bytes.decode('utf8')
