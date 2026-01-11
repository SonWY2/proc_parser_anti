"""
Prompt Formatter

FunctionContext를 다양한 LLM 프롬프트 형식으로 변환합니다.
"""

from typing import Dict, List, Optional
from ..types import FunctionContext


class PromptFormatter:
    """
    LLM 프롬프트 형식 변환기
    
    다양한 프롬프트 템플릿 지원:
    - markdown: 기본 Markdown 형식
    - compact: 토큰 절약용 압축 형식
    - xml: XML 태그 형식
    """
    
    def __init__(self, format_type: str = "markdown"):
        """
        Args:
            format_type: 'markdown', 'compact', 'xml'
        """
        self.format_type = format_type
    
    def format(self, context: FunctionContext, 
               include_source: bool = True,
               max_vars: int = 20,
               max_sql_length: int = 500) -> str:
        """
        FunctionContext를 프롬프트로 변환
        
        Args:
            context: FunctionContext 객체
            include_source: 소스 코드 포함 여부
            max_vars: 최대 변수 표시 수
            max_sql_length: SQL 최대 길이
            
        Returns:
            포맷된 프롬프트 문자열
        """
        if self.format_type == "compact":
            return self._format_compact(context, include_source, max_vars, max_sql_length)
        elif self.format_type == "xml":
            return self._format_xml(context, include_source, max_vars, max_sql_length)
        else:
            return self._format_markdown(context, include_source, max_vars, max_sql_length)
    
    def _format_markdown(self, ctx: FunctionContext, 
                         include_source: bool,
                         max_vars: int,
                         max_sql_length: int) -> str:
        """Markdown 형식"""
        lines = []
        
        # 함수 정보
        lines.append(f"# Function: {ctx.name}")
        lines.append(f"**Return:** `{ctx.return_type}` | **Lines:** {ctx.line_range[0]}-{ctx.line_range[1]}")
        
        if ctx.parameters:
            params = ", ".join(f"`{p.get('type','')} {p.get('name','')}`" for p in ctx.parameters)
            lines.append(f"**Parameters:** {params}")
        
        # 변수
        if ctx.local_variables or ctx.host_variables:
            lines.append("\n## Variables")
            
            if ctx.local_variables:
                lines.append(f"### Local ({len(ctx.local_variables)})")
                for v in ctx.local_variables[:max_vars]:
                    mapping = f" → `{v.java_name}`" if v.java_name else ""
                    lines.append(f"- `{v.data_type} {v.name}`{mapping}")
            
            if ctx.host_variables:
                lines.append(f"### Host ({len(ctx.host_variables)})")
                for h in ctx.host_variables[:max_vars]:
                    icon = "⬇️" if h.direction == "input" else "⬆️"
                    lines.append(f"- {icon} `:{h.name}` ({h.sql_id})")
        
        # SQL
        if ctx.sql_statements:
            lines.append(f"\n## SQL ({len(ctx.sql_statements)})")
            for sql in ctx.sql_statements:
                lines.append(f"### {sql.sql_id} ({sql.sql_type})")
                if sql.normalized_sql:
                    snippet = sql.normalized_sql[:max_sql_length]
                    if len(sql.normalized_sql) > max_sql_length:
                        snippet += " ..."
                    lines.append(f"```sql\n{snippet}\n```")
        
        # 의존성
        deps_parts = []
        if ctx.called_functions:
            deps_parts.append(f"Calls: {', '.join(ctx.called_functions)}")
        if ctx.used_structs:
            deps_parts.append(f"Structs: {', '.join(s.name for s in ctx.used_structs)}")
        if ctx.bam_calls:
            deps_parts.append(f"BAM: {', '.join(b.name for b in ctx.bam_calls)}")
        if deps_parts:
            lines.append(f"\n## Dependencies")
            for d in deps_parts:
                lines.append(f"- {d}")
        
        # 매핑
        if ctx.variable_mappings:
            lines.append(f"\n## Mappings")
            for proc, java in list(ctx.variable_mappings.items())[:10]:
                lines.append(f"- {proc} → {java}")
        
        # 소스
        if include_source and ctx.raw_content:
            lines.append(f"\n## Source")
            lines.append(f"```c\n{ctx.get_raw_content_snippet(30)}\n```")
        
        return "\n".join(lines)
    
    def _format_compact(self, ctx: FunctionContext,
                        include_source: bool,
                        max_vars: int,
                        max_sql_length: int) -> str:
        """토큰 절약용 압축 형식"""
        parts = []
        
        # 함수 시그니처
        params = ",".join(f"{p.get('type','')} {p.get('name','')}" for p in ctx.parameters)
        parts.append(f"[FUNC]{ctx.return_type} {ctx.name}({params})")
        
        # 변수 (압축)
        if ctx.local_variables:
            vars_str = ";".join(f"{v.data_type} {v.name}" for v in ctx.local_variables[:max_vars])
            parts.append(f"[VARS]{vars_str}")
        
        # 호스트 변수
        if ctx.host_variables:
            hvars = ";".join(f"{h.direction[0]}:{h.name}" for h in ctx.host_variables[:max_vars])
            parts.append(f"[HOST]{hvars}")
        
        # SQL (압축)
        if ctx.sql_statements:
            for sql in ctx.sql_statements:
                sql_str = (sql.normalized_sql or "")[:max_sql_length//2]
                parts.append(f"[SQL:{sql.sql_type}]{sql_str}")
        
        # 매핑
        if ctx.variable_mappings:
            maps = ";".join(f"{k}->{v}" for k,v in list(ctx.variable_mappings.items())[:10])
            parts.append(f"[MAP]{maps}")
        
        # 소스 (매우 축약)
        if include_source and ctx.raw_content:
            parts.append(f"[SRC]{ctx.get_raw_content_snippet(15)}")
        
        return "\n".join(parts)
    
    def _format_xml(self, ctx: FunctionContext,
                    include_source: bool,
                    max_vars: int,
                    max_sql_length: int) -> str:
        """XML 태그 형식"""
        lines = []
        
        lines.append("<function>")
        lines.append(f"  <name>{ctx.name}</name>")
        lines.append(f"  <return_type>{ctx.return_type}</return_type>")
        
        if ctx.parameters:
            lines.append("  <parameters>")
            for p in ctx.parameters:
                lines.append(f"    <param type='{p.get('type','')}' name='{p.get('name','')}' />")
            lines.append("  </parameters>")
        
        if ctx.local_variables:
            lines.append("  <variables>")
            for v in ctx.local_variables[:max_vars]:
                java = f" java='{v.java_name}'" if v.java_name else ""
                lines.append(f"    <var type='{v.data_type}' name='{v.name}'{java} />")
            lines.append("  </variables>")
        
        if ctx.sql_statements:
            lines.append("  <sql_statements>")
            for sql in ctx.sql_statements:
                snippet = (sql.normalized_sql or "")[:max_sql_length]
                lines.append(f"    <sql id='{sql.sql_id}' type='{sql.sql_type}'>")
                lines.append(f"      <query><![CDATA[{snippet}]]></query>")
                if sql.input_vars:
                    lines.append(f"      <inputs>{','.join(sql.input_vars)}</inputs>")
                if sql.output_vars:
                    lines.append(f"      <outputs>{','.join(sql.output_vars)}</outputs>")
                lines.append("    </sql>")
            lines.append("  </sql_statements>")
        
        if ctx.variable_mappings:
            lines.append("  <mappings>")
            for proc, java in list(ctx.variable_mappings.items())[:10]:
                lines.append(f"    <map from='{proc}' to='{java}' />")
            lines.append("  </mappings>")
        
        if include_source and ctx.raw_content:
            lines.append("  <source>")
            lines.append(f"    <![CDATA[{ctx.get_raw_content_snippet(30)}]]>")
            lines.append("  </source>")
        
        lines.append("</function>")
        
        return "\n".join(lines)
