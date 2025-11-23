import tree_sitter
try:
    import tree_sitter_c
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    print("Warning: tree-sitter-c not found. C parsing will be limited.")

class CParser:
    def __init__(self):
        if HAS_TREE_SITTER:
            self.language = tree_sitter.Language(tree_sitter_c.language())
            self.parser = tree_sitter.Parser(self.language)
        else:
            self.parser = None

    def parse(self, source_code):
        """
        Parse C source code and extract functions, structs, variables.
        """
        elements = []
        if not self.parser:
            return elements

        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node
        
        # Use manual traversal instead of queries for better compatibility
        # across different tree-sitter versions
        self._traverse(root_node, elements)
        
        return elements

    def _traverse(self, node, elements, current_function=None):
        # Recursive traversal
        
        node_type = node.type
        
        if node_type == 'function_definition':
            # Extract function name
            func_name = self._get_function_name(node)
            if func_name:
                elements.append({
                    "type": "function",
                    "name": func_name,
                    "line_start": node.start_point.row + 1,
                    "line_end": node.end_point.row + 1,
                    "raw_content": node.text.decode('utf8'),
                    "function": None # Top level
                })
                current_function = func_name
        
        elif node_type == 'declaration':
            # Variable declaration
            var_name, var_type = self._get_variable_info(node)
            if var_name:
                elements.append({
                    "type": "variable",
                    "name": var_name,
                    "data_type": var_type,
                    "line_start": node.start_point.row + 1,
                    "line_end": node.end_point.row + 1,
                    "raw_content": node.text.decode('utf8'),
                    "function": current_function
                })

        elif node_type == 'struct_specifier':
            struct_name = self._get_struct_name(node)
            if struct_name:
                 elements.append({
                    "type": "struct",
                    "name": struct_name,
                    "line_start": node.start_point.row + 1,
                    "line_end": node.end_point.row + 1,
                    "raw_content": node.text.decode('utf8'),
                    "function": current_function
                })

        for child in node.children:
            self._traverse(child, elements, current_function)

    def _get_function_name(self, node):
        # child: declarator -> function_declarator -> declarator -> identifier
        declarator = node.child_by_field_name('declarator')
        if not declarator: return None
        
        while declarator.type == 'pointer_declarator':
            declarator = declarator.child_by_field_name('declarator')
            
        if declarator.type == 'function_declarator':
            identifier = declarator.child_by_field_name('declarator')
            if identifier and identifier.type == 'identifier':
                return identifier.text.decode('utf8')
        return None

    def _get_variable_info(self, node):
        # type, declarator
        type_node = node.child_by_field_name('type')
        declarator = node.child_by_field_name('declarator')
        
        if not type_node or not declarator: return None, None
        
        var_type = type_node.text.decode('utf8')
        
        # Handle pointers, arrays, inits
        while declarator.type in ['pointer_declarator', 'array_declarator', 'init_declarator']:
            declarator = declarator.child_by_field_name('declarator')
            
        if declarator and declarator.type == 'identifier':
            return declarator.text.decode('utf8'), var_type
            
        return None, None

    def _get_struct_name(self, node):
        name_node = node.child_by_field_name('name')
        if name_node and name_node.type == 'type_identifier':
            return name_node.text.decode('utf8')
        return None

