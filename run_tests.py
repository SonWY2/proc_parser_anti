import pytest
import sys
import os

print("Starting test execution...")
output_file = "test_run_output.txt"

# Redirect stdout/stderr to file
with open(output_file, "w", encoding="utf-8") as f:
    sys.stdout = f
    sys.stderr = f
    
    print("Running newly created plugin tests...")
    ret1 = pytest.main(["-v", "tests/unit/test_lineage_plugins.py"])
    print(f"\nPlugin tests result: {ret1}")
    
    print("\nRunning existing variable lineage tests...")
    ret2 = pytest.main(["-v", "tests/unit/test_variable_lineage.py"])
    print(f"\nExisting tests result: {ret2}")

print("Test execution finished.")
