
import sys
import pytest

# Redirect stdout/stderr to a file
with open("test_output.txt", "w") as f:
    sys.stdout = f
    sys.stderr = f
    
    print("Starting tests...")
    ret = pytest.main(["tests/parsing/test_sql_call_extractor.py", "-v"])
    print(f"Tests finished with code: {ret}")

sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
