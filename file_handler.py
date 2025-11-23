import os
import json
from parser_core import ProCParser

def process_directory(input_dir, output_dir):
    """
    Walk through input_dir, parse .pc and .h files, and write results to output_dir.
    Results are separated by element type (e.g., sql.jsonl, function.jsonl).
    """
    parser = ProCParser()
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Clear existing type files or prepare to append? 
    # For a fresh run, we should probably overwrite.
    # Let's collect all elements first or write incrementally?
    # Writing incrementally is better for large datasets.
    # But we need to ensure we start fresh.
    
    # We'll use a set to track which files we've opened in this run to truncate them first
    initialized_files = set()

    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith(('.pc', '.h')):
                file_path = os.path.join(root, file)
                print(f"Processing {file_path}...")
                
                try:
                    elements = parser.parse_file(file_path)
                    
                    # Group by type
                    elements_by_type = {}
                    for el in elements:
                        el_type = el.get('type', 'unknown')
                        if el_type not in elements_by_type:
                            elements_by_type[el_type] = []
                        elements_by_type[el_type].append(el)
                    
                    # Write to type-specific files
                    for el_type, items in elements_by_type.items():
                        output_filename = f"{el_type}.jsonl"
                        output_file_path = os.path.join(output_dir, output_filename)
                        
                        mode = 'a'
                        if output_filename not in initialized_files:
                            mode = 'w' # Overwrite on first write of this run
                            initialized_files.add(output_filename)
                            
                        with open(output_file_path, mode, encoding='utf-8') as f:
                            for item in items:
                                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                                
                except Exception as e:
                    print(f"Failed to process {file_path}: {e}")

