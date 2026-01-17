"""
Context Extractor 타입 정의

FunctionContext 및 관련 데이터 클래스를 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class VariableInfo:
    """변수 정보"""
    name: str
    data_type: str
    array_size: Optional[str] = None
    scope: str = "local"  # local, global, static
    line_start: Optional[int] = None
    java_name: Optional[str] = None  # 변환된 Java 변수명
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "data_type": self.data_type,
            "array_size": self.array_size,
            "scope": self.scope,
            "java_name": self.java_name
        }


@dataclass
class HostVariableInfo:
    """SQL 호스트 변수 정보"""
    name: str
    direction: str  # input, output
    sql_id: str
    java_name: Optional[str] = None
    struct_field: Optional[str] = None  # 구조체.필드 형식인 경우
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "direction": self.direction,
            "sql_id": self.sql_id,
            "java_name": self.java_name,
            "struct_field": self.struct_field
        }


@dataclass
class SQLInfo:
    """SQL 문 정보"""
    sql_id: str
    sql_type: str  # SELECT, INSERT, UPDATE, DELETE, etc.
    raw_content: str
    normalized_sql: Optional[str] = None
    input_vars: List[str] = field(default_factory=list)
    output_vars: List[str] = field(default_factory=list)
    line_start: Optional[int] = None
    mybatis_id: Optional[str] = None
    relationship: Optional[Dict] = None  # cursor, transaction 등
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sql_id": self.sql_id,
            "sql_type": self.sql_type,
            "normalized_sql": self.normalized_sql,
            "input_vars": self.input_vars,
            "output_vars": self.output_vars,
            "mybatis_id": self.mybatis_id,
            "relationship": self.relationship
        }


@dataclass
class StructInfo:
    """구조체 정보"""
    name: str
    fields: Dict[str, Dict[str, Any]]  # field_name → field_info
    dto_class: Optional[str] = None  # 대응되는 DTO 클래스명
    field_mappings: Dict[str, str] = field(default_factory=dict)  # struct_field → omm_field
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "field_count": len(self.fields),
            "dto_class": self.dto_class,
            "fields": {k: {"dtype": v.get("dtype"), "description": v.get("description")} 
                       for k, v in list(self.fields.items())[:10]},  # 최대 10개
            "field_mappings": self.field_mappings
        }
    
    def get_field_mapping_summary(self) -> str:
        """필드 매핑 요약"""
        if not self.field_mappings:
            return "No mappings"
        mappings = [f"{k}→{v}" for k, v in list(self.field_mappings.items())[:5]]
        return ", ".join(mappings)


@dataclass
class OMMFieldInfo:
    """OMM 필드 정보"""
    name: str
    java_type: str
    length: Optional[int] = None
    description: Optional[str] = None
    original_struct_field: Optional[str] = None  # 원본 구조체 필드명
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "java_type": self.java_type,
            "length": self.length,
            "description": self.description,
            "original_struct_field": self.original_struct_field
        }


@dataclass
class BamCallInfo:
    """BAM 호출 정보"""
    name: str
    arguments: List[str] = field(default_factory=list)
    line_start: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "line_start": self.line_start
        }


@dataclass
class FunctionContext:
    """
    함수 레벨 컨텍스트 정보
    
    LLM 프롬프트에 주입할 모든 정보를 포함합니다.
    """
    # 함수 기본 정보
    name: str
    return_type: str
    parameters: List[Dict[str, Any]]
    docstring: Optional[str]
    raw_content: str
    line_range: Tuple[int, int]
    
    # 변수 정보
    local_variables: List[VariableInfo] = field(default_factory=list)
    host_variables: List[HostVariableInfo] = field(default_factory=list)
    
    # SQL 정보
    sql_statements: List[SQLInfo] = field(default_factory=list)
    
    # 의존성
    called_functions: List[str] = field(default_factory=list)
    used_structs: List[StructInfo] = field(default_factory=list)
    bam_calls: List[BamCallInfo] = field(default_factory=list)
    used_macros: List[str] = field(default_factory=list)
    
    # OMM 정보
    omm_fields: List['OMMFieldInfo'] = field(default_factory=list)
    
    # 변환 매핑
    variable_mappings: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "function": {
                "name": self.name,
                "return_type": self.return_type,
                "parameters": self.parameters,
                "docstring": self.docstring,
                "line_range": list(self.line_range),
            },
            "variables": {
                "local": [v.to_dict() for v in self.local_variables],
                "host": [h.to_dict() for h in self.host_variables],
            },
            "sql": [s.to_dict() for s in self.sql_statements],
            "dependencies": {
                "called_functions": self.called_functions,
                "structs": [s.to_dict() for s in self.used_structs],
                "bam_calls": [b.to_dict() for b in self.bam_calls],
                "macros": self.used_macros,
                "omm_fields": [o.to_dict() for o in self.omm_fields],
            },
            "mappings": self.variable_mappings,
            "summary": {
                "local_var_count": len(self.local_variables),
                "host_var_count": len(self.host_variables),
                "sql_count": len(self.sql_statements),
                "dependency_count": len(self.called_functions) + len(self.bam_calls),
            }
        }
    
    def get_raw_content_snippet(self, max_lines: int = 50) -> str:
        """함수 본문 일부 반환 (너무 길면 축약)"""
        lines = self.raw_content.split('\n')
        if len(lines) <= max_lines:
            return self.raw_content
        return '\n'.join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
