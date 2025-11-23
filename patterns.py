import re

# Include: #include <...> or #include "..."
# Captures: quote_type (< or "), path, quote_type (> or ")
PATTERN_INCLUDE = re.compile(r'#include\s+([<"])(.*?)([>"])')

# Macro: #define NAME VALUE
# Captures: name, value (optional)
PATTERN_MACRO = re.compile(r'#define\s+(\w+)(?:\s+(.*?))?$', re.MULTILINE)

# SQL Block: EXEC SQL ... ;
# Using DOTALL to match across lines.
# Captures: content inside EXEC SQL ... ;
PATTERN_SQL = re.compile(r'EXEC\s+SQL\s+(.*?);', re.DOTALL | re.IGNORECASE)

# Special Construct: BAMCALL(...)
# Captures: arguments inside BAMCALL(...)
PATTERN_BAMCALL = re.compile(r'BAMCALL\s*\((.*?)\);', re.DOTALL)

# Host Variable in SQL: :var
# Edge case handling:
# 1. Negative lookbehind to avoid matching inside strings (simplified check)
# 2. Check for valid identifier after colon
# Note: A full context-aware parser is better, but regex can approximate.
# We will use a simpler regex here and refine in the converter logic.
PATTERN_HOST_VAR = re.compile(r':([a-zA-Z_]\w*)')

# Comments
PATTERN_COMMENT_SINGLE = re.compile(r'//.*')
PATTERN_COMMENT_MULTI = re.compile(r'/\*.*?\*/', re.DOTALL)

# Function Definition (Heuristic for C)
# ReturnType FunctionName(Args) { ... }
# This is very hard with regex, relying on Tree-sitter is better.
# But we might need a fallback or quick check.

# Variable Declaration (Heuristic)
# Type Name; or Type Name = Value;

