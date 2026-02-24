import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from proc_parser.core import ProCParser

def test_struct_parsing():
    parser = ProCParser()
    sample_file = os.path.join(project_root, 'tests', 'samples', 'sample.pc')
    
    print(f"Parsing: {sample_file}")
    elements = parser.parse_file(sample_file)
    
    # Filter struct elements
    struct_elements = [e for e in elements if e['type'] == 'struct']
    
    print(f"\n=== Struct Elements Found: {len(struct_elements)} ===")
    for i, el in enumerate(struct_elements):
        print(f"\n[Struct {i+1}]")
        print(f"  Name: {el.get('name')}")
        print(f"  Line: {el.get('line_start')}-{el.get('line_end')}")
        print(f"  Raw Content:\n    {el.get('raw_content', '').replace(chr(10), chr(10)+'    ')}")
    
    # Also check if struct-typed variables are detected
    var_elements = [e for e in elements if e['type'] == 'variable']
    struct_vars = [v for v in var_elements if 'struct' in v.get('data_type', '')]
    
    print(f"\n=== Struct-typed Variables Found: {len(struct_vars)} ===")
    for i, v in enumerate(struct_vars):
        print(f"\n[Struct Variable {i+1}]")
        print(f"  Name: {v.get('name')}")
        print(f"  Data Type: {v.get('data_type')}")
        print(f"  Line: {v.get('line_start')}")
    
    if len(struct_elements) == 0:
        print("\n*** WARNING: No struct definitions found! Parser may not be extracting structs correctly. ***")
    else:
        print("\n*** SUCCESS: Struct parsing is working. ***")

if __name__ == "__main__":
    test_struct_parsing()
