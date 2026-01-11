"""
Context Extractor

VariableLineageTracker와 proc_parser 결과에서 
Function 레벨 컨텍스트를 추출합니다.
"""

from typing import Dict, List, Optional, Any, Set
from .types import (
    FunctionContext,
    VariableInfo,
    HostVariableInfo,
    SQLInfo,
    StructInfo,
    BamCallInfo,
    OMMFieldInfo,
)

# 부모 패키지에서 타입 import
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ContextExtractor:
    """
    Function 레벨 컨텍스트 추출기
    
    Usage:
        from variable_lineage import VariableLineageTracker
        from variable_lineage.context_extractor import ContextExtractor
        
        tracker = VariableLineageTracker(source_file="sample.pc")
        tracker.add_all_program_elements(elements)
        tracker.add_java_variables()
        tracker.build_links()
        
        extractor = ContextExtractor(tracker, elements)
        context = extractor.extract_function_context("main")
        prompt = extractor.to_prompt(context)
    """
    
    def __init__(self, tracker, elements: List[Dict], 
                 db_vars_info: Optional[Dict] = None):
        """
        Args:
            tracker: VariableLineageTracker 인스턴스
            elements: ProCParser.parse_file() 결과
            db_vars_info: HeaderParser 결과 (구조체 정보)
        """
        self.tracker = tracker
        self.elements = elements
        self.db_vars_info = db_vars_info or {}
        
        # 인덱스 구축
        self._build_indices()
    
    def _build_indices(self):
        """빠른 조회를 위한 인덱스 구축"""
        # 함수 인덱스
        self.functions = {
            el['name']: el 
            for el in self.elements 
            if el.get('type') == 'function'
        }
        
        # 함수별 요소 인덱스
        self.elements_by_function: Dict[str, List[Dict]] = {}
        for el in self.elements:
            func_name = el.get('function')
            if func_name:
                if func_name not in self.elements_by_function:
                    self.elements_by_function[func_name] = []
                self.elements_by_function[func_name].append(el)
        
        # 매크로 인덱스
        self.macros = {
            el['name']: el.get('value', '')
            for el in self.elements 
            if el.get('type') == 'macro'
        }
        
        # 변수 → Java 변수 매핑 구축
        self.var_mappings: Dict[str, str] = {}
        # 구조체 필드 → OMM 필드 매핑
        self.struct_to_omm: Dict[str, Dict[str, str]] = {}  # struct_name → {field → omm_field}
        
        if self.tracker:
            for link in self.tracker.graph.links:
                source_node = self.tracker.graph.get_node(link.source_id)
                target_node = self.tracker.graph.get_node(link.target_id)
                
                if not source_node or not target_node:
                    continue
                
                # ProCVariable → JavaVariable 매핑
                if link.target_id.startswith('java_var_'):
                    self.var_mappings[source_node.name] = target_node.name
                
                # StructField → OMMField 매핑
                if link.source_id.startswith('struct_field_') and link.target_id.startswith('omm_field_'):
                    # struct_field_{struct}_{field} 파싱
                    parts = link.source_id.replace('struct_field_', '').split('_', 1)
                    if len(parts) == 2:
                        struct_name, field_name = parts
                        if struct_name not in self.struct_to_omm:
                            self.struct_to_omm[struct_name] = {}
                        self.struct_to_omm[struct_name][field_name] = target_node.name
    
    def extract_function_context(self, func_name: str) -> Optional[FunctionContext]:
        """
        특정 함수의 전체 컨텍스트 추출
        
        Args:
            func_name: 함수명
            
        Returns:
            FunctionContext 또는 None (함수를 찾지 못한 경우)
        """
        if func_name not in self.functions:
            return None
        
        func = self.functions[func_name]
        func_elements = self.elements_by_function.get(func_name, [])
        
        # 1. 로컬 변수 추출
        local_vars = self._extract_local_variables(func_elements)
        
        # 2. SQL 및 호스트 변수 추출
        sql_list, host_vars = self._extract_sql_info(func_elements)
        
        # 3. BAM 호출 추출
        bam_calls = self._extract_bam_calls(func_elements)
        
        # 4. 호출하는 함수 추출
        called_funcs = self._extract_called_functions(func_elements)
        
        # 5. 사용하는 구조체 추출
        used_structs = self._extract_used_structs(local_vars, host_vars)
        
        # 6. 사용하는 매크로 추출
        used_macros = self._extract_used_macros(local_vars)
        
        # 7. OMM 필드 추출
        omm_fields = self._extract_omm_fields(used_structs, host_vars)
        
        # 8. 변환 매핑 (함수 내 변수만)
        var_names = set(v.name for v in local_vars)
        var_names.update(h.name for h in host_vars)
        mappings = {
            name: self.var_mappings[name]
            for name in var_names
            if name in self.var_mappings
        }
        
        return FunctionContext(
            name=func_name,
            return_type=func.get('return_type', 'void'),
            parameters=func.get('parameters', []),
            docstring=func.get('docstring'),
            raw_content=func.get('raw_content', ''),
            line_range=(func.get('line_start', 0), func.get('line_end', 0)),
            local_variables=local_vars,
            host_variables=host_vars,
            sql_statements=sql_list,
            called_functions=called_funcs,
            used_structs=used_structs,
            bam_calls=bam_calls,
            used_macros=used_macros,
            omm_fields=omm_fields,
            variable_mappings=mappings,
        )
    
    def extract_all_contexts(self) -> Dict[str, FunctionContext]:
        """모든 함수의 컨텍스트 추출"""
        return {
            name: self.extract_function_context(name)
            for name in self.functions
        }
    
    def _extract_local_variables(self, func_elements: List[Dict]) -> List[VariableInfo]:
        """로컬 변수 추출"""
        variables = []
        for el in func_elements:
            if el.get('type') != 'variable':
                continue
            
            var = VariableInfo(
                name=el.get('name', ''),
                data_type=el.get('data_type', ''),
                array_size=el.get('array_size') or (
                    el.get('resolved_array_sizes', [None])[0] 
                    if el.get('resolved_array_sizes') else None
                ),
                scope=el.get('scope', 'local'),
                line_start=el.get('line_start'),
                java_name=self.var_mappings.get(el.get('name'))
            )
            variables.append(var)
        
        return variables
    
    def _extract_sql_info(self, func_elements: List[Dict]) -> tuple:
        """SQL 정보 및 호스트 변수 추출"""
        sql_list = []
        host_vars = []
        
        for el in func_elements:
            if el.get('type') != 'sql':
                continue
            
            sql_id = el.get('sql_id', '')
            input_vars = el.get('input_host_vars', [])
            output_vars = el.get('output_host_vars', [])
            
            sql_info = SQLInfo(
                sql_id=sql_id,
                sql_type=el.get('sql_type', 'UNKNOWN'),
                raw_content=el.get('raw_content', ''),
                normalized_sql=el.get('normalized_sql'),
                input_vars=input_vars,
                output_vars=output_vars,
                line_start=el.get('line_start'),
                relationship=el.get('relationship'),
            )
            sql_list.append(sql_info)
            
            # 호스트 변수 추출
            for var in input_vars:
                var_name = var.lstrip(':')
                host_var = HostVariableInfo(
                    name=var_name,
                    direction='input',
                    sql_id=sql_id,
                    java_name=self.var_mappings.get(var_name),
                    struct_field=var_name if '.' in var_name else None
                )
                host_vars.append(host_var)
            
            for var in output_vars:
                var_name = var.lstrip(':')
                host_var = HostVariableInfo(
                    name=var_name,
                    direction='output',
                    sql_id=sql_id,
                    java_name=self.var_mappings.get(var_name),
                    struct_field=var_name if '.' in var_name else None
                )
                host_vars.append(host_var)
        
        return sql_list, host_vars
    
    def _extract_bam_calls(self, func_elements: List[Dict]) -> List[BamCallInfo]:
        """BAM 호출 추출"""
        bam_calls = []
        for el in func_elements:
            if el.get('type') != 'bam_call':
                continue
            
            bam = BamCallInfo(
                name=el.get('name', ''),
                arguments=el.get('arguments', []),
                line_start=el.get('line_start')
            )
            bam_calls.append(bam)
        
        return bam_calls
    
    def _extract_called_functions(self, func_elements: List[Dict]) -> List[str]:
        """호출하는 함수 목록 추출 (간단한 휴리스틱)"""
        called = set()
        
        # BAM 호출에서 추출
        for el in func_elements:
            if el.get('type') == 'bam_call':
                called.add(el.get('name', ''))
        
        # 함수 본문에서 다른 함수 호출 패턴 검색 (간단한 휴리스틱)
        # 실제로는 AST 분석이 필요하나, 여기서는 tracker의 CALLS 관계 사용
        if self.tracker:
            func_node_id = f"function_{self.elements_by_function}"
            for link in self.tracker.graph.links:
                if link.source_id.startswith('function_') and hasattr(link, 'link_type'):
                    from ..types import LinkType
                    if link.link_type == LinkType.CALLS:
                        target = self.tracker.graph.get_node(link.target_id)
                        if target:
                            called.add(target.name)
        
        return list(called)
    
    def _extract_used_structs(self, local_vars: List[VariableInfo], 
                              host_vars: List[HostVariableInfo]) -> List[StructInfo]:
        """사용하는 구조체 추출"""
        struct_names: Set[str] = set()
        
        # 변수 타입에서 구조체 이름 추출
        for var in local_vars:
            dtype = var.data_type
            if dtype and not dtype in ('int', 'char', 'long', 'double', 'float', 'void'):
                # 사용자 정의 타입일 가능성
                struct_names.add(dtype.replace('*', '').strip())
        
        # 호스트 변수에서 구조체.필드 패턴 추출
        for hv in host_vars:
            if '.' in hv.name:
                struct_name = hv.name.split('.')[0]
                struct_names.add(struct_name)
        
        # db_vars_info에서 구조체 정보 가져오기
        structs = []
        for name in struct_names:
            fields = self.db_vars_info.get(name, {})
            field_mappings = self.struct_to_omm.get(name, {})
            
            # DTO 클래스 이름 추측 (snake_case → PascalCase)
            dto_class = None
            if fields:  # 필드가 있으면 실제 구조체
                dto_class = self._to_pascal_case(name)
            
            struct = StructInfo(
                name=name,
                fields=fields,
                dto_class=dto_class,
                field_mappings=field_mappings,
            )
            structs.append(struct)
        
        return structs
    
    def _extract_omm_fields(self, used_structs: List[StructInfo], 
                            host_vars: List[HostVariableInfo]) -> List[OMMFieldInfo]:
        """
        사용되는 OMM 필드 정보 추출
        
        Args:
            used_structs: 사용되는 구조체 리스트
            host_vars: 호스트 변수 리스트
            
        Returns:
            OMM 필드 정보 리스트
        """
        omm_fields = []
        seen_fields = set()
        
        # 1. 구조체 필드에서 OMM 필드 추출
        for struct in used_structs:
            for field_name, field_info in struct.fields.items():
                omm_name = struct.field_mappings.get(field_name, field_name)
                
                if omm_name in seen_fields:
                    continue
                seen_fields.add(omm_name)
                
                # dtype을 Java 타입으로 변환
                java_type = self._c_to_java_type(field_info.get('dtype', 'String'))
                
                omm_field = OMMFieldInfo(
                    name=omm_name,
                    java_type=java_type,
                    length=field_info.get('size'),
                    description=field_info.get('description'),
                    original_struct_field=f"{struct.name}.{field_name}"
                )
                omm_fields.append(omm_field)
        
        # 2. 호스트 변수에서 직접 추적
        for hv in host_vars:
            if '.' in hv.name:
                parts = hv.name.split('.')
                if len(parts) == 2:
                    struct_name, field_name = parts
                    omm_name = hv.java_name or self._snake_to_camel(field_name)
                    
                    if omm_name in seen_fields:
                        continue
                    seen_fields.add(omm_name)
                    
                    omm_field = OMMFieldInfo(
                        name=omm_name,
                        java_type="String",  # 기본값
                        description=f"From host var :{hv.name}",
                        original_struct_field=hv.name
                    )
                    omm_fields.append(omm_field)
        
        return omm_fields
    
    def _to_pascal_case(self, name: str) -> str:
        """스네이크_케이스를 PascalCase로 변환"""
        return ''.join(word.title() for word in name.split('_'))
    
    def _snake_to_camel(self, name: str) -> str:
        """스네이크_케이스를 camelCase로 변환"""
        parts = name.split('_')
        return parts[0].lower() + ''.join(p.title() for p in parts[1:])
    
    def _c_to_java_type(self, c_type: str) -> str:
        """C 타입을 Java 타입으로 변환"""
        type_map = {
            'char': 'String',
            'int': 'Integer',
            'long': 'Long',
            'double': 'BigDecimal',
            'float': 'Float',
        }
        return type_map.get(c_type.lower().strip(), c_type)
    
    def _extract_used_macros(self, local_vars: List[VariableInfo]) -> List[str]:
        """사용하는 매크로 추출"""
        used = set()
        
        for var in local_vars:
            if var.array_size and var.array_size in self.macros:
                used.add(var.array_size)
        
        return list(used)
    
    # ===== 출력 포맷터 =====
    
    def to_prompt(self, context: FunctionContext, 
                  include_raw_content: bool = True,
                  max_sql_length: int = 500) -> str:
        """
        FunctionContext를 LLM 프롬프트 형식으로 변환
        
        Args:
            context: FunctionContext 객체
            include_raw_content: 함수 본문 포함 여부
            max_sql_length: SQL 최대 길이 (잘라냄)
            
        Returns:
            프롬프트 문자열
        """
        lines = []
        
        # 함수 기본 정보
        lines.append(f"## Function: {context.name}")
        lines.append(f"- Return Type: `{context.return_type}`")
        if context.parameters:
            params = ", ".join(
                f"{p.get('type', '')} {p.get('name', '')}" 
                for p in context.parameters
            )
            lines.append(f"- Parameters: `{params}`")
        lines.append(f"- Lines: {context.line_range[0]}-{context.line_range[1]}")
        
        if context.docstring:
            lines.append(f"\n### Documentation")
            lines.append(context.docstring)
        
        # 변수 정보
        if context.local_variables:
            lines.append(f"\n### Local Variables ({len(context.local_variables)})")
            for var in context.local_variables[:10]:  # 최대 10개
                java_map = f" → `{var.java_name}`" if var.java_name else ""
                lines.append(f"- `{var.data_type} {var.name}`{java_map}")
            if len(context.local_variables) > 10:
                lines.append(f"- ... ({len(context.local_variables) - 10} more)")
        
        # 호스트 변수
        if context.host_variables:
            lines.append(f"\n### Host Variables ({len(context.host_variables)})")
            for hv in context.host_variables[:10]:
                dir_icon = "→" if hv.direction == "input" else "←"
                java_map = f" = `{hv.java_name}`" if hv.java_name else ""
                lines.append(f"- `:{hv.name}` {dir_icon} {hv.sql_id}{java_map}")
            if len(context.host_variables) > 10:
                lines.append(f"- ... ({len(context.host_variables) - 10} more)")
        
        # SQL 정보
        if context.sql_statements:
            lines.append(f"\n### SQL Statements ({len(context.sql_statements)})")
            for sql in context.sql_statements:
                lines.append(f"\n#### {sql.sql_id} ({sql.sql_type})")
                if sql.input_vars:
                    lines.append(f"- Input: `{', '.join(sql.input_vars[:5])}`")
                if sql.output_vars:
                    lines.append(f"- Output: `{', '.join(sql.output_vars[:5])}`")
                if sql.normalized_sql:
                    sql_snippet = sql.normalized_sql[:max_sql_length]
                    if len(sql.normalized_sql) > max_sql_length:
                        sql_snippet += "..."
                    lines.append(f"```sql\n{sql_snippet}\n```")
        
        # 의존성
        deps = []
        if context.called_functions:
            deps.append(f"Functions: {', '.join(context.called_functions)}")
        if context.used_structs:
            deps.append(f"Structs: {', '.join(s.name for s in context.used_structs)}")
        if context.bam_calls:
            deps.append(f"BAM: {', '.join(b.name for b in context.bam_calls)}")
        if deps:
            lines.append(f"\n### Dependencies")
            for dep in deps:
                lines.append(f"- {dep}")
        
        # 변환 매핑
        if context.variable_mappings:
            lines.append(f"\n### Variable Mappings")
            for proc, java in list(context.variable_mappings.items())[:10]:
                lines.append(f"- `{proc}` → `{java}`")
        
        # 함수 본문 (선택)
        if include_raw_content and context.raw_content:
            lines.append(f"\n### Source Code")
            snippet = context.get_raw_content_snippet(max_lines=50)
            lines.append(f"```c\n{snippet}\n```")
        
        return "\n".join(lines)
    
    def to_json(self, context: FunctionContext, indent: int = 2) -> str:
        """FunctionContext를 JSON 형식으로 변환"""
        import json
        return json.dumps(context.to_dict(), indent=indent, ensure_ascii=False)
