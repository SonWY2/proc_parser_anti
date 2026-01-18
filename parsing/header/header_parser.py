"""
헤더 파서 메인 클래스
typedef 구조체와 STP 정보를 통합하여 db_vars_info 구조를 생성합니다.

플러그인 아키텍처를 사용하여 다양한 헤더 포맷을 확장 가능하게 지원합니다.
"""
import os
import sys
from typing import Dict, List, Optional, Any

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 하위 호환성을 위해 기존 파서 import 유지
from .typedef_parser import TypedefStructParser, StructInfo, FieldInfo
from .stp_parser import STPParser
from .parser_interface import HeaderParserPlugin, ParseContext, HeaderFormatType

from infra.config import (
    get_java_type,
    snake_to_camel,
    camel_to_pascal,
    find_count_field,
    is_custom_struct,
    PRIMITIVE_TYPES,
)
from infra.config.logger import logger


class HeaderParser:
    """
    C 헤더 파일 파서 메인 클래스
    
    플러그인 아키텍처를 사용하여 다양한 헤더 포맷을 지원합니다.
    기본적으로 typedef 구조체, STP 배열, 매크로를 처리하는 플러그인이 등록됩니다.
    
    사용 예:
        # 기본 사용 (하위 호환성 유지)
        parser = HeaderParser()
        result = parser.parse_file("sample.h")
        
        # 커스텀 플러그인 추가
        parser = HeaderParser(use_plugins=True)
        parser.register_plugin(MyCustomPlugin())
        result = parser.parse(header_content)
    """
    
    def __init__(
        self,
        external_macros: Optional[Dict[str, int]] = None,
        count_field_mapping: Optional[Dict[str, str]] = None,
        use_plugins: bool = False
    ):
        """
        Args:
            external_macros: 외부 매크로 값 딕셔너리 (예: {"MAX_SIZE": 30})
            count_field_mapping: count 필드 수동 매핑 (예: {"outrec1": "total_count"})
            use_plugins: True면 플러그인 시스템 사용, False면 기존 직접 호출 방식
        """
        # 기존 파서 (하위 호환성)
        self.typedef_parser = TypedefStructParser()
        self.stp_parser = STPParser()
        self.external_macros = external_macros or {}
        self.count_field_mapping = count_field_mapping or {}
        
        # 플러그인 시스템
        self._use_plugins = use_plugins
        self._plugins: List[HeaderParserPlugin] = []
        
        if use_plugins:
            self._load_default_plugins()
        
        logger.debug(f"HeaderParser 초기화 (macros: {len(self.external_macros)}개)")
    
    # ========== 플러그인 관리 ==========
    
    def register_plugin(self, plugin: HeaderParserPlugin):
        """
        플러그인 등록
        
        Args:
            plugin: HeaderParserPlugin 인스턴스
        """
        self._plugins.append(plugin)
        self._plugins.sort(key=lambda p: p.priority)
        logger.debug(f"플러그인 등록: {plugin.name} (priority={plugin.priority})")
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """
        플러그인 등록 해제
        
        Args:
            plugin_name: 제거할 플러그인 이름
            
        Returns:
            True if removed, False if not found
        """
        for i, plugin in enumerate(self._plugins):
            if plugin.name == plugin_name:
                del self._plugins[i]
                logger.debug(f"플러그인 해제: {plugin_name}")
                return True
        return False
    
    def get_plugins(self) -> List[HeaderParserPlugin]:
        """등록된 플러그인 목록 반환"""
        return list(self._plugins)
    
    def _load_default_plugins(self):
        """기본 플러그인 로드"""
        from .plugins import get_default_plugins
        for plugin in get_default_plugins():
            self.register_plugin(plugin)
    
    # ========== 파일 파싱 ==========
    
    def parse_file(self, file_path: str) -> Dict[str, Dict]:
        """
        헤더 파일을 읽어서 파싱
        
        Args:
            file_path: C 헤더 파일 경로
            
        Returns:
            db_vars_info 구조
        """
        logger.info(f"헤더 파싱 시작: {file_path}")
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        result = self.parse(content)
        logger.success(f"헤더 파싱 완료: {file_path} ({len(result)}개 구조체)")
        return result
    
    def parse(self, content: str) -> Dict[str, Dict]:
        """
        헤더 파일 내용을 파싱하여 db_vars_info 구조 생성
        
        Args:
            content: C 헤더 파일 내용
            
        Returns:
            {
                "struct_name_t": {
                    "fieldName": {
                        "dtype": "String",
                        "size": 8,
                        "decimal": 0,
                        "name": "field_name",
                        "org_name": "field_name",
                        "description": "필드 설명",
                        "arraySize": 30,         # 배열인 경우
                        "arrayReference": "fieldCountName"  # count 필드 있는 경우
                    },
                    ...
                },
                ...
            }
        """
        if self._use_plugins and self._plugins:
            return self._parse_with_plugins(content)
        else:
            return self._parse_legacy(content)
    
    def _parse_with_plugins(self, content: str) -> Dict[str, Dict]:
        """플러그인 기반 파싱"""
        context = ParseContext(macros=dict(self.external_macros))
        
        # 플러그인 순차 실행
        for plugin in self._plugins:
            if plugin.can_parse(content):
                try:
                    plugin_result = plugin.parse(content, context)
                    
                    # 결과를 컨텍스트에 병합
                    if "macros" in plugin_result:
                        context.macros.update(plugin_result["macros"])
                    if "structs" in plugin_result:
                        context.structs.update(plugin_result["structs"])
                    if "stp_data" in plugin_result:
                        context.stp_data.update(plugin_result["stp_data"])
                    if "db_vars_info" in plugin_result:
                        context.db_vars_info.update(plugin_result["db_vars_info"])
                        
                    logger.debug(f"플러그인 실행 완료: {plugin.name}")
                except Exception as e:
                    logger.error(f"플러그인 실행 실패: {plugin.name} - {e}")
        
        # 플러그인 결과를 db_vars_info로 변환 (후처리)
        return self._convert_to_db_vars_info(context)
    
    def _convert_to_db_vars_info(self, context: ParseContext) -> Dict[str, Dict]:
        """ParseContext를 db_vars_info 형식으로 변환"""
        result = {}
        
        for struct_name, struct_info in context.structs.items():
            # 구조체의 모든 필드명 집합
            field_names = {f.name for f in struct_info.fields}
            
            variables = {}
            for field in struct_info.fields:
                camel_name = snake_to_camel(field.name)
                java_type = self._get_field_java_type(field)
                
                # 매크로 값으로 배열 크기 해결
                resolved_size = self._resolve_array_size_with_context(
                    field.array_size, context.macros
                )
                
                var_info = {
                    "dtype": java_type,
                    "size": resolved_size,
                    "decimal": 0,
                    "name": field.name,
                    "org_name": field.name,
                }
                
                if field.comment:
                    var_info["description"] = field.comment
                
                if field.array_size and is_custom_struct(field.data_type):
                    var_info["arraySize"] = resolved_size
                    
                    count_field = find_count_field(
                        field.name,
                        field_names,
                        self.count_field_mapping
                    )
                    if count_field:
                        var_info["arrayReference"] = count_field
                    
                    var_info["structType"] = field.data_type
                
                variables[camel_name] = var_info
            
            # STP 정보로 size/decimal 업데이트
            stp_name = struct_name.replace('_t', '_stp')
            if stp_name in context.stp_data:
                from .plugins.stp_parser_plugin import STPParserPlugin
                STPParserPlugin.update_variables(variables, context.stp_data[stp_name])
            
            result[struct_name] = variables
        
        return result
    
    def _resolve_array_size_with_context(
        self, size_expr: Optional[str], macros: Dict[str, Any]
    ) -> int:
        """컨텍스트의 매크로를 사용하여 배열 크기 해결"""
        if not size_expr:
            return 9
        
        try:
            cleaned = size_expr.replace(' ', '')
            return eval(cleaned)
        except:
            pass
        
        # 컨텍스트 + 외부 매크로 병합
        all_macros = {**self.external_macros, **macros}
        for macro, value in all_macros.items():
            if isinstance(value, (int, float)) and macro in size_expr:
                try:
                    replaced = size_expr.replace(macro, str(value))
                    return eval(replaced)
                except:
                    pass
        
        return 9
    
    def _parse_legacy(self, content: str) -> Dict[str, Dict]:
        """기존 직접 호출 방식 파싱 (하위 호환성)"""
        # 1. typedef 구조체 파싱
        structs = self.typedef_parser.parse(content)
        
        # 2. STP 배열 파싱
        stp_data = self.stp_parser.parse(content)
        
        # 3. 구조체별로 db_vars_info 생성
        result = {}
        
        for struct_name, struct_info in structs.items():
            field_names = self.typedef_parser.get_field_names(struct_info)
            
            variables = {}
            for field in struct_info.fields:
                camel_name = snake_to_camel(field.name)
                java_type = self._get_field_java_type(field)
                
                var_info = {
                    "dtype": java_type,
                    "size": self._resolve_array_size(field.array_size),
                    "decimal": 0,
                    "name": field.name,
                    "org_name": field.name,
                }
                
                if field.comment:
                    var_info["description"] = field.comment
                
                if field.array_size and is_custom_struct(field.data_type):
                    var_info["arraySize"] = self._resolve_array_size(field.array_size)
                    
                    count_field = find_count_field(
                        field.name,
                        field_names,
                        self.count_field_mapping
                    )
                    if count_field:
                        var_info["arrayReference"] = count_field
                    
                    var_info["structType"] = field.data_type
                
                variables[camel_name] = var_info
            
            # STP 정보로 size/decimal 업데이트
            stp_name = struct_name.replace('_t', '_stp')
            if stp_name in stp_data:
                self.stp_parser.update_variables(variables, stp_data[stp_name])
            
            result[struct_name] = variables
        
        return result
    
    def _get_field_java_type(self, field: FieldInfo) -> str:
        """필드의 Java 타입 결정"""
        if field.data_type in PRIMITIVE_TYPES or field.data_type.lower() in PRIMITIVE_TYPES:
            return get_java_type(field.data_type.lower())
        
        return camel_to_pascal(snake_to_camel(field.data_type))
    
    def _resolve_array_size(self, size_expr: Optional[str]) -> int:
        """배열 크기 표현식을 정수로 변환"""
        if not size_expr:
            return 9
        
        try:
            cleaned = size_expr.replace(' ', '')
            return eval(cleaned)
        except:
            pass
        
        for macro, value in self.external_macros.items():
            if macro in size_expr:
                try:
                    replaced = size_expr.replace(macro, str(value))
                    return eval(replaced)
                except:
                    pass
        
        return 9
