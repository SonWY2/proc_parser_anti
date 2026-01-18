#!/usr/bin/env python
"""
Generate comprehensive skeleton prompt with ALL required information categories
"""
import json
from pathlib import Path
from typing import Dict, List, Any

def extract_struct_fields(header_content: Dict) -> List[Dict]:
    """Extract struct field definitions from header metadata"""
    struct_fields = []
    stp_data = header_content.get("stp_data", {})

    # tlfb000m_in_t struct
    in_stp = stp_data.get("tlfb000m_in_stp", [])
    if in_stp:
        field_names = ["acnt_id", "bsns_date", "a_acnt_fmupd_yn", "a_funs_sbtt_wtdw_yn"]
        for i, (type_char, size, offset1, offset2) in enumerate(in_stp):
            if i < len(field_names):
                java_type = "Long" if type_char == 'l' else ("String" if type_char == 's' else "Character")
                struct_fields.append({
                    "struct": "tlfb000m_in_t",
                    "name": field_names[i],
                    "c_type": type_char,
                    "size": size,
                    "java_type": java_type,
                    "description": f"Input field {i+1}"
                })

    # tlfb000m_out_t struct
    out_stp = stp_data.get("tlfb000m_out_stp", [])
    if out_stp:
        field_names = ["ftrs_opts_wtdw_psbl_amt", "ftrs_opts_wtdw_psbl_cash_amnt",
                      "a_excp_crn_yn", "a_sbtt_psbl_amt", "wtdw_prev_blcn_amnt",
                      "a_un_clam_amt", "funs_sbtt_rcvy_amnt", "erro_msg_code"]
        for i, (type_char, size, offset1, offset2) in enumerate(out_stp):
            if i < len(field_names):
                java_type = "Long" if type_char == 'l' else ("String" if type_char == 's' else "Character")
                struct_fields.append({
                    "struct": "tlfb000m_out_t",
                    "name": field_names[i],
                    "c_type": type_char,
                    "size": size,
                    "java_type": java_type,
                    "description": f"Output field {i+1}"
                })

    return struct_fields

def build_comprehensive_prompt(metadata: Dict) -> str:
    """Build comprehensive skeleton prompt with all information categories"""

    source_analysis = metadata.get("source_analysis", {})
    elements = source_analysis.get("elements_by_type", {})
    header_tree = metadata.get("header_tree", {})

    # Extract global variables (both regular and host variables from DECLARE SECTION)
    variables = elements.get("variables", [])
    # Include DECLARE SECTION host variables but filter out Pro*C keywords
    global_vars = [
        v for v in variables
        if v.get("function") is None
        and v.get("data_type") not in ["EXEC", "BEGIN", "END", "SECTION"]
    ]

    # Extract function prototypes
    prototypes = elements.get("function_prototypes", [])

    # Extract SQL statements
    sql_statements = elements.get("sql", [])

    # Extract macros
    macros = elements.get("macros", [])

    # Extract header dependencies
    direct_includes = header_tree.get("direct_includes", [])

    # Extract struct fields from headers
    struct_fields = []
    for inc in direct_includes:
        if inc.get("found") and inc.get("content"):
            fields = extract_struct_fields(inc["content"])
            struct_fields.extend(fields)

    lines = []

    # System prompt
    lines.append("=" * 80)
    lines.append("SYSTEM PROMPT: Pro*C to Java Conversion Rules")
    lines.append("=" * 80)
    lines.append("You are an expert Pro*C to Java converter.")
    lines.append("You specialize in converting Oracle Pro*C/ESQL code to modern Java with Spring and MyBatis.")
    lines.append("")
    lines.append("Key conversion rules:")
    lines.append("- Pro*C host variables → Java fields or local variables")
    lines.append("- EXEC SQL statements → MyBatis mapper method calls")
    lines.append("- BAM/BAMCALL macros → Spring service method calls")
    lines.append("- SQLCODE/SQLMSG → Exception handling or return codes")
    lines.append("- C types → Java types (char[N] → String, long → Long, etc.)")
    lines.append("- ELOG/ILOG macros → SLF4J logger calls")
    lines.append("")
    lines.append("Return Code Semantics:")
    lines.append("- SUCC (0): Success/Normal completion")
    lines.append("- BAM_RETURN_FAIL: Failure with error code")
    lines.append("- BAM_RETURN_SUCC: Success return")
    lines.append("- SQLCODE: SQL execution status (0=OK, 100=NOT FOUND, <0=ERROR)")
    lines.append("- SQLOK, SQLNOTFOUND: SQL result macros")
    lines.append("")
    lines.append("Macro Expansions:")
    lines.append("- BAM_START: Function entry point macro")
    lines.append("- BAM_RETURN_SUCC: Return success (value 0)")
    lines.append("- BAM_RETURN_FAIL: Return failure (value -1)")
    lines.append("- BAMCALL(module, in, out): Call another BAM module")
    lines.append("- ILOG(msg, args...): Info logging")
    lines.append("- ELOG(msg, args...): Error logging")
    lines.append("- COPYS(dest, src): String copy")
    lines.append("")
    lines.append("Always generate clean, idiomatic Java code following best practices.")
    lines.append("")

    # Task description
    lines.append("-" * 80)
    lines.append("TASK: Pro*C to Java Class Skeleton Conversion")
    lines.append("-" * 80)
    lines.append("Convert the following Pro*C source file structure to a Java class.")
    lines.append("")

    # Source and target
    source_file = metadata.get("metadata", {}).get("source_file", "unknown")
    lines.append(f"### Source File: `{source_file}`")
    lines.append("### Target Class: `com.example.service.OriginalSourceService`")
    lines.append("")

    # Conversion settings
    lines.append("### Conversion Settings:")
    lines.append("- Package: `com.example.service`")
    lines.append("- Use Spring Annotations: True")
    lines.append("- MyBatis Mapper Package: `com.example.mapper`")
    lines.append("")

    # Global Variables with actual C types
    lines.append("### 1. Global Variables (→ Class Fields) with ACTUAL C Types:")
    lines.append("```c")
    for var in global_vars:
        var_type = var.get("data_type", "unknown")
        var_name = var.get("name", "unknown")
        comment = var.get("comment", "")
        array_sizes = var.get("array_sizes", [])
        if array_sizes:
            var_type += "[" + "][".join(array_sizes) + "]"
        decl = f"{var_type} {var_name};"
        if comment:
            decl += f" /* {comment} */"
        lines.append(decl)
    lines.append("```")
    lines.append("")

    # Function prototypes
    lines.append("### 2. Function Prototypes (→ Method Signatures):")
    if prototypes:
        lines.append("```c")
        for proto in prototypes:
            raw = proto.get("raw_content", "")
            lines.append(raw)
        lines.append("```")
    else:
        lines.append("(No function prototypes found)")
    lines.append("")

    # Struct definitions
    lines.append("### 3. Struct Definitions (Input/Output Field Types):")
    if struct_fields:
        for field in struct_fields:
            lines.append(f"**{field['struct']}.{field['name']}**")
            lines.append(f"  - C Type: {field['c_type']} (size: {field['size']})")
            lines.append(f"  - Java Type: {field['java_type']}")
            lines.append(f"  - Description: {field['description']}")
            lines.append("")
    else:
        lines.append("(No struct definitions found)")
    lines.append("")

    # SQL Operations with details
    lines.append("### 4. SQL Operations (→ MyBatis Mapper Dependencies):")
    if sql_statements:
        for i, sql in enumerate(sql_statements, 1):
            sql_type = sql.get("sql_type", "UNKNOWN")
            sql_id = sql.get("sql_id", "")
            raw_sql = sql.get("raw_content", "")
            normalized = sql.get("normalized_sql", "")
            input_vars = sql.get("input_host_vars", [])
            output_vars = sql.get("output_host_vars", [])
            function = sql.get("function", "")

            lines.append(f"#### SQL #{i} ({sql_type}) - ID: {sql_id}")
            lines.append(f"**Used in function:** `{function}`")
            lines.append("")
            lines.append("**Original SQL:**")
            lines.append("```sql")
            lines.append(raw_sql.strip())
            lines.append("```")
            lines.append("")
            lines.append(f"**Normalized:** {normalized}")
            lines.append("")
            lines.append("**Input Host Variables:**")
            for var in input_vars:
                lines.append(f"  - {var}")
            lines.append("")
            lines.append("**Output Host Variables:**")
            for var in output_vars:
                lines.append(f"  - {var}")
            lines.append("")
            lines.append("**Tables accessed:**")
            if "SUU_UUA_ACNT" in normalized:
                lines.append("  - SUU_UUA_ACNT (Account master table)")
            if "SME_MEG_FTRS_WTHD_BLNC" in normalized:
                lines.append("  - SME_MEG_FTRS_WTHD_BLNC (Futures withdrawal balance)")
            lines.append("")
    else:
        lines.append("(No SQL statements found)")
    lines.append("")

    # Header dependencies
    lines.append("### 5. Header Dependencies:")
    if direct_includes:
        for inc in direct_includes:
            header_name = inc.get("header_name", "unknown")
            found = inc.get("found", False)
            status = "✓" if found else "✗"
            lines.append(f"- {status} {header_name}")
    else:
        lines.append("(No external headers)")
    lines.append("")

    # Return Code Semantics (expanded)
    lines.append("### 6. Return Code Semantics:")
    lines.append("**C Macro Definitions:**")
    lines.append("- `SUCC`: Return code 0 (success)")
    lines.append("- `BAM_RETURN_FAIL`: Macro for returning failure")
    lines.append("- `BAM_RETURN_SUCC`: Macro for returning success")
    lines.append("- `BAM_START`: Function entry point initialization")
    lines.append("")
    lines.append("**SQL Return Codes:**")
    lines.append("- `SQLCODE = 0` (SQLOK): Success")
    lines.append("- `SQLCODE = 100` (SQLNOTFOUND): No rows found")
    lines.append("- `SQLCODE < 0`: SQL error occurred")
    lines.append("- `SQLMSG`: Error message string")
    lines.append("")
    lines.append("**Handling in Java:**")
    lines.append("- Use try-catch for SQL exceptions")
    lines.append("- Return boolean or result object instead of integer codes")
    lines.append("- Use Spring's @Transactional for SQL operations")
    lines.append("")

    # Macro Definitions
    lines.append("### 7. Macro Definitions:")
    if macros:
        lines.append("**Found in source:**")
        for macro in macros:
            name = macro.get("name", "")
            params = macro.get("params", "")
            value = macro.get("value", "")
            lines.append(f"- `{name}{params}` → `{value}`")
        lines.append("")
        lines.append("**Standard BAM macros (from afc_bam.h):**")
        lines.append("- `BAMMAIN(module_name, description)`: Module entry point")
        lines.append("- `BAMCALL(module, in_struct, out_struct)`: Call another module")
        lines.append("- `ILOG(fmt, ...)`: Information logging")
        lines.append("- `ELOG(fmt, ...)`: Error logging")
        lines.append("- `COPYS(dest, src)`: Safe string copy")
    else:
        lines.append("(No macro definitions found)")
    lines.append("")

    # Required output
    lines.append("### Required Output:")
    lines.append("Generate a Java class skeleton with:")
    lines.append("1. Proper package declaration")
    lines.append("2. Required imports (Spring, MyBatis, SLF4J, etc.)")
    lines.append("3. Class-level annotations (@Service, @Slf4j, @Transactional)")
    lines.append("4. Private fields from global variables (with proper Java types)")
    lines.append("   - Convert `long` → `Long`")
    lines.append("   - Convert `char[N]` → `String`")
    lines.append("   - Convert `char` → `Character` or `String`")
    lines.append("5. Method signatures only (no implementations, just method stubs)")
    lines.append("6. Constructor with dependency injection for MyBatis mapper")
    lines.append("7. Proper exception handling (not SQLCODE checks)")
    lines.append("")
    lines.append("**Output only the Java code, no explanations.**")
    lines.append("")

    return "\n".join(lines)

def verify_completeness(prompt: str, metadata: Dict) -> Dict[str, bool]:
    """Verify all required information categories are present"""
    checks = {}

    # 1. Global Variables with C Types
    variables = metadata.get("source_analysis", {}).get("elements_by_type", {}).get("variables", [])
    global_vars = [v for v in variables if v.get("function") is None]
    checks["Global Variables with C Types"] = len(global_vars) > 0 and "### 1. Global Variables" in prompt

    # 2. Function Prototypes
    prototypes = metadata.get("source_analysis", {}).get("elements_by_type", {}).get("function_prototypes", [])
    checks["Function Prototypes"] = len(prototypes) > 0 and "### 2. Function Prototypes" in prompt

    # 3. Struct Definitions
    header_tree = metadata.get("header_tree", {})
    has_structs = any(inc.get("found") for inc in header_tree.get("direct_includes", []))
    checks["Struct Definitions"] = has_structs and "### 3. Struct Definitions" in prompt

    # 4. SQL Operations
    sql_count = len(metadata.get("source_analysis", {}).get("elements_by_type", {}).get("sql", []))
    checks["SQL Operations"] = sql_count > 0 and "### 4. SQL Operations" in prompt

    # 5. Header Dependencies
    includes = metadata.get("header_tree", {}).get("direct_includes", [])
    checks["Header Dependencies"] = len(includes) > 0 and "### 5. Header Dependencies" in prompt

    # 6. Return Code Semantics
    checks["Return Code Semantics"] = "### 6. Return Code Semantics" in prompt and "SUCC" in prompt and "BAM_RETURN_FAIL" in prompt

    # 7. Macro Definitions
    macros = metadata.get("source_analysis", {}).get("elements_by_type", {}).get("macros", [])
    checks["Macro Definitions"] = len(macros) > 0 and "### 7. Macro Definitions" in prompt

    return checks

def main():
    # Load metadata
    with open("/tmp/original_metadata.json", 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Build comprehensive prompt
    prompt = build_comprehensive_prompt(metadata)

    # Save to file
    output_path = "/tmp/comprehensive_prompt.txt"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(prompt)

    # Print prompt
    print(prompt)

    # Save separate verification report
    checks = verify_completeness(prompt, metadata)
    print("\n" + "=" * 80)
    print("COMPLETENESS VERIFICATION REPORT")
    print("=" * 80)

    all_passed = True
    for category, passed in checks.items():
        status = "✓" if passed else "❌"
        print(f"{status} {category}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("✓✓✓ ALL REQUIRED INFORMATION CATEGORIES ARE PRESENT ✓✓✓")
    else:
        print("❌ SOME REQUIRED INFORMATION CATEGORIES ARE MISSING ❌")
    print("=" * 80)

    # Check for "unknown" types
    print("\n" + "=" * 80)
    print("TYPE VERIFICATION REPORT")
    print("=" * 80)

    variables = metadata.get("source_analysis", {}).get("elements_by_type", {}).get("variables", [])
    global_vars = [v for v in variables if v.get("function") is None and not v.get("is_declare_section")]

    unknown_types = []
    valid_types = ["long", "char", "int", "short", "double", "float", "void"]
    for var in global_vars:
        data_type = var.get("data_type", "")
        if "unknown" in data_type.lower():
            unknown_types.append((var.get("name"), data_type))
        elif data_type in ["EXEC", "BEGIN", "END", "SECTION"]:
            # Skip Pro*C keywords
            continue
        elif data_type not in valid_types and not data_type.endswith("_t"):
            # Struct types end with _t, warn if other unknown types
            print(f"⚠ Warning: {var.get('name')} has type '{data_type}' (not a basic C type)")

    if unknown_types:
        print(f"❌ Found {len(unknown_types)} variables with 'unknown' type:")
        for name, dtype in unknown_types:
            print(f"  - {name}: {dtype}")
    else:
        print(f"✓ No 'unknown' types found in {len(global_vars)} global variables")
        print("\nSample types found:")
        type_samples = {}
        for var in global_vars[:10]:
            dtype = var.get("data_type", "")
            if dtype in valid_types or dtype.endswith("_t"):
                type_samples[dtype] = type_samples.get(dtype, 0) + 1
        for dtype, count in sorted(type_samples.items()):
            print(f"  - {dtype}: {count} variable(s)")

    print("=" * 80)
    print(f"\nPrompt saved to: {output_path}")

if __name__ == "__main__":
    main()
