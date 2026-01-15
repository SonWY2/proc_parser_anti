"""
Test script for verifying proc_parser functionality with original_source.sqc
"""
import json
import os
import sys
from collections import Counter

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from proc_parser import ProCParser

def main():
    # Input file
    input_file = os.path.join(os.path.dirname(__file__), "sample_input", "original_source.sqc")
    output_dir = os.path.join(os.path.dirname(__file__), "test_output_original_source")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"Parsing: {input_file}")
    print("=" * 80)
    
    # Create parser and parse
    parser = ProCParser()
    elements = parser.parse_file(input_file, output_dir=output_dir, create_debug_file=False)
    
    # Count elements by type
    type_counter = Counter(el.get('type', 'unknown') for el in elements)
    
    print("\n=== ELEMENT SUMMARY ===")
    for el_type, count in sorted(type_counter.items()):
        print(f"  {el_type}: {count}")
    
    print(f"\nTotal elements: {len(elements)}")
    
    # Save all elements to JSON for inspection
    output_file = os.path.join(output_dir, "all_elements.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(elements, f, ensure_ascii=False, indent=2)
    print(f"\nFull output saved to: {output_file}")
    
    # === SQL Elements Analysis ===
    print("\n" + "=" * 80)
    print("=== SQL ELEMENTS ANALYSIS ===")
    sql_elements = [el for el in elements if el.get('type') == 'sql']
    
    for i, sql in enumerate(sql_elements, 1):
        print(f"\n--- SQL #{i} ---")
        print(f"  ID: {sql.get('id', 'N/A')}")
        print(f"  SQL Type: {sql.get('sql_type', 'N/A')}")
        print(f"  Line: {sql.get('start_line', 'N/A')} - {sql.get('end_line', 'N/A')}")
        print(f"  In Function: {sql.get('function_name', 'N/A')}")
        
        # Input variables
        in_vars = sql.get('input_variables', [])
        print(f"  Input Variables ({len(in_vars)}): {in_vars}")
        
        # Output variables
        out_vars = sql.get('output_variables', [])
        print(f"  Output Variables ({len(out_vars)}): {out_vars}")
        
        # Alias info
        alias = sql.get('alias', None)
        if alias:
            print(f"  Alias: {alias}")
        
        # First 100 chars of SQL
        normalized = sql.get('normalized_sql', sql.get('content', ''))[:200]
        print(f"  SQL (first 200 chars): {normalized}...")
    
    # === Check for Unparsed Elements ===
    print("\n" + "=" * 80)
    print("=== UNPARSED SEGMENTS ===")
    unparsed = [el for el in elements if el.get('type') == 'unparsed']
    
    if unparsed:
        print(f"Found {len(unparsed)} unparsed segments:")
        for i, up in enumerate(unparsed, 1):
            content = up.get('content', '')[:100]
            print(f"\n--- Unparsed #{i} ---")
            print(f"  Line: {up.get('start_line', 'N/A')} - {up.get('end_line', 'N/A')}")
            print(f"  Content (first 100 chars): {content}...")
    else:
        print("No unparsed segments found. All code was successfully parsed!")
    
    # === Functions Analysis ===
    print("\n" + "=" * 80)
    print("=== FUNCTIONS ANALYSIS ===")
    functions = [el for el in elements if el.get('type') == 'function']
    
    for i, func in enumerate(functions, 1):
        print(f"\n--- Function #{i}: {func.get('name', 'N/A')} ---")
        print(f"  Return Type: {func.get('return_type', 'N/A')}")
        print(f"  Line: {func.get('start_line', 'N/A')} - {func.get('end_line', 'N/A')}")
        params = func.get('parameters', [])
        print(f"  Parameters: {params}")
    
    # === Host Variables Analysis ===
    print("\n" + "=" * 80)
    print("=== HOST VARIABLES (from DECLARE SECTION) ===")
    host_vars = [el for el in elements if el.get('type') == 'host_variable']
    
    for i, var in enumerate(host_vars[:20], 1):  # First 20
        print(f"  {i}. {var.get('name', 'N/A')} : {var.get('data_type', 'N/A')}")
    
    if len(host_vars) > 20:
        print(f"  ... and {len(host_vars) - 20} more host variables")
    
    # === Check for OMM/DBIO/DAO generation ===
    print("\n" + "=" * 80)
    print("=== OMM/DBIO/DAO GENERATION CHECK ===")
    
    # Check if OMM/DBIO files exist
    omm_dir = os.path.join(output_dir, "omm")
    dbio_dir = os.path.join(output_dir, "dbio")
    dao_dir = os.path.join(output_dir, "dao")
    
    for gen_type, gen_dir in [("OMM", omm_dir), ("DBIO", dbio_dir), ("DAO", dao_dir)]:
        if os.path.exists(gen_dir):
            files = os.listdir(gen_dir)
            print(f"  {gen_type}: {len(files)} files generated in {gen_dir}")
            for f in files[:5]:
                print(f"    - {f}")
        else:
            print(f"  {gen_type}: Directory not found (may require separate generator)")
    
    # === Validation Summary ===
    print("\n" + "=" * 80)
    print("=== VALIDATION SUMMARY ===")
    
    issues = []
    
    # Check SQL parsing
    if len(sql_elements) == 0:
        issues.append("WARNING: No SQL elements extracted!")
    else:
        print(f"✓ SQL parsing: {len(sql_elements)} SQL statements found")
    
    # Check for SQLs without variables
    sql_no_vars = [sql for sql in sql_elements 
                   if not sql.get('input_variables') and not sql.get('output_variables')]
    if sql_no_vars and any(sql.get('sql_type') not in ['COMMIT', 'ROLLBACK'] for sql in sql_no_vars):
        issues.append(f"WARNING: {len(sql_no_vars)} SELECT/UPDATE/INSERT SQLs have no I/O variables")
    
    # Check for unparsed segments
    if unparsed:
        issues.append(f"WARNING: {len(unparsed)} unparsed segments found")
    
    # Check functions
    if len(functions) == 0:
        issues.append("WARNING: No functions extracted!")
    else:
        print(f"✓ Function parsing: {len(functions)} functions found")
    
    # Check host variables
    if len(host_vars) == 0:
        issues.append("WARNING: No host variables extracted!")
    else:
        print(f"✓ Host variable parsing: {len(host_vars)} host variables found")
    
    # Print issues
    if issues:
        print("\n--- ISSUES FOUND ---")
        for issue in issues:
            print(f"  ⚠ {issue}")
    else:
        print("\n✓ All checks passed!")
    
    return len(issues) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
