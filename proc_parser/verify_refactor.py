
import sys
import os

# Ensure project root is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"Project root added to path: {project_root}")
sys.stdout.flush()

try:
    from proc_parser.core import ProCParser
    print("Successfully imported ProCParser")
except ImportError as e:
    print(f"Failed to import ProCParser: {e}")
    sys.exit(1)


def verify():
    with open('verification_result.txt', 'w') as log_file:
        def log(msg):
            log_file.write(msg + '\n')
            log_file.flush()
            
        log("Initializing parser...")
        try:
            parser = ProCParser()
            log("Parser initialized.")
        except Exception as e:
            log(f"Failed to initialize parser: {e}")
            return

        sample_file = os.path.join(project_root, 'tests', 'samples', 'sample.pc')
        
        if os.path.exists(sample_file):
            log(f"Parsing file: {sample_file}")
        else:
            log("Sample file not found, creating a dummy file.")
            sample_file = os.path.join(current_dir, 'dummy.pc')
            with open(sample_file, 'w') as f:
                f.write("""
                #include <stdio.h>
                EXEC SQL INCLUDE sqlca;
                
                void main() {
                    EXEC SQL BEGIN DECLARE SECTION;
                    char *uid = "scott/tiger";
                    EXEC SQL END DECLARE SECTION;
                    
                    EXEC SQL CONNECT :uid;
                    
                    printf("Connected\\n");
                }
                """)
        
        try:
            elements = parser.parse_file(sample_file)
            log(f"Successfully parsed {len(elements)} elements.")
            
            sql_elements = [e for e in elements if e['type'] == 'sql']
            log(f"SQL Elements found: {len(sql_elements)}")
            for i, el in enumerate(sql_elements):
                log(f"  SQL {i+1}: {el.get('raw_content', '')[:50]}...")

            func_elements = [e for e in elements if e['type'] == 'function']
            log(f"Functions found: {len(func_elements)}")
            
            unknown_elements = [e for e in elements if e['type'] == 'unknown']
            log(f"Unknown elements: {len(unknown_elements)}")
            
            if len(sql_elements) > 0 and len(func_elements) > 0:
                 log("VERIFICATION SUCCESS: Logic seems preserved.")
            else:
                 log("VERIFICATION WARNING: Missing expected elements.")

        except Exception as e:
            log(f"Parsing failed: {e}")
            import traceback
            traceback.print_exc(file=log_file)

if __name__ == "__main__":
    verify()
