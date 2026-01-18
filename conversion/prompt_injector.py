"""
Simple Prompt Injector for Pro*C to Java conversion.

Template-based prompt builder using f-strings.
Allows injecting context from multiple sources into skeleton/function conversion prompts.

Features:
- F-string based template building (no external dependencies)
- Section-based composition (system, task, context, instructions)
- Context injection from multiple sources (metadata, previous functions, custom context)
- Variable validation
- Template registry with custom templates

Usage:
    from conversion.prompt_injector import PromptTemplate, PromptInjector, TemplateRegistry

    # 1. Define template or use built-in
    template = PromptTemplate.from_builtin("skeleton")

    # 2. Create injector
    injector = PromptInjector(template)

    # 3. Inject variables
    prompt = injector.build({
        "source_file": "original_source.sqc",
        "class_name": "Tlfb000mService",
        "global_vars": [...],
        "function_prototypes": [...],
        "sql_operations": [...],
        "config": {...},
        # Custom context
        "additional_context": "...",
        "previous_functions": [...],
    })
"""

from typing import Dict, Any, List, Optional


# ============================================================================
# BUILT-IN TEMPLATES
# ============================================================================

SKELETON_TEMPLATE = """## Task: Pro*C to Java Class Skeleton Conversion

Convert following Pro*C source file structure to a Java class.

### Source File: `{source_file}`
### Target Class: `{package}.{class_name}`

### Conversion Settings:
- Package: `{package}`
- Use Spring Annotations: {use_spring_annotations}
- MyBatis Mapper Package: `{mybatis_mapper_package}`

### Global Variables (→ Class Fields):
{global_vars_section}

### Function Prototypes (→ Method Signatures):
{function_prototypes_section}

### SQL Operations (→ MyBatis Mapper Dependencies):
{sql_operations_section}

### Header Dependencies:
{header_dependencies_section}

### Required Output:
Generate a Java class skeleton with:
1. Proper package declaration
2. Required imports (Spring, MyBatis, etc.)
3. Class-level annotations (@Service, @Slf4j if applicable)
4. Private fields from global variables (with proper Java types)
5. Method signatures only (no implementations, just method stubs)
6. Constructor with dependency injection

Output only Java code, no explanations.
"""


FUNCTION_TEMPLATE = """## Task: Pro*C Function to Java Method Conversion

Convert following Pro*C function to a Java method.

### Function: `{function_name}` → `{java_method_name}`
{documentation_section}

### Original Pro*C Code:
```c
{original_code}
```
{sql_statements_section}

{local_variables_section}

{called_functions_section}

{class_fields_section}

### Conversion Instructions:
1. Convert C types to Java types
2. Replace embedded SQL with MyBatis mapper method calls
3. Convert BAM calls to appropriate Spring service calls
4. Handle SQLCODE checks with try-catch or return values
5. Use SLF4J logging instead of ELOG/ILOG macros
6. Keep business logic intact

Output only Java method code, no explanations.
"""


SYSTEM_PROMPT = """You are an expert Pro*C to Java converter.
You specialize in converting Oracle Pro*C/ESQL code to modern Java with Spring and MyBatis.

Key conversion rules:
- Pro*C host variables → Java fields or local variables
- EXEC SQL statements → MyBatis mapper method calls
- BAM/BAMCALL macros → Spring service method calls
- SQLCODE/SQLMSG → Exception handling or return codes
- C types → Java types (char[N] → String, long → Long, etc.)
- ELOG/ILOG macros → SLF4J logger calls

Always generate clean, idiomatic Java code following best practices."""


# ============================================================================
# TEMPLATE REGISTRY
# ============================================================================

class TemplateRegistry:
    """Registry of built-in prompt templates."""

    _templates = {
        "skeleton": SKELETON_TEMPLATE,
        "function": FUNCTION_TEMPLATE,
        "system": SYSTEM_PROMPT,
    }

    @classmethod
    def get_template(cls, template_name: str) -> str:
        """Get a template by name."""
        if template_name not in cls._templates:
            raise ValueError(f"Template '{template_name}' not found. Available: {list(cls._templates.keys())}")
        return cls._templates[template_name]

    @classmethod
    def list_templates(cls) -> List[str]:
        """List all available templates."""
        return list(cls._templates.keys())

    @classmethod
    def register_template(cls, template_name: str, template: str) -> None:
        """Register a custom template."""
        cls._templates[template_name] = template


# ============================================================================
# PROMPT TEMPLATE
# ============================================================================

class PromptTemplate:
    """Wrapper for a prompt template with f-string rendering."""

    def __init__(self, template_name: str, template_str: Optional[str] = None):
        """
        Args:
            template_name: Name identifier for template
            template_str: Custom template string (None if using built-in)
        """
        self.template_name = template_name

        if template_str:
            self.template_str = template_str
        else:
            self.template_str = TemplateRegistry.get_template(template_name)

    def build(self, context: Dict[str, Any]) -> str:
        """
        Build prompt from template with context injection.

        Args:
            context: Dictionary of variables to inject into template

        Returns:
            Rendered prompt string
        """
        # Build context dictionary with None defaults for missing values
        safe_context = {
            "source_file": context.get("source_file"),
            "package": context.get("package", "com.example.service"),
            "class_name": context.get("class_name", "UnknownService"),
            "use_spring_annotations": context.get("use_spring_annotations", True),
            "mybatis_mapper_package": context.get("mybatis_mapper_package", "com.example.mapper"),
            "global_vars": context.get("global_vars", []),
            "function_prototypes": context.get("function_prototypes", []),
            "functions": context.get("functions", []),
            "sql_operations": context.get("sql_operations", {}),
            "header_dependencies": context.get("header_dependencies", []),
            # Function-specific context
            "function_name": context.get("function_name"),
            "java_method_name": context.get("java_method_name"),
            "original_code": context.get("original_code", ""),
            "documentation": context.get("documentation", ""),
            "sql_statements": context.get("sql_statements", []),
            "local_variables": context.get("local_variables", []),
            "called_functions": context.get("called_functions", []),
            "class_fields": context.get("class_fields", []),
            "additional_context": context.get("additional_context", ""),
            "system_prompt": context.get("system_prompt"),
            "generated_at": context.get("generated_at", "unknown"),
        }

        # Build sections
        sections = []

        # 1. Global variables section
        sections.append(self._build_global_vars_section(safe_context))

        # 2. Function prototypes section
        sections.append(self._build_function_prototypes_section(safe_context))

        # 3. SQL operations section
        sections.append(self._build_sql_operations_section(safe_context))

        # 4. Header dependencies section
        sections.append(self._build_header_dependencies_section(safe_context))

        # 5. Function-specific sections
        if "function_name" in context:
            sections.append(self._build_function_specific_sections(safe_context))

        # 6. Output requirements
        sections.append(self._build_output_requirements_section(safe_context))

        # 7. Custom context
        if safe_context.get("additional_context"):
            sections.append(f"\n### Additional Context:\n{safe_context['additional_context']}")

        # Combine with system prompt
        system_prompt = safe_context.get("system_prompt", TemplateRegistry.get_template("system"))
        full_prompt = f"{system_prompt}\n\n"
        full_prompt += "\n\n".join(sections)

        return full_prompt

    def _build_global_vars_section(self, context: Dict[str, Any]) -> str:
        """Build global variables section."""
        global_vars = context.get("global_vars", [])
        if global_vars:
            lines = ["```c"]
            for var in global_vars[:20]:
                var_type = var.get("var_type", "unknown")
                var_name = var.get("name", "unknown")
                array_sizes = var.get("resolved_array_sizes") or var.get("array_sizes", [])
                if array_sizes:
                    suffix = "".join(f"[{'' if size is None else size}]" for size in array_sizes)
                    lines.append(f"{var_type} {var_name}{suffix};")
                else:
                    lines.append(f"{var_type} {var_name};")
            if len(global_vars) > 20:
                lines.append(f"// ... and {len(global_vars) - 20} more variables")
            lines.append("```")
            return "\n".join(lines)
        else:
            return "(No global variables)"

    def _build_function_prototypes_section(self, context: Dict[str, Any]) -> str:
        """Build function prototypes section."""
        prototypes = context.get("function_prototypes", [])
        if prototypes:
            lines = ["```c"]
            for proto in prototypes:
                lines.append(proto.get("raw_content", ""))
            lines.append("```")
            return "\n".join(lines)
        else:
            return "(No function prototypes)"

    def _build_sql_operations_section(self, context: Dict[str, Any]) -> str:
        """Build SQL operations section."""
        sql_ops = context.get("sql_operations", {})
        if sql_ops:
            lines = []
            for sql_type, count in sql_ops.items():
                lines.append(f"- {sql_type}: {count} statements")
            return "\n".join(lines)
        else:
            return "(No SQL statements)"

    def _build_header_dependencies_section(self, context: Dict[str, Any]) -> str:
        """Build header dependencies section."""
        headers = context.get("header_dependencies", [])
        if headers:
            lines = []
            for header in headers:
                lines.append(f"- {header}")
            return "\n".join(lines)
        else:
            return "(No external headers)"

    def _build_function_specific_sections(self, context: Dict[str, Any]) -> str:
        """Build function-specific sections."""
        lines = []

        # Documentation
        documentation = context.get("documentation", "")
        if documentation:
            lines.append("### Original Documentation:")
            lines.append("```")
            lines.append(documentation)
            lines.append("```")
            lines.append("")

        # Original code
        original_code = context.get("original_code", "")
        if original_code:
            lines.append("### Original Pro*C Code:")
            lines.append("```c")
            lines.append(original_code[:500])
            if len(original_code) > 500:
                lines.append("... (truncated)")
            lines.append("```")
            lines.append("")

        # SQL statements
        sql_stats = context.get("sql_statements", [])
        if sql_stats:
            lines.append("### SQL Statements in this function:")
            for i, sql in enumerate(sql_stats, start=1):
                sql_type = sql.get("sql_type", "UNKNOWN")
                lines.append(f"#### SQL #{i} ({sql_type}):")
                lines.append("```sql")
                lines.append(sql.get("raw_content", "")[:500])
                if len(sql.get("raw_content", "")) > 500:
                    lines.append("... (truncated)")
                lines.append("```")
            lines.append("")

        # Local variables
        local_vars = context.get("local_variables", [])
        if local_vars:
            lines.append("### Local Variables:")
            for var in local_vars[:10]:
                var_type = var.get("var_type", "unknown")
                var_name = var.get("name", "unknown")
                array_sizes = var.get("resolved_array_sizes") or var.get("array_sizes", [])
                suffix = "".join(f"[{'' if size is None else size}]" for size in array_sizes) if array_sizes else ""
                lines.append(f"- `{var_type} {var_name}{suffix}`")
            if len(local_vars) > 10:
                lines.append(f"- ... and {len(local_vars) - 10} more")
            lines.append("")

        # Called functions
        called_funcs = context.get("called_functions", [])
        if called_funcs:
            lines.append("### Called Functions:")
            for call in called_funcs[:15]:
                lines.append(f"- `{call}`")
            lines.append("")

        # Class fields
        class_fields = context.get("class_fields", [])
        if class_fields:
            lines.append("### Available Class Fields (from skeleton):")
            for field in class_fields[:10]:
                java_type = field.get("java_type", "Object")
                field_name = field.get("name", "unknown")
                lines.append(f"- `{java_type} {field_name}`")
            lines.append("")

        return "\n".join(lines)

    def _build_output_requirements_section(self, context: Dict[str, Any]) -> str:
        """Build output requirements section."""
        lines = ["### Required Output:"]
        if "function_name" in context:
            lines.extend([
                "Generate a Java method with:",
                "1. Proper Java return type",
                "2. Appropriate exception handling",
                "3. MyBatis mapper method calls instead of SQL",
                "4. Spring service calls instead of BAM calls",
            ])
        else:
            lines.extend([
                "Generate a Java class skeleton with:",
                "1. Proper package declaration",
                "2. Required imports (Spring, MyBatis, etc.)",
                "3. Class-level annotations (@Service, @Slf4j if applicable)",
                "4. Private fields from global variables (with proper Java types)",
                "5. Method signatures only (no implementations, just method stubs)",
                "6. Constructor with dependency injection",
            ])

        lines.append("")
        lines.append("Output only Java code, no explanations.")
        return "\n".join(lines)


# ============================================================================
# PROMPT INJECTOR
# ============================================================================

class PromptInjector:
    """
    Advanced prompt builder with context injection capabilities.

    Features:
    - F-string based template building (no external dependencies)
    - Section-based composition
    - Multiple context sources (metadata, previous, custom)
    - Variable validation
    - Template registry with custom templates
    """

    def __init__(self, template: PromptTemplate):
        """
        Args:
            template: PromptTemplate instance to use for rendering
        """
        self.template = template

    def build(self, context: Dict[str, Any]) -> str:
        """
        Build complete prompt with all necessary context injected.

        Args:
            context: Dictionary containing all context variables

        Returns:
            Complete prompt with all context sections
        """
        return self.template.build(context)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_skeleton_prompt(context: Dict[str, Any]) -> str:
    """
    Convenience function to create a skeleton prompt.

    Args:
        context: Full conversion context

    Returns:
        Rendered skeleton prompt
    """
    template = PromptTemplate("skeleton")
    injector = PromptInjector(template)
    return injector.build(context)


def create_function_prompt(context: Dict[str, Any]) -> str:
    """
    Convenience function to create a function prompt.

    Args:
        context: Full conversion context including function-specific data

    Returns:
        Rendered function prompt
    """
    template = PromptTemplate("function")
    injector = PromptInjector(template)
    return injector.build(context)


def build_complete_prompt(
    system_prompt: Optional[str] = None,
    sections: Optional[List[str]] = None,
) -> str:
    """
    Build a complete prompt from multiple sections.

    Args:
        system_prompt: Optional custom system prompt
        sections: List of prompt sections to join

    Returns:
        Complete prompt string
    """
    prompt_parts = []
    if system_prompt:
        prompt_parts.append(system_prompt)
    else:
        prompt_parts.append(TemplateRegistry.get_template("system"))

    if sections:
        prompt_parts.extend(sections)

    return "\n\n".join(prompt_parts)
