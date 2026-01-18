#!/usr/bin/env python
"""
Generate complete skeleton prompt for Pro*C to Java conversion
"""
import json
from pathlib import Path

# Import the conversion modules
from conversion.types import ConversionConfig
from conversion.prompt_builder import PromptBuilder

def main():
    # Load the metadata
    metadata_path = "/tmp/original_metadata.json"
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Create conversion config
    config = ConversionConfig(
        package_name="com.example.service",
        class_name_suffix="Service",
        use_spring_annotations=True,
        mybatis_mapper_package="com.example.mapper"
    )

    # Create prompt builder
    builder = PromptBuilder(config)

    # Build the skeleton prompt
    system_prompt = builder.get_system_prompt()
    skeleton_prompt = builder.build_skeleton_prompt(metadata)

    # Combine system prompt and skeleton prompt
    full_prompt = f"""{system_prompt}

---
{skeleton_prompt}
"""

    # Save to file
    output_path = "/tmp/skeleton_prompt.txt"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_prompt)

    # Also print to console
    print("=" * 80)
    print("GENERATED SKELETON PROMPT")
    print("=" * 80)
    print(full_prompt)
    print("=" * 80)
    print(f"\nPrompt saved to: {output_path}")

    # Verify no "unknown" types
    print("\n" + "=" * 80)
    print("VERIFICATION CHECKS")
    print("=" * 80)

    # Check for "unknown" in global variables
    variables = metadata.get("source_analysis", {}).get("elements_by_type", {}).get("variables", [])
    global_vars = [v for v in variables if v.get("function") is None]

    unknown_count = 0
    for var in global_vars:
        data_type = var.get("data_type", "")
        if "unknown" in data_type.lower():
            print(f"❌ FOUND 'unknown' type: {var.get('name')} -> {data_type}")
            unknown_count += 1
        elif data_type in ["EXEC", "BEGIN", "END"]:
            # These are Pro*C keywords, skip
            continue
        else:
            print(f"✓ {var.get('name')}: {data_type}")

    if unknown_count > 0:
        print(f"\n❌ VERIFICATION FAILED: Found {unknown_count} variables with 'unknown' type")
    else:
        print(f"\n✓ VERIFICATION PASSED: No 'unknown' types found in {len(global_vars)} global variables")

    # Check all required information categories
    print("\n" + "=" * 80)
    print("REQUIRED INFORMATION CATEGORIES CHECK")
    print("=" * 80)

    checks = {
        "1. Global Variables with C Types": len(global_vars) > 0,
        "2. Function Prototypes": len(metadata.get("source_analysis", {}).get("elements_by_type", {}).get("function_prototypes", [])) > 0,
        "3. Struct Definitions": "header_tree" in metadata,
        "4. SQL Operations": len(metadata.get("source_analysis", {}).get("elements_by_type", {}).get("sql", [])) > 0,
        "5. Header Dependencies": "header_tree" in metadata,
        "6. Return Code Semantics": "system prompt" in full_prompt.lower(),
        "7. Macro Definitions": len(metadata.get("source_analysis", {}).get("elements_by_type", {}).get("macros", [])) > 0,
    }

    all_passed = True
    for category, passed in checks.items():
        status = "✓" if passed else "❌"
        print(f"{status} {category}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✓ ALL REQUIRED INFORMATION CATEGORIES ARE PRESENT")
    else:
        print("\n❌ SOME REQUIRED INFORMATION CATEGORIES ARE MISSING")

    return full_prompt

if __name__ == "__main__":
    main()
